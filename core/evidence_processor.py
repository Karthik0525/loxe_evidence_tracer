from connectors.aws_connector import AWSConnector
from .rules_engine import RulesEngine
from .data_models import EvidenceFinding


class EvidenceProcessor:
    """Orchestrates the process of gathering evidence using a specific client-provided role."""

    # The __init__ method now also accepts the 'region' parameter.
    def __init__(self, role_arn, external_id, region):
        """
        Initializes the processor by creating connector and engine instances.

        :param role_arn: The ARN of the client's IAM role.
        :param external_id: The unique external ID for the session.
        :param region: The AWS region to scan.
        """
        # The region is now passed down to the AWSConnector when it's created.
        self.connector = AWSConnector(role_arn=role_arn, external_id=external_id, region=region)

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
                description='Failed to assume the provided IAM Role. Check credentials and permissions.',
                evidence={}
            )
            yield 1, [error_finding]
            return

        s3_buckets = self.connector.list_s3_buckets()
        if s3_buckets is None:
            yield 0, []
            return

        total_buckets = len(s3_buckets)
        yield total_buckets, None

        for bucket in s3_buckets:
            finding = self.rules_engine.check_s3_public_access_block(bucket)
            yield None, [finding]

        print("✅ S3 checks complete.")