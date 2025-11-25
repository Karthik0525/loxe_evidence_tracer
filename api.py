from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import os
import json
import io
import uuid
from datetime import datetime

# --- UPDATED IMPORTS ---
from core.evidence_processor import EvidenceProcessor
from database import update_scan_results, upsert_assets, update_asset_status, get_asset_map, insert_findings_bulk, engine, \
    text, clear_asset_findings
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

        # B. INVENTORY
        print("🔍 Collecting Inventory...")
        assets = processor.collect_assets()
        upsert_assets(assets, cloud_account_id)

        # Get the Map (ARN -> DB_ID)
        asset_map = get_asset_map(cloud_account_id)

        # --- THE FIX: Clear Old Data ---
        # 1. Identify all assets we are about to check
        all_scanned_asset_ids = list(asset_map.values())

        # 2. Wipe their finding history so we start fresh
        if all_scanned_asset_ids:
            clear_asset_findings(all_scanned_asset_ids)
        # -------------------------------

        # C. RUN CHECKS
        raw_findings_objects = processor.run_s3_checks()

        # D. PROCESS FINDINGS
        findings_json = []
        finding_records = []
        failure_count = 0

        for finding in raw_findings_objects:
            # ... (Everything inside this loop stays EXACTLY the same) ...
            # ... Extract Data ...
            f_control = getattr(finding, "control_id", "N/A")
            f_resource_name = getattr(finding, "resource", "Unknown")
            f_status = getattr(finding, "status", "UNKNOWN")
            f_desc = getattr(finding, "description", "")
            f_evidence = getattr(finding, "evidence", {})

            finding_dict = {
                "control_id": f_control,
                "resource": f_resource_name,
                "status": f_status,
                "description": f_desc,
                "evidence": f_evidence
            }
            findings_json.append(finding_dict)

            if f_status in ["FAIL", "ERROR"]:
                failure_count += 1

            if f_resource_name:
                arn = f"arn:aws:s3:::{f_resource_name}"
                update_asset_status(cloud_account_id, arn, f_status)

                db_asset_id = asset_map.get(arn)

                if db_asset_id and f_status == "FAIL":
                    finding_records.append({
                        "id": f"find_{uuid.uuid4().hex}",
                        "controlId": f_control,
                        "status": f_status,
                        "description": f_desc,
                        "severity": "HIGH",
                        "assetId": db_asset_id,
                        "scanId": scan_id,
                        "updatedAt": datetime.now()
                    })

        # E. Save Finding Records
        if finding_records:
            insert_findings_bulk(finding_records)

        # ... (Calculate Score and Save Results logic stays same) ...
        total_items = len(findings_json)
        if total_items == 0:
            score = 100
        else:
            score = int(((total_items - failure_count) / total_items) * 100)

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