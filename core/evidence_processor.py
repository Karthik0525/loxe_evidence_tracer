from connectors.aws_connector import AWSConnector
from .rules_engine import RulesEngine
from .data_models import EvidenceFinding  # Make sure this import is here


class EvidenceProcessor:
    """Orchestrates the process of gathering evidence using a specific client-provided role."""

    def __init__(self, role_arn, external_id):
        self.connector = AWSConnector(role_arn=role_arn, external_id=external_id)
        self.rules_engine = RulesEngine(self.connector)
        print("✅ EvidenceProcessor initialized.")

    def run_s3_checks(self):
        """
        Runs all S3-related checks and YIELDS each finding as it's completed.
        This is a generator function.
        """
        if not self.connector.session:
            error_finding = EvidenceFinding(
                control_id='N/A',
                resource=self.connector.role_arn,
                status='ERROR',
                description='Failed to assume the provided IAM Role. Check the Role ARN and External ID.',
                evidence={}
            )
            yield 1, [error_finding]  # Yield total and the error
            return

        s3_buckets = self.connector.list_s3_buckets()
        if s3_buckets is None:
            yield 0, []  # Yield zero total and empty list
            return

        total_buckets = len(s3_buckets)
        print(f"\n🔎 Found {total_buckets} S3 buckets. Starting scan...")

        # First, yield the total number of items to scan
        yield total_buckets, None

        # Next, loop through and yield each finding one by one
        for bucket in s3_buckets:
            finding = self.rules_engine.check_s3_public_access_block(bucket)
            yield None, [finding]  # Yield a list containing one finding

        print("✅ S3 checks complete.")