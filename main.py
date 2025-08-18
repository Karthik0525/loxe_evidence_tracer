import json
from core.evidence_processor import EvidenceProcessor
from reporting.report_generator import generate_csv_report


def main():
    """
    The main entry point for the SOC 2 Evidence Tracer application.
    """
    print("🚀 Starting Loxe AI Evidence Tracer...")

    try:
        processor = EvidenceProcessor()
        s3_findings = processor.run_s3_checks()
        all_findings = s3_findings

        if all_findings:
            print("\n--- Final Evidence Report ---")
            print(json.dumps(all_findings, indent=2))
            print("--- End of Report ---")

            generate_csv_report(all_findings)

        else:
            print("\nNo evidence was collected.")

    except Exception as e:
        print(f"❌ An unexpected error occurred during the run: {e}")


if __name__ == "__main__":
    main()