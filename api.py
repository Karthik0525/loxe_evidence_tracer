# api.py
from flask import Flask, request, jsonify
from flask_cors import CORS

from core.evidence_processor import EvidenceProcessor

app = Flask(__name__)
CORS(app)


@app.route('/scan', methods=['POST'])
def perform_scan():
    """This function is called when a request is sent to our API."""
    try:
        data = request.json
        role_arn = data['role_arn']
        external_id = data['external_id']

        processor = EvidenceProcessor(role_arn=role_arn, external_id=external_id)
        findings = processor.run_s3_checks()


        total_items, _ = next(findings)
        results = [finding[1][0].__dict__ for finding in findings]

        return jsonify({
            "total_items": total_items,
            "findings": results
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)