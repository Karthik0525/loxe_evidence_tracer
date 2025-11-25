import pandas as pd
import io


def generate_csv_string(findings_list):
    """
    Takes a list of evidence findings and returns a CSV string
    instead of saving to a file.
    """
    if not findings_list:
        return ""

    # Create the DataFrame
    df = pd.DataFrame(findings_list)

    # Select and Reorder columns (Handle cases where columns might be missing)
    report_columns = ['control_id', 'status', 'resource', 'description']

    # Ensure all columns exist, fill with N/A if missing
    for col in report_columns:
        if col not in df.columns:
            df[col] = 'N/A'

    df = df.reindex(columns=report_columns)

    # Write to a memory buffer instead of a hard drive file
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)

    # Return the text content of the CSV
    return csv_buffer.getvalue()