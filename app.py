from datetime import date, datetime
from io import BytesIO
import re

import gspread
import pandas as pd
import streamlit as st

MAX_FILE_SIZE_MB = 10
SHEET_COLUMNS = [
    "Name",
    "First Name",
    "Last Name",
    "Company Name",
    "Website",
    "Email",
    "Verify Status",
    "LinkedIn",
]

# Map common source-header variations to the requested Google Sheets columns.
HEADER_ALIASES = {
    "name": "Name",
    "full name": "Name",
    "first name": "First Name",
    "firstname": "First Name",
    "last name": "Last Name",
    "lastname": "Last Name",
    "company": "Company Name",
    "company name": "Company Name",
    "website": "Website",
    "url": "Website",
    "email": "Email",
    "verify status": "Verify Status",
    "verification status": "Verify Status",
    "varify status": "Verify Status",
    "linkedin": "LinkedIn",
    "linkedin url": "LinkedIn",
    "linkedin profile": "LinkedIn",
}

st.set_page_config(
    page_title="Automated Data Entry & Cleaning Portal",
    page_icon="🤖",
    layout="wide",
)
st.title("🤖 Automated Data Cleaning & Entry Portal")
st.markdown(
    "Upload a contact/lead CSV or Excel file to clean it and optionally sync "
    "the matching fields to your Google Sheets contact template."
)
st.markdown("---")
st.info(
    "🔒 Uploaded files are processed in app memory. Google Sheets sync is "
    "optional and only happens when you click the sync button. Review your "
    "hosting provider's privacy and data-retention policies before uploading "
    "sensitive information."
)


def get_sheet_configuration():
    """Return the configured worksheet or a safe, user-facing error."""
    try:
        credentials = dict(st.secrets["gcp_service_account"])
        spreadsheet_id = st.secrets["spreadsheet_id"]
        worksheet_name = st.secrets.get("worksheet_name", "Sheet1")
    except (KeyError, AttributeError):
        return None, "Google Sheets is not configured in app secrets."

    try:
        client = gspread.service_account_from_dict(credentials)
        worksheet = client.open_by_key(spreadsheet_id).worksheet(worksheet_name)
        return worksheet, None
    except Exception:
        return None, (
            "Could not connect to the configured Google Sheet. Check the app "
            "secrets, spreadsheet ID, worksheet name, and service-account access."
        )


def normalized_header(value):
    return re.sub(r"\s+", " ", str(value).strip().lower())


def make_contact_sheet_frame(dataframe):
    """Map recognized contact columns into the fixed screenshot schema."""
    mapped = {}
    for source_column in dataframe.columns:
        destination = HEADER_ALIASES.get(normalized_header(source_column))
        if destination and destination not in mapped:
            mapped[destination] = source_column

    result = pd.DataFrame(index=dataframe.index)
    for column in SHEET_COLUMNS:
        if column in mapped:
            result[column] = dataframe[mapped[column]]
        else:
            result[column] = ""
    return result


def to_sheet_value(value):
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
    st.info("👈 Upload a contact/lead Excel or CSV file from the sidebar.")
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

            st.subheader("📊 Uploaded Data Preview")
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
                st.subheader("✨ Cleaned Data")
                edited_df = st.data_editor(
                    st.session_state.processed_df,
                    num_rows="dynamic",
                    use_container_width=True,
                    key="cleaned_data_editor",
                )
                st.download_button(
                    label="📥 Download Cleaned CSV File",
                    data=edited_df.to_csv(index=False).encode("utf-8"),
                    file_name="client_cleaned_output.csv",
                    mime="text/csv",
                )

                contact_df = make_contact_sheet_frame(edited_df)
                mapped_columns = [
                    column for column in edited_df.columns
                    if normalized_header(column) in HEADER_ALIASES
                ]
                st.markdown("---")
                st.subheader("Google Sheets Contact Form Preview")
                st.caption(
                    "The sheet template uses the requested columns. Unmatched "
                    "fields will be left blank; order data is not automatically "
                    "converted into contact/lead information."
                )
                st.dataframe(contact_df.head(10), use_container_width=True)

                if st.button("Sync contact rows to Google Sheets"):
                    if not mapped_columns:
                        st.error(
                            "No contact columns were found. Include headers such "
                            "as Name, First Name, Last Name, Company Name, "
                            "Website, Email, Verify Status, or LinkedIn."
                        )
                    elif contact_df.empty:
                        st.warning("There are no rows to sync.")
                    else:
                        worksheet, config_error = get_sheet_configuration()
                        if config_error:
                            st.error(config_error)
                        else:
                            try:
                                existing_headers = worksheet.row_values(1)
                                if not existing_headers:
                                    worksheet.update(
                                        "A1",
                                        [SHEET_COLUMNS],
                                        value_input_option="RAW",
                                    )
                                elif existing_headers != SHEET_COLUMNS:
                                    st.error(
                                        "The worksheet's first row must exactly "
                                        "match the template: "
                                        + ", ".join(SHEET_COLUMNS)
                                        + ". No rows were synced."
                                    )
                                    st.stop()

                                rows = [
                                    [to_sheet_value(value) for value in row]
                                    for row in contact_df.itertuples(
                                        index=False, name=None
                                    )
                                ]
                                worksheet.append_rows(
                                    rows, value_input_option="RAW"
                                )
                                st.success(
                                    f"Synced {len(rows)} contact rows to "
                                    "Google Sheets."
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
        "editor. Add the values below to Streamlit Cloud **App settings → "
        "Secrets**. Keep the spreadsheet ID at the top level and credentials "
        "inside `[gcp_service_account]`. Never commit credentials to GitHub."
    )
    st.code(
        'spreadsheet_id = "your-google-spreadsheet-id"\n'
        'worksheet_name = "Sheet1"\n\n'
        '[gcp_service_account]\n'
        'type = "service_account"\n'
        'project_id = "your-project-id"\n'
        'private_key_id = "your-private-key-id"\n'
        'private_key = "-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n"\n'
        'client_email = "your-service-account@your-project.iam.gserviceaccount.com"\n'
        'token_uri = "https://oauth2.googleapis.com/token"',
        language="toml",
    )
