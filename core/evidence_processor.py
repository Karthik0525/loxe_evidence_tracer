# core/evidence_processor.py

from connectors.aws_connector import AWSConnector
from .rules_engine import RulesEngine
from .data_models import EvidenceFinding


class EvidenceProcessor:
    def __init__(self, role_arn, external_id, region):
        self.connector = AWSConnector(role_arn=role_arn, external_id=external_id, region=region)
        self.rules_engine = RulesEngine(self.connector)
        print("✅ EvidenceProcessor initialized.")

    def run_s3_checks(self):
        """
        Runs all S3 checks and returns a complete list of findings.
        """
        if not self.connector.session:
            return [EvidenceFinding(
                control_id='N/A', resource=self.connector.role_arn, status='ERROR',
                description='Failed to assume IAM Role. Check ARN, External ID, and Region.', evidence={}
            )]

        s3_buckets = self.connector.list_s3_buckets()
        if s3_buckets is None:
            # An error occurred in the connector, which already printed a message.
            return []
        if not s3_buckets:
            # It's not an error, there are just no buckets. Return an empty list.
            return []

        all_findings = []
        for bucket in s3_buckets:
            finding = self.rules_engine.check_s3_public_access_block(bucket)
            all_findings.append(finding)

        print(f"✅ S3 checks complete. Found {len(all_findings)} items.")
        return all_findings