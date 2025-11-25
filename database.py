import os
from sqlalchemy import create_engine, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import URL
from dotenv import load_dotenv
import json

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Connect with auto-reconnect settings
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=300)


def upsert_assets(assets: list, cloud_account_id: str):
    """
    Bulk inserts or updates assets in the Postgres 'Asset' table.
    """
    if not assets:
        return

    # Prepare data for SQLAlchemy
    # We inject the cloudAccountId and ensure metadata is JSON stringified
    records = []
    for asset in assets:
        record = asset.copy()
        record['cloudAccountId'] = cloud_account_id
        # Ensure metadata is valid JSON
        if isinstance(record.get('metadata'), dict):
            record['metadata'] = json.dumps(record['metadata'], default=str)
        records.append(record)

    try:
        with engine.connect() as conn:
            # Define the table structure roughly for the statement
            # We use raw SQL table name "Asset"
            from sqlalchemy import Table, MetaData, Column, String, DateTime, JSON
            metadata_obj = MetaData()
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

            # Construct the Upsert Statement
            stmt = insert(asset_table).values(records)

            # Define what to do on conflict (Upsert logic)
            # We match on the unique constraint [cloudAccountId, resourceId]
            # We update everything except the ID
            update_dict = {
                col.name: col
                for col in stmt.excluded
                if col.name not in ['id', 'resourceId', 'cloudAccountId']
            }

            # Execute the upsert
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