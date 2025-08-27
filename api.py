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

        # The processor will now raise a specific error if connection fails
        processor = EvidenceProcessor(role_arn=role_arn, external_id=external_id, region=region)
        findings = processor.run_s3_checks()

        return jsonify({"findings": [finding.__dict__ for finding in findings]})

    # Catch the specific ValueError from our connector, or any other exception
    except (ValueError, ConnectionError, Exception) as e:
        # Return the specific, user-friendly error message
        return jsonify({"error": str(e)}), 400


if __name__ == '__main__':
    app.run(debug=True, port=5000)