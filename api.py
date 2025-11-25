from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
import os

# --- LOCAL IMPORTS ---
# These import your custom code from the other files in your project
from connectors.aws_connector import AWSConnector
from database import update_scan_results

app = FastAPI()


# 1. Request Model (Updated with external_id)
class ScanRequest(BaseModel):
    cloud_account_id: str
    role_arn: str
    scan_id: str
    external_id: str  # <-- This is the new field we added


# 2. Background Task Function
def run_background_scan(role_arn: str, scan_id: str, cloud_account_id: str, external_id: str):
    print(f"🚀 Starting scan for {scan_id}...")

    try:
        # Initialize the AWS Connector using the ID passed from Next.js
        aws = AWSConnector(role_arn=role_arn, external_id=external_id)

        # Run the Real Scan logic
        # (This calls your existing scanning engine)
        raw_results = aws.scan_all()

        # Calculate a Score (Simple math for now)
        # e.g., Start at 100, subtract 5 for every failure found
        total_failures = len(raw_results.get("failures", []))
        score = max(0, 100 - (total_failures * 5))

        # Save the results to the Vercel Database
        update_scan_results(
            scan_id=scan_id,
            status="COMPLETED",
            score=score,
            findings=raw_results
        )
        print(f"✅ Scan {scan_id} finished and saved.")

    except Exception as e:
        print(f"💥 Scan failed: {e}")
        # Update DB with failure status so the UI doesn't hang forever
        update_scan_results(scan_id, "FAILED", 0, {"error": str(e)})


# 3. The API Endpoint
@app.post("/scan")
async def start_scan(request: ScanRequest, background_tasks: BackgroundTasks):
    # Add the heavy lifting to the background queue
    background_tasks.add_task(
        run_background_scan,
        request.role_arn,
        request.scan_id,
        request.cloud_account_id,
        request.external_id  # <-- Pass the ID along to the background function
    )
    return {"status": "Scan started", "scan_id": request.scan_id}


@app.get("/")
def health_check():
    return {"status": "Loxe Engine is Online"}