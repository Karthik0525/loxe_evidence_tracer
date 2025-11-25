from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
import os

# --- LOCAL IMPORTS ---
# We import the processor, not the connector, because the processor manages the connector
from core.evidence_processor import EvidenceProcessor
from database import update_scan_results

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

    role_arn = role_arn.strip()
    external_id = external_id.strip()

    try:
        # A. Initialize the Processor
        # Your EvidenceProcessor class expects (role_arn, external_id, region)
        # We default to us-east-1 for now to match your connector default
        processor = EvidenceProcessor(role_arn=role_arn, external_id=external_id, region='us-east-1')

        # B. Run the Checks
        # This calls the method you showed me in evidence_processor.py
        raw_findings_objects = processor.run_s3_checks()

        # C. Serialize Data (CRITICAL STEP)
        # We must convert your Python Objects (EvidenceFinding) into simple Dictionaries (JSON)
        # so they can be saved to the Postgres database.
        findings_json = []
        failure_count = 0

        for finding in raw_findings_objects:
            # Extract attributes from the EvidenceFinding object
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
            score = 100  # Default to 100 if no buckets found (nothing insecure)
        else:
            # Percentage of passed checks
            score = int(((total_items - failure_count) / total_items) * 100)

        # E. Save to Vercel Database
        update_scan_results(
            scan_id=scan_id,
            status="COMPLETED",
            score=score,
            findings={"results": findings_json}  # Wrap list in a dict for JSON storage
        )
        print(f"✅ Scan {scan_id} finished. Score: {score}")

    except Exception as e:
        print(f"💥 Scan failed: {e}")
        # Update DB with failure status so the UI doesn't hang
        update_scan_results(scan_id, "FAILED", 0, {"error": str(e)})


# 3. The API Endpoint
@app.post("/scan")
async def start_scan(request: ScanRequest, background_tasks: BackgroundTasks):
    # Add to background queue
    background_tasks.add_task(
        run_background_scan,
        request.role_arn,
        request.scan_id,
        request.cloud_account_id,
        request.external_id
    )
    return {"status": "Scan started", "scan_id": request.scan_id}


@app.get("/")
def health_check():
    return {"status": "Loxe Engine is Online"}