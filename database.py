import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import json

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# --- THE FIX IS HERE ---
# pool_pre_ping=True tells SQLAlchemy to check the connection before using it.
# pool_recycle=300 refreshes connections every 5 minutes to prevent timeouts.
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=300)


def update_scan_results(scan_id: str, status: str, score: int, findings: dict):
    try:
        with engine.connect() as connection:
            query = text("""
                UPDATE "Scan"
                SET status = :status, score = :score, findings = :findings
                WHERE id = :scan_id
            """)

            # Ensure findings is a JSON string if it isn't already
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
        # We re-raise the error so api.py knows it failed!
        raise e