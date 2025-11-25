import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import json

# Load the secret key
load_dotenv()

# Get the URL (and fix a small Vercel quirk where it starts with postgres:// instead of postgresql://)
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Create the engine
engine = create_engine(DATABASE_URL)


def update_scan_results(scan_id: str, status: str, score: int, findings: dict):
    """
    Updates the Scan row in Postgres with the results from Python.
    """
    try:
        with engine.connect() as connection:
            # We use a raw SQL query to update the specific scan
            # We convert the findings dict to a JSON string
            query = text("""
                UPDATE "Scan"
                SET status = :status, score = :score, findings = :findings
                WHERE id = :scan_id
            """)

            connection.execute(query, {
                "status": status,
                "score": score,
                "findings": json.dumps(findings),
                "scan_id": scan_id
            })

            connection.commit()
            print(f"✅ Successfully saved results for Scan {scan_id}")

    except Exception as e:
        print(f"❌ Failed to save to DB: {e}")