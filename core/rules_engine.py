from botocore.exceptions import ClientError
from .data_models import EvidenceFinding

class RulesEngine:
    """
    Contains a set of rules to check for SOC 2 compliance evidence in AWS.
    """

    def __init__(self, aws_connector):
        """
        Initializes the RulesEngine with a pre-configured AWSConnector.

        :param aws_connector: An instance of the AWSConnector class.
        """
        self.connector = aws_connector
        self.s3_client = self.connector.session.client('s3')
        print("✅ RulesEngine initialized.")

    def check_s3_public_access_block(self, bucket_name):
        """
        Checks if a specific S3 bucket has the Public Access Block enabled.
        This is a common requirement for SOC 2 CC6.1.

        :param bucket_name: The name of the S3 bucket to check.
        :return: An EvidenceFinding dataclass object.
        """
        status = ''
        description = ''
        evidence_details = {}

        try:
            pab_config = self.s3_client.get_public_access_block(Bucket=bucket_name)
            config = pab_config.get('PublicAccessBlockConfiguration', {})

            is_compliant = all([
                config.get('BlockPublicAcls', False),
                config.get('IgnorePublicAcls', False),
                config.get('BlockPublicPolicy', False),
                config.get('RestrictPublicBuckets', False)
            ])

            if is_compliant:
                status = 'PASS'
                description = 'S3 bucket Public Access Block is enabled.'
            else:
                status = 'FAIL'
                description = 'S3 bucket Public Access Block is not fully enabled.'

            evidence_details = config

        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchPublicAccessBlockConfiguration':
                status = 'FAIL'
                description = 'S3 bucket does not have a Public Access Block configured.'
                evidence_details = {'error': 'NoSuchPublicAccessBlockConfiguration'}
            else:
                status = 'ERROR'
                description = f"Could not check bucket '{bucket_name}'."
                evidence_details = {'error': str(e)}

        return EvidenceFinding(
            control_id='CC6.1',
            resource=bucket_name,
            status=status,
            description=description,
            evidence=evidence_details
        )


if __name__ == "__main__":
    print("RulesEngine defined. Ready to be used by the Evidence Processor.")