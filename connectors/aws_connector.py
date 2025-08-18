import boto3
from botocore.exceptions import ClientError


class AWSConnector:
    """A class to handle connections and interactions with AWS by assuming a customer's IAM Role."""

    def __init__(self, role_arn, external_id, region='us-east-1'):
        """
        Initializes the AWSConnector by assuming a role to get temporary credentials.

        :param role_arn: The ARN of the IAM role to assume.
        :param external_id: The unique external ID required to assume the role.
        :param region: The AWS region to operate in.
        """
        self.role_arn = role_arn
        self.external_id = external_id
        self.region_name = region
        self.session = self._create_session()

        if self.session:
            print("✅ AWS session established successfully by assuming role.")
        else:
            print("❌ Failed to establish AWS session.")

    def _create_session(self):
        """Creates a boto3 session using temporary credentials from an assumed role."""
        try:
            sts_client = boto3.client('sts')

            assumed_role_object = sts_client.assume_role(
                RoleArn=self.role_arn,
                RoleSessionName="LoxeEvidenceTracerSession",
                ExternalId=self.external_id
            )

            credentials = assumed_role_object['Credentials']

            return boto3.Session(
                aws_access_key_id=credentials['AccessKeyId'],
                aws_secret_access_key=credentials['SecretAccessKey'],
                aws_session_token=credentials['SessionToken'],
                region_name=self.region_name
            )
        except ClientError as e:
            print(f"❌ Could not assume role. Please check the provided ARN and External ID. Error: {e}")
            return None

    def list_s3_buckets(self):
        """Connects to S3 and lists all buckets using the temporary session."""
        if not self.session:
            return None
        try:
            s3_client = self.session.client('s3')
            response = s3_client.list_buckets()
            buckets = [bucket['Name'] for bucket in response['Buckets']]
            print("Successfully retrieved S3 buckets.")
            return buckets
        except ClientError as e:
            print(f"❌ An unexpected error occurred while listing buckets: {e}")
            return None