from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import os
import json
import io

# --- LOCAL IMPORTS ---
from core.evidence_processor import EvidenceProcessor
from database import update_scan_results, upsert_assets, engine, text
from reporting.report_generator import generate_csv_string

app = FastAPI()


# 1. Request Model
class ScanRequest(BaseModel):
    cloud_account_id: str
    role_arn: str
    scan_id: str
    external_id: str


# 2. Background Task Function
def run_background_scan(role_arn: str, scan_id: str, cloud_account_id: str, external_id: str):
    print(f"🚀 Starting scan for {scan_id}...")

    # Sanitize inputs
    role_arn = role_arn.strip()
    external_id = external_id.strip()

    try:
        # A. Initialize the Processor
        processor = EvidenceProcessor(role_arn=role_arn, external_id=external_id, region='us-east-1')

        # --- NEW STEP: INVENTORY COLLECTION ---
        print("🔍 Collecting Inventory...")
        assets = processor.collect_assets()

        # Save Inventory to DB (The Memory)
        upsert_assets(assets, cloud_account_id)
        # --------------------------------------

        # B. Run the Compliance Checks
        raw_findings_objects = processor.run_s3_checks()

        # C. Serialize Data
        findings_json = []
        failure_count = 0

        for finding in raw_findings_objects:
            finding_dict = {
                "control_id": getattr(finding, "control_id", "N/A"),
                "resource": getattr(finding, "resource", "Unknown"),
                "status": getattr(finding, "status", "UNKNOWN"),
                "description": getattr(finding, "description", ""),
                "evidence": getattr(finding, "evidence", {})
            }
            findings_json.append(finding_dict)

            if finding_dict["status"] == "FAIL" or finding_dict["status"] == "ERROR":
                failure_count += 1

        # D. Calculate Score
        total_items = len(findings_json)
        if total_items == 0:
            score = 100
        else:
            score = int(((total_items - failure_count) / total_items) * 100)

        # E. Save Results
        update_scan_results(
            scan_id=scan_id,
            status="COMPLETED",
            score=score,
            findings={"results": findings_json}
        )
        print(f"✅ Scan {scan_id} finished. Score: {score}")

    except Exception as e:
        print(f"💥 Scan failed: {e}")
        update_scan_results(scan_id, "FAILED", 0, {"error": str(e)})


# 3. The Scan Endpoint
@app.post("/scan")
async def start_scan(request: ScanRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(
        run_background_scan,
        request.role_arn,
        request.scan_id,
        request.cloud_account_id,
        request.external_id
    )
    return {"status": "Scan started", "scan_id": request.scan_id}


# 4. The Download Endpoint (Stays the same)
@app.get("/download/{scan_id}")
def download_report(scan_id: str):
    with engine.connect() as conn:
        result = conn.execute(
            text('SELECT findings FROM "Scan" WHERE id = :id'),
            {"id": scan_id}
        ).fetchone()

    if not result or not result[0]:
        return {"error": "Scan not found or no data available"}

    data = result[0]
    if isinstance(data, str):
        data = json.loads(data)

    findings_list = data.get("results", [])
    csv_content = generate_csv_string(findings_list)

    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=scan_report_{scan_id}.csv"}
    )


@app.get("/")
def health_check():
    return {"status": "Loxe Engine is Online"}