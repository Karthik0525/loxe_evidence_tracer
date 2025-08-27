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
        findings = processor.run_s3_checks()  # This now returns a simple list

        # Check if the only result is an error from the processor
        if findings and findings[0].status == 'ERROR':
            return jsonify({"error": findings[0].description}), 400

        # Convert the list of dataclass objects to a list of dictionaries for the JSON response
        return jsonify({"findings": [finding.__dict__ for finding in findings]})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)