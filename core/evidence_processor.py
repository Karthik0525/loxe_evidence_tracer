from connectors.aws_connector import AWSConnector
from .rules_engine import RulesEngine


class EvidenceProcessor:
    """Orchestrates the process of gathering evidence using a specific client-provided role."""

    def __init__(self, role_arn, external_id):
        """
        Initializes the processor by creating connector and engine instances.

        :param role_arn: The ARN of the client's IAM role.
        :param external_id: The unique external ID for the session.
        """
        self.connector = AWSConnector(role_arn=role_arn, external_id=external_id)

        self.rules_engine = RulesEngine(self.connector)
        print("✅ EvidenceProcessor initialized.")

    def run_s3_checks(self):
        """
        Runs all S3-related checks and collects the evidence.
        """
        all_findings = []

        if not self.connector.session:
            print("❌ Cannot run checks because AWS session was not established.")
            error_finding = {
                'control_id': 'N/A',
                'resource': self.connector.role_arn,
                'status': 'ERROR',
                'description': 'Failed to assume the provided IAM Role. Check the Role ARN and External ID.',
                'evidence': {}
            }
            return [error_finding]

        s3_buckets = self.connector.list_s3_buckets()

        if s3_buckets is None:
            return []

        print(f"\n🔎 Found {len(s3_buckets)} S3 buckets. Running checks...")

        for bucket in s3_buckets:
            finding = self.rules_engine.check_s3_public_access_block(bucket)
            all_findings.append(finding)

        print("✅ S3 checks complete.")
        return all_findings