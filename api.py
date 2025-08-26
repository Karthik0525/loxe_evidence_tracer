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
        role_arn = data['role_arn']
        external_id = data['external_id']
        region = data.get('region', 'us-east-1')  # Get region from request, default to us-east-1

        # Pass the region down to the processor
        processor = EvidenceProcessor(role_arn=role_arn, external_id=external_id, region=region)

        findings_generator = processor.run_s3_checks()
        total_items, initial_findings = next(findings_generator)

        if initial_findings and initial_findings[0].status == 'ERROR':
            return jsonify({"error": initial_findings[0].description}), 400

        # Collect all findings from the generator
        results = [finding_batch[0] for _, finding_batch in findings_generator]

        return jsonify({
            "total_items": total_items,
            "findings": [finding.__dict__ for finding in results]
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)