from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import os
import json
import io

# --- LOCAL IMPORTS ---
from core.evidence_processor import EvidenceProcessor
from database import update_scan_results, engine, text
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

    # Sanitize inputs (remove trailing spaces from copy-pasting)
    role_arn = role_arn.strip()
    external_id = external_id.strip()

    try:
        # A. Initialize the Processor
        # We default to us-east-1 for initial connection
        processor = EvidenceProcessor(role_arn=role_arn, external_id=external_id, region='us-east-1')

        # B. Run the Checks
        raw_findings_objects = processor.run_s3_checks()

        # C. Serialize Data (CRITICAL STEP)
        # Convert Python Objects (EvidenceFinding) into simple Dictionaries (JSON)
        # so they can be saved to the Postgres database.
        findings_json = []
        failure_count = 0

        for finding in raw_findings_objects:
            # Extract attributes safely
            finding_dict = {
                "control_id": getattr(finding, "control_id", "N/A"),
                "resource": getattr(finding, "resource", "Unknown"),
                "status": getattr(finding, "status", "UNKNOWN"),
                "description": getattr(finding, "description", ""),
                "evidence": getattr(finding, "evidence", {})
            }
            findings_json.append(finding_dict)

            # Count failures for the score
            if finding_dict["status"] == "FAIL" or finding_dict["status"] == "ERROR":
                failure_count += 1

        # D. Calculate Score
        total_items = len(findings_json)
        if total_items == 0:
            score = 100  # Default to 100 if nothing found
        else:
            # Percentage of passed checks
            score = int(((total_items - failure_count) / total_items) * 100)

        # E. Save to Vercel Database
        update_scan_results(
            scan_id=scan_id,
            status="COMPLETED",
            score=score,
            findings={"results": findings_json}
        )
        print(f"✅ Scan {scan_id} finished. Score: {score}")

    except Exception as e:
        print(f"💥 Scan failed: {e}")
        # Update DB with failure status
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


# 4. The Download Endpoint
@app.get("/download/{scan_id}")
def download_report(scan_id: str):
    # Fetch from DB
    with engine.connect() as conn:
        result = conn.execute(
            text('SELECT findings FROM "Scan" WHERE id = :id'),
            {"id": scan_id}
        ).fetchone()

    if not result or not result[0]:
        return {"error": "Scan not found or no data available"}

    # Parse JSON
    data = result[0]
    if isinstance(data, str):
        data = json.loads(data)

    findings_list = data.get("results", [])

    # Use your report generator to create CSV string
    csv_content = generate_csv_string(findings_list)

    # Stream back to user
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=scan_report_{scan_id}.csv"}
    )


@app.get("/")
def health_check():
    return {"status": "Loxe Engine is Online"}