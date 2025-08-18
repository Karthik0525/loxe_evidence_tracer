import pandas as pd
import os
from datetime import datetime

def generate_csv_report(findings_list):
    """
    Takes a list of evidence findings (dictionaries) and saves them to a CSV file.

    :param findings_list: A list of finding dictionaries.
    """
    if not findings_list:
        print("No findings to generate a report for.")
        return

    df = pd.DataFrame(findings_list)

    report_columns = ['control_id', 'status', 'resource', 'description']
    df = df.reindex(columns=report_columns)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"soc2_evidence_report_{timestamp}.csv"

    try:
        df.to_csv(filename, index=False)
        print(f"\n✅ Successfully generated report: {os.path.abspath(filename)}")
    except Exception as e:
        print(f"❌ Failed to generate report: {e}")