from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import os
import json
import io

# --- UPDATED IMPORTS ---
from core.evidence_processor import EvidenceProcessor
from database import update_scan_results, upsert_assets, update_asset_status, engine, \
    text  # <-- Added update_asset_status
from reporting.report_generator import generate_csv_string

app = FastAPI()


class ScanRequest(BaseModel):
    cloud_account_id: str
    role_arn: str
    scan_id: str
    external_id: str


def run_background_scan(role_arn: str, scan_id: str, cloud_account_id: str, external_id: str):
    print(f"🚀 Starting scan for {scan_id}...")

    role_arn = role_arn.strip()
    external_id = external_id.strip()

    try:
        # A. Initialize
        processor = EvidenceProcessor(role_arn=role_arn, external_id=external_id, region='us-east-1')

        # B. INVENTORY (Status = UNKNOWN)
        print("🔍 Collecting Inventory...")
        assets = processor.collect_assets()
        upsert_assets(assets, cloud_account_id)

        # C. RUN CHECKS
        raw_findings_objects = processor.run_s3_checks()

        # D. SERIALIZE & SYNC STATUS (The Fix)
        findings_json = []
        failure_count = 0

        for finding in raw_findings_objects:
            # 1. Prepare for Scan Report
            finding_dict = {
                "control_id": getattr(finding, "control_id", "N/A"),
                "resource": getattr(finding, "resource", "Unknown"),
                "status": getattr(finding, "status", "UNKNOWN"),
                "description": getattr(finding, "description", ""),
                "evidence": getattr(finding, "evidence", {})
            }
            findings_json.append(finding_dict)

            # 2. Count Score
            if finding_dict["status"] in ["FAIL", "ERROR"]:
                failure_count += 1

            # --- THE FIX: Update Inventory Status ---
            # We must reconstruct the ARN because 'finding.resource' is just the name (e.g. "my-bucket")
            # but the DB resourceId is the ARN (e.g. "arn:aws:s3:::my-bucket")
            try:
                resource_name = getattr(finding, "resource", "")
                status = getattr(finding, "status", "UNKNOWN")

                # Only S3 logic for now
                if resource_name:
                    arn = f"arn:aws:s3:::{resource_name}"
                    update_asset_status(cloud_account_id, arn, status)
            except Exception as update_err:
                print(f"⚠️ Could not sync status: {update_err}")
            # ----------------------------------------

        # E. Calculate Score
        total_items = len(findings_json)
        if total_items == 0:
            score = 100
        else:
            score = int(((total_items - failure_count) / total_items) * 100)

        # F. Save Scan Results
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


# ... (The rest of the file: endpoints / download / health_check stay exactly the same)
# Just make sure the @app.post and @app.get parts are still there at the bottom!
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