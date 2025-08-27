# connectors/aws_connector.py

import boto3
from botocore.exceptions import ClientError


class AWSConnector:
    def __init__(self, role_arn, external_id, region='us-east-1'):
        self.role_arn = role_arn
        self.external_id = external_id
        self.region_name = region
        self.session = self._create_session()

        if self.session:
            print(f"✅ AWS session established successfully in region '{self.region_name}'.")

    def _create_session(self):
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
            # --- NEW: Granular Error Analysis ---
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']

            if error_code == 'AccessDenied':
                if 'ExternalId' in error_message:
                    # This is the most common error we expect to see
                    raise ValueError(
                        "The External ID is incorrect. Please refresh the page to generate a new ID and try the setup process again.")
                else:
                    # This error means the loxe-app-backend-user is misconfigured
                    raise ValueError("Access Denied. Please check the permissions of the application's backend user.")
            elif error_code == 'ValidationError':
                # This error means the ARN is formatted incorrectly
                raise ValueError(
                    "The Role ARN format is invalid. Please copy it again from the CloudFormation Outputs tab.")
            else:
                # Catch any other AWS errors
                raise ValueError(f"An unexpected AWS error occurred: {error_message}")
        except Exception as e:
            # Catch non-AWS errors
            raise ValueError(f"An unexpected error occurred: {e}")

    def list_s3_buckets(self):
        if not self.session:
            # This will now be caught by the processor
            raise ConnectionError("Cannot list S3 buckets because the AWS session was not established.")
        try:
            s3_client = self.session.client('s3')
            response = s3_client.list_buckets()
            return [bucket['Name'] for bucket in response['Buckets']]
        except ClientError as e:
            raise ConnectionError(f"An AWS error occurred while listing buckets: {e.response['Error']['Message']}")