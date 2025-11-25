from connectors.aws_connector import AWSConnector
from .rules_engine import RulesEngine
from .data_models import EvidenceFinding
from datetime import datetime


class EvidenceProcessor:
    def __init__(self, role_arn, external_id, region):
        self.connector = AWSConnector(role_arn=role_arn, external_id=external_id, region=region)
        self.rules_engine = RulesEngine(self.connector)
        print("✅ EvidenceProcessor initialized.")

    def collect_assets(self):
        """
        Scans the environment to build a complete Inventory of assets.
        Returns a list of dictionaries ready for the 'Asset' DB table.
        """
        if not self.connector.session:
            return []

        assets = []
        s3_client = self.connector.session.client('s3')

        try:
            # List all buckets
            response = s3_client.list_buckets()
            for bucket in response.get('Buckets', []):
                name = bucket['Name']
                creation_date = bucket['CreationDate']

                # Get Region (Crucial for Context)
                # API quirk: us-east-1 often returns None
                try:
                    loc_resp = s3_client.get_bucket_location(Bucket=name)
                    region = loc_resp.get('LocationConstraint') or 'us-east-1'
                except:
                    region = 'unknown'

                # Construct the Asset Dictionary
                asset = {
                    "name": name,
                    "resourceId": f"arn:aws:s3:::{name}",  # Unique ID
                    "type": "AWS::S3::Bucket",
                    "provider": "AWS",
                    "region": region,
                    "status": "UNKNOWN",  # Will be updated by the scan later
                    "metadata": {
                        "creation_date": creation_date.isoformat(),
                        "owner_id": response.get('Owner', {}).get('ID')
                    },
                    "updatedAt": datetime.now()
                }
                assets.append(asset)

        except Exception as e:
            print(f"⚠️ Error collecting assets: {e}")

        print(f"✅ Collected {len(assets)} assets for inventory.")
        return assets

    def run_s3_checks(self):
        """
        Runs all S3 checks and returns findings.
        """
        if not self.connector.session:
            return []  # Return empty list on connection failure

        # We use the connector's list method or the one we just built
        # For simplicity, let's use the connector's existing method
        try:
            s3_buckets = self.connector.list_s3_buckets()
        except:
            return []

        if not s3_buckets:
            return []

        all_findings = []
        for bucket in s3_buckets:
            finding = self.rules_engine.check_s3_public_access_block(bucket)
            all_findings.append(finding)

        print(f"✅ S3 checks complete. Found {len(all_findings)} items.")
        return all_findings