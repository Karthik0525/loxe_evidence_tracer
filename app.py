# app.py

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

# --- ⬇️ IMPORTANT: REPLACE THESE THREE VALUES ⬇️ ---
YOUR_APP_ACCOUNT_ID = "123456789012" # <-- REPLACE with your 12-digit AWS Account ID.
YOUR_APP_REGION = "us-east-1"      # <-- REPLACE with your AWS region (e.g., us-east-2).
TEMPLATE_S3_URL = "https://your-bucket-name.s3.amazonaws.com/templates/your-template-name.yaml" # <-- REPLACE with your full S3 Object URL.
# --- ⬆️ IMPORTANT: END OF VALUES TO REPLACE ⬆️ ---


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
    elif "123456789012" in YOUR_APP_ACCOUNT_ID or "your-bucket-name" in TEMPLATE_S3_URL:
        st.error("Please replace the placeholder values at the top of the app.py file before running.")
    else:
        with st.spinner("Connecting to your AWS account and running checks... This may take a moment."):
            try:
                # Initialize our backend with the user-provided role
                processor = EvidenceProcessor(
                    role_arn=role_arn_input,
                    external_id=st.session_state.external_id
                )
                findings = processor.run_s3_checks()

                if findings and findings[0].get('status') == 'ERROR':
                     st.error(f"Could not connect to AWS: {findings[0]['description']}")
                elif findings:
                    st.success(f"Success! Found {len(findings)} pieces of S3 evidence.")
                    df = pd.DataFrame(findings)
                    st.dataframe(df)

                    # Provide a download button for the CSV report
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
                else:
                    st.warning("The tracer ran successfully but found no S3 buckets to analyze.")
            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")