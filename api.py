from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from connectors.aws_connector import AWSConnector
from database import update_scan_results  # <-- Import the new tool

app = FastAPI()


class ScanRequest(BaseModel):
    cloud_account_id: str
    role_arn: str
    scan_id: str


def run_background_scan(role_arn: str, scan_id: str, cloud_account_id: str):
    print(f"🚀 Starting scan for {scan_id}...")

    try:
        # 1. Initialize AWS Connector
        aws = AWSConnector(role_arn=role_arn)

        # 2. Run the Real Scan (Your existing logic)
        # Assuming aws.scan_all() returns a dict of failures/passes
        raw_results = aws.scan_all()

        # 3. Calculate a Score (Simple math for now)
        # e.g., Start at 100, subtract 5 for every failure
        total_failures = len(raw_results.get("failures", []))
        score = max(0, 100 - (total_failures * 5))

        # 4. Save to Vercel Database
        update_scan_results(
            scan_id=scan_id,
            status="COMPLETED",
            score=score,
            findings=raw_results
        )

    except Exception as e:
        print(f"💥 Scan failed: {e}")
        # Mark as failed in DB so the user knows
        update_scan_results(scan_id, "FAILED", 0, {"error": str(e)})


@app.post("/scan")
async def start_scan(request: ScanRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(
        run_background_scan,
        request.role_arn,
        request.scan_id,
        request.cloud_account_id
    )
    return {"status": "Scan started", "scan_id": request.scan_id}