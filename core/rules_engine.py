from botocore.exceptions import ClientError
from .data_models import EvidenceFinding


class RulesEngine:
    """
    Contains a set of rules to check for SOC 2 compliance evidence in AWS.
    """

    def __init__(self, aws_connector):
        """
        Initializes the RulesEngine with a pre-configured AWSConnector.
        """
        self.connector = aws_connector
        # IMPORTANT: Check if the session is valid before creating clients.
        self.s3_client = None
        if self.connector and self.connector.session:
            self.s3_client = self.connector.session.client('s3')

        print("✅ RulesEngine initialized.")

    def check_s3_public_access_block(self, bucket_name):
        """
        Checks if a specific S3 bucket has the Public Access Block enabled.
        """
        # If the s3_client couldn't be created, we can't run the check.
        if not self.s3_client:
            return EvidenceFinding(
                control_id='CC6.1',
                resource=bucket_name,
                status='ERROR',
                description='Could not run check because the S3 client is not available.',
                evidence={'error': 'Invalid AWS session.'}
            )

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