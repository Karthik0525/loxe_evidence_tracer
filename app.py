import streamlit as st
import pandas as pd
import uuid
from core.evidence_processor import EvidenceProcessor

# --- App Configuration ---
st.set_page_config(
    page_title="Loxe AI Evidence Tracer",
    page_icon="🛡️",
    layout="centered"
)

YOUR_APP_ACCOUNT_ID = "828750669333"
YOUR_APP_REGION = "us-east-2"
TEMPLATE_S3_URL = "https://loxe-evidence-tracer-testbucket.s3.us-east-2.amazonaws.com/loxe-iam-role-template.yaml"


# --- UI Sections ---
st.title("🛡️ Loxe AI Evidence Tracer")
st.write(
    "Automatically map AWS configurations to SOC 2 controls. "
    "This MVP demo focuses on checking S3 bucket security against control **CC6.1**."
)

st.header("Step 1: Create a Secure Connection")
st.info(
    "To securely scan your AWS account, we use a one-click CloudFormation setup. "
    "This creates a read-only IAM Role in your account that Loxe AI can temporarily use. "
    "We never see or store your secret keys.",
    icon="ℹ️"
)

# Generate a unique External ID for the session and store it.
if 'external_id' not in st.session_state:
    st.session_state.external_id = f"loxe-beta-{uuid.uuid4().hex[:12]}"

st.text_input(
    "Your Unique External ID (auto-generated for this session)",
    value=st.session_state.external_id,
    disabled=True
)

# Construct the Launch Stack URL with the necessary parameters.
launch_stack_url = (
    f"https://console.aws.amazon.com/cloudformation/home?region={YOUR_APP_REGION}#/stacks/create/review"
    f"?templateURL={TEMPLATE_S3_URL}"
    f"&stackName=Loxe-Evidence-Tracer-Role-Stack"
    f"&param_ExternalId={st.session_state.external_id}"
    f"&param_LoxeAppAwsAccountId={YOUR_APP_ACCOUNT_ID}"
)

st.link_button("🚀 Launch AWS CloudFormation Setup", launch_stack_url, type="primary")

st.write("After creating the stack, navigate to the **Outputs** tab in CloudFormation and paste the `RoleArn` below.")
role_arn_input = st.text_input(
    "Paste the Role ARN here:",
    placeholder="arn:aws:iam::CUSTOMER_ACCOUNT_ID:role/Loxe-Evidence-Tracer-Role"
)

st.header("Step 2: Run the Evidence Tracer")
if st.button("🔎 Map Evidence", type="secondary"):
    if not role_arn_input:
        st.error("Please provide the Role ARN from the CloudFormation setup.")
    # ... (rest of your checks) ...
    else:
        progress_bar = st.progress(0, text="Initializing...")
        status_text = st.empty()
        all_findings = []

        try:
            processor = EvidenceProcessor(
                role_arn=role_arn_input,
                external_id=st.session_state.external_id
            )

            # --- CORRECTED LOGIC ---
            # 1. Create the generator object ONCE
            s3_checks_generator = processor.run_s3_checks()

            # 2. Get the first yielded item (the total count)
            total_items, initial_findings = next(s3_checks_generator)

            if initial_findings and initial_findings[0].status == 'ERROR':
                st.error(f"Could not connect to AWS: {initial_findings[0].description}")
                progress_bar.empty()
            elif total_items == 0:
                st.warning("The tracer ran successfully but found no S3 buckets to analyze.")
                progress_bar.empty()
            else:
                # 3. Loop through the REST of the items from the SAME generator
                for i, (_, findings_batch) in enumerate(s3_checks_generator, start=1):
                    if findings_batch:
                        finding = findings_batch[0]
                        all_findings.append(finding)

                        # Update UI in real-time
                        progress_percentage = i / total_items
                        progress_bar.progress(progress_percentage, text=f"Scanning item {i}/{total_items}")
                        status_text.info(f"Checking resource: {finding.resource}...")

                status_text.success("Scan complete!")

                # --- Display Final Results ---
                st.subheader("Compliance Health Score & Report")

                fresh_count = sum(1 for f in all_findings if f.freshness.name == 'FRESH')
                stale_count = sum(1 for f in all_findings if f.freshness.name == 'STALE')

                health_score = (fresh_count / total_items) * 100

                st.metric("Overall Health", f"{health_score:.1f}%")
                col1, col2, col3 = st.columns(3)
                col1.metric("Fresh Evidence", fresh_count)
                col2.metric("Stale Evidence", stale_count)
                col3.metric("Expired Evidence", len(all_findings) - fresh_count - stale_count)

                display_data = [{
                    "control_id": f.control_id, "resource": f.resource, "status": f.status,
                    "description": f.description, "freshness": f.freshness.value,
                    "timestamp": f.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')
                } for f in all_findings]

                df = pd.DataFrame(display_data)
                st.dataframe(df)


                @st.cache_data
                def convert_df_to_csv(df_to_convert):
                    return df_to_convert.to_csv(index=False).encode('utf-8')


                csv = convert_df_to_csv(df)
                st.download_button(
                    label="⬇️ Download Report as CSV",
                    data=csv,
                    file_name="soc2_evidence_report.csv",
                    mime="text/csv",
                )

        except Exception as e:
            st.error(f"An unexpected error occurred: {e}")
            if 'progress_bar' in locals():
                progress_bar.empty()