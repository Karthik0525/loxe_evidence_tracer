# api.py
from flask import Flask, request, jsonify
from flask_cors import CORS
from core.evidence_processor import EvidenceProcessor

app = Flask(__name__)
CORS(app)


@app.route('/scan', methods=['POST'])
def perform_scan():
    try:
        data = request.json
        role_arn = data.get('role_arn')
        external_id = data.get('external_id')
        region = data.get('region', 'us-east-2')

        if not role_arn or not external_id:
            return jsonify({"error": "role_arn and external_id are required."}), 400

        processor = EvidenceProcessor(role_arn=role_arn, external_id=external_id, region=region)
        findings = processor.run_s3_checks()

        if findings and findings[0].status == 'ERROR':
            return jsonify({"error": findings[0].description}), 400

        # --- NEW: Manually build the dictionary for the response ---
        results = []
        for finding in findings:
            # Create a dictionary from our dataclass object
            finding_dict = finding.__dict__
            # Convert the FreshnessStatus Enum object to its string name (e.g., "FRESH")
            finding_dict['freshness'] = finding.freshness.name
            results.append(finding_dict)

        return jsonify({"findings": results})

    except (ValueError, ConnectionError, Exception) as e:
        return jsonify({"error": str(e)}), 400


if __name__ == '__main__':
    app.run(debug=True, port=5000)