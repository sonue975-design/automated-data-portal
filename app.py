from io import BytesIO
from datetime import date, datetime

import gspread
import pandas as pd
import streamlit as st

MAX_FILE_SIZE_MB = 10

st.set_page_config(
    page_title="Automated Data Entry & Cleaning Portal",
    page_icon="🤖",
    layout="wide",
)

st.title("🤖 Automated Data Cleaning & Entry Portal")
st.markdown(
    "Upload an Excel or CSV file to clean, format, analyze, and optionally "
    "sync its rows to a configured Google Sheet."
)
st.markdown("---")
st.info(
    "🔒 Uploaded files are processed in app memory. Google Sheets sync is "
    "optional and only happens when you click the sync button. Review your "
    "hosting provider's privacy and data-retention policies before uploading "
    "sensitive information."
)


def get_sheet_configuration():
    """Return configured Google Sheets client and worksheet, if available."""
    try:
        credentials = dict(st.secrets["gcp_service_account"])
        spreadsheet_id = st.secrets["spreadsheet_id"]
        worksheet_name = st.secrets.get("worksheet_name", "Sheet1")
    except (KeyError, AttributeError):
        return None, None, "Google Sheets is not configured in app secrets."

    try:
        client = gspread.service_account_from_dict(credentials)
        worksheet = client.open_by_key(spreadsheet_id).worksheet(worksheet_name)
        return client, worksheet, None
    except Exception:
        return None, None, (
            "Could not connect to the configured Google Sheet. Check the app "
            "secrets, sheet ID, worksheet name, and service-account access."
        )


def to_sheet_value(value):
    """Convert pandas and Python values to safe Google Sheets cell values."""
    if pd.isna(value):
        return ""
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()
    if hasattr(value, "item"):
        value = value.item()
    return value if isinstance(value, (str, int, float, bool)) else str(value)


st.sidebar.header("📁 Client Portal Upload")
uploaded_file = st.sidebar.file_uploader(
    "Upload CSV or Excel file", type=["csv", "xlsx", "xls"]
)

if uploaded_file is None:
    st.info("👈 Upload an Excel or CSV file from the sidebar to get started.")
else:
    file_size_mb = uploaded_file.size / (1024 * 1024)
    if file_size_mb > MAX_FILE_SIZE_MB:
        st.error(
            f"File size ({file_size_mb:.2f} MB) exceeds the "
            f"{MAX_FILE_SIZE_MB} MB limit. Please upload a smaller file."
        )
        st.session_state.pop("processed_df", None)
    else:
        try:
            file_bytes = BytesIO(uploaded_file.getvalue())
            if uploaded_file.name.lower().endswith(".csv"):
                df = pd.read_csv(file_bytes)
            else:
                df = pd.read_excel(file_bytes)

            st.subheader("📊 Raw Uploaded Data Preview")
            st.dataframe(df.head(10), use_container_width=True)

            st.sidebar.markdown("---")
            st.sidebar.subheader("⚙️ Cleaning Options")
            remove_duplicates = st.sidebar.checkbox(
                "Remove Duplicate Rows", value=True
            )
            fill_missing = st.sidebar.checkbox(
                "Fill Missing Values with 'N/A'", value=True
            )

            if st.sidebar.button("🚀 Process & Clean Data"):
                processed_df = df.copy()
                if remove_duplicates:
                    processed_df = processed_df.drop_duplicates()
                if fill_missing:
                    processed_df = processed_df.fillna("N/A")
                st.session_state.processed_df = processed_df

            if "processed_df" in st.session_state:
                st.success("Data successfully processed and cleaned!")
                st.subheader("✨ Cleaned Output Table")
                edited_df = st.data_editor(
                    st.session_state.processed_df,
                    num_rows="dynamic",
                    use_container_width=True,
                    key="cleaned_data_editor",
                )

                csv_data = edited_df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="📥 Download Cleaned CSV File",
                    data=csv_data,
                    file_name="client_cleaned_output.csv",
                    mime="text/csv",
                )

                st.markdown("---")
                st.subheader("📄 Optional Google Sheets Sync")
                st.caption(
                    "Sync appends the edited rows to the configured worksheet. "
                    "The sheet's first row must be empty or match the uploaded "
                    "column names exactly."
                )
                if st.button("Sync cleaned rows to Google Sheets"):
                    _, worksheet, config_error = get_sheet_configuration()
                    if config_error:
                        st.error(config_error)
                    elif edited_df.empty:
                        st.warning("There are no rows to sync.")
                    else:
                        headers = [str(column) for column in edited_df.columns]
                        try:
                            existing = worksheet.row_values(1)
                            if not existing:
                                worksheet.update("A1", [headers], value_input_option="RAW")
                            elif existing != headers:
                                st.error(
                                    "The Google Sheet's first row does not match "
                                    "the uploaded columns. No rows were synced "
                                    "to avoid placing data in the wrong columns."
                                )
                                st.stop()

                            rows = [
                                [to_sheet_value(value) for value in row]
                                for row in edited_df.itertuples(
                                    index=False, name=None
                                )
                            ]
                            worksheet.append_rows(
                                rows, value_input_option="RAW"
                            )
                            st.success(
                                f"Synced {len(rows)} rows to Google Sheets."
                            )
                        except Exception:
                            st.error(
                                "Google Sheets sync failed. Check worksheet "
                                "permissions and try again."
                            )

                numeric_cols = edited_df.select_dtypes(
                    include="number"
                ).columns.tolist()
                if numeric_cols:
                    st.markdown("---")
                    st.subheader("📈 Quick Data Visualization / Analytics")
                    selected_col = st.selectbox(
                        "Select numeric column for chart:", numeric_cols
                    )
                    st.bar_chart(edited_df[selected_col])

        except Exception:
            st.error(
                "Could not process this file. Check that it is a valid CSV or "
                "Excel file and try again."
            )

with st.expander("Google Sheets setup (admin)"):
    st.markdown(
        "Create a Google service account, enable the Google Sheets API, and "
        "share the target spreadsheet with the service-account email as an "
        "editor. Add the credentials and target sheet details to Streamlit "
        "Cloud **App settings → Secrets**. Never commit credentials to GitHub."
    )
    st.code(
        '[gcp_service_account]\n'
        'type = "service_account"\n'
        'project_id = "your-project-id"\n'
        'private_key_id = "your-private-key-id"\n'
        'private_key = "-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n"\n'
        'client_email = "your-service-account@your-project.iam.gserviceaccount.com"\n'
        'token_uri = "https://oauth2.googleapis.com/token"\n\n'
        'spreadsheet_id = "your-google-spreadsheet-id"\n'
        'worksheet_name = "Sheet1"',
        language="toml",
    )
    st.caption(
        "The sync keeps the uploaded file's column names and order. To use "
        "specific contact columns such as Name, Email, or LinkedIn, the source "
        "file must contain those fields or be mapped before syncing."
    )
