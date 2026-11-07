from io import BytesIO
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
    "Upload an Excel or CSV file to clean, format, and analyze your data."
)
st.markdown("---")
st.info(
    "🔒 This app processes uploaded files in memory and does not intentionally "
    "save them to persistent storage. Do not upload sensitive data unless you "
    "have reviewed the hosting provider's privacy and data-retention policies."
)

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

                st.success("Data successfully processed and cleaned!")
                st.subheader("✨ Cleaned Output Table")
                edited_df = st.data_editor(
                    processed_df, num_rows="dynamic", use_container_width=True
                )

                csv_data = edited_df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="📥 Download Cleaned CSV File",
                    data=csv_data,
                    file_name="client_cleaned_output.csv",
                    mime="text/csv",
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
