import os
import uuid  # <-- Import UUID
from sqlalchemy import create_engine, text
from sqlalchemy.dialects.postgresql import insert
from dotenv import load_dotenv
import json

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=300)


def upsert_assets(assets: list, cloud_account_id: str):
    if not assets:
        return

    records = []
    for asset in assets:
        record = asset.copy()
        record['cloudAccountId'] = cloud_account_id

        # --- THE FIX: Generate ID manually ---
        # We generate a unique ID for every row (used only on insert)
        # Postgres ignores this on update conflicts anyway.
        record['id'] = f"asset_{uuid.uuid4().hex}"
        # -------------------------------------

        if isinstance(record.get('metadata'), dict):
            record['metadata'] = json.dumps(record['metadata'], default=str)
        records.append(record)

    try:
        with engine.connect() as conn:
            from sqlalchemy import Table, MetaData, Column, String, DateTime, JSON
            metadata_obj = MetaData()

            # We MUST include the 'id' column in the table definition now
            asset_table = Table('Asset', metadata_obj,
                                Column('id', String, primary_key=True),
                                Column('resourceId', String),
                                Column('cloudAccountId', String),
                                Column('name', String),
                                Column('type', String),
                                Column('provider', String),
                                Column('region', String),
                                Column('status', String),
                                Column('metadata', JSON),
                                Column('updatedAt', DateTime)
                                )

            # We pass the full record (INCLUDING 'id') to the insert statement
            stmt = insert(asset_table).values(records)

            update_dict = {
                col.name: col
                for col in stmt.excluded
                if col.name not in ['id', 'resourceId', 'cloudAccountId']
            }

            on_conflict_stmt = stmt.on_conflict_do_update(
                index_elements=['cloudAccountId', 'resourceId'],
                set_=update_dict
            )

            conn.execute(on_conflict_stmt)
            conn.commit()
            print(f"✅ Successfully upserted {len(records)} assets.")

    except Exception as e:
        print(f"❌ Failed to upsert assets: {e}")
        raise e

def update_scan_results(scan_id: str, status: str, score: int, findings: dict):
    try:
        with engine.connect() as connection:
            query = text("""
                UPDATE "Scan"
                SET status = :status, score = :score, findings = :findings
                WHERE id = :scan_id
            """)

            findings_json = json.dumps(findings) if isinstance(findings, dict) else findings

            connection.execute(query, {
                "status": status,
                "score": score,
                "findings": findings_json,
                "scan_id": scan_id
            })

            connection.commit()
            print(f"✅ Successfully saved results for Scan {scan_id}")

    except Exception as e:
        print(f"❌ Failed to save to DB: {e}")
        raise e


def update_asset_status(cloud_account_id: str, resource_id: str, status: str):
    """
    Updates the status of a specific asset.
    """
    try:
        with engine.connect() as connection:
            query = text("""
                UPDATE "Asset"
                SET status = :status
                WHERE "cloudAccountId" = :cloud_account_id 
                AND "resourceId" = :resource_id
            """)

            connection.execute(query, {
                "status": status,
                "cloud_account_id": cloud_account_id,
                "resource_id": resource_id
            })
            connection.commit()

    except Exception as e:
        print(f"⚠️ Failed to update asset status for {resource_id}: {e}")


def get_asset_map(cloud_account_id: str):
    """
    Returns a dictionary mapping Resource IDs (ARNs) to Internal Database IDs.
    Example: {'arn:aws:s3:::my-bucket': 'asset_12345uuid'}
    """
    asset_map = {}
    try:
        with engine.connect() as conn:
            # Fetch only the ID and resourceId for this account
            query = text('SELECT id, "resourceId" FROM "Asset" WHERE "cloudAccountId" = :id')
            result = conn.execute(query, {"id": cloud_account_id})

            for row in result:
                # row[0] is id, row[1] is resourceId
                asset_map[row[1]] = row[0]

        return asset_map
    except Exception as e:
        print(f"⚠️ Failed to fetch asset map: {e}")
        return {}


def insert_findings_bulk(findings_data: list):
    """
    Bulk inserts finding records into the Finding table.
    """
    if not findings_data:
        return

    try:
        with engine.connect() as conn:
            from sqlalchemy import Table, MetaData, Column, String, DateTime
            metadata_obj = MetaData()

            finding_table = Table('Finding', metadata_obj,
                                  Column('id', String, primary_key=True),
                                  Column('controlId', String),
                                  Column('status', String),
                                  Column('description', String),
                                  Column('severity', String),
                                  Column('assetId', String),
                                  Column('scanId', String),
                                  Column('updatedAt', DateTime)
                                  )

            # Use generic insert
            stmt = insert(finding_table).values(findings_data)

            # Execute
            conn.execute(stmt)
            conn.commit()
            print(f"✅ Successfully inserted {len(findings_data)} finding records.")

    except Exception as e:
        print(f"❌ Failed to insert findings: {e}")
        # Don't raise, we don't want to crash the whole scan if just the details fail


def clear_asset_findings(asset_ids: list):
    """
    Deletes all existing findings for the given list of Asset IDs.
    This ensures we don't have duplicate/stale findings from previous scans.
    """
    if not asset_ids:
        return
    try:
        with engine.connect() as connection:
            # Postgres syntax for "Delete where ID is in this list"
            query = text('DELETE FROM "Finding" WHERE "assetId" = ANY(:ids)')
            connection.execute(query, {"ids": asset_ids})
            connection.commit()
            print(f"🧹 Cleared old findings for {len(asset_ids)} assets.")

    except Exception as e:
        print(f"⚠️ Failed to clear old findings: {e}")