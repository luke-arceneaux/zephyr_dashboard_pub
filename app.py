import streamlit as st
import pandas as pd
import boto3
from urllib.parse import urlparse
from datetime import date, time

# -----------------------------
# Config
# -----------------------------

METADATA_PATH = "zephyr_stereo_metadata_0.csv"

PRESIGNED_EXPIRY = 3600  # seconds

st.set_page_config(
    page_title="Sleep Data Dashboard",
    layout="wide"
)

# -----------------------------
# Helpers
# -----------------------------

@st.cache_data
def load_metadata():
    dtype={'Subject_ID': str, 'Session_ID': object}
    return pd.read_csv(METADATA_PATH, dtype=dtype)


def parse_s3_uri(uri):
    parsed = urlparse(uri)
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")
    return bucket, key

def make_clickable(label, url):
    if not url:
        return ""
    return f"[{label}]({url})"


# def generate_presigned_url(s3_uri):
#     if pd.isna(s3_uri) or not s3_uri:
#         return None

#     bucket, key = parse_s3_uri(s3_uri)

#     s3 = boto3.client("s3")
#     return s3.generate_presigned_url(
#         ClientMethod="get_object",
#         Params={"Bucket": bucket, "Key": key},
#         ExpiresIn=PRESIGNED_EXPIRY
#     )

def generate_presigned_url(s3_uri):
    if not isinstance(s3_uri, str):
        return None

    s3_uri = s3_uri.strip()

    if not s3_uri.startswith("s3://"):
        return None

    try:
        bucket, key = parse_s3_uri(s3_uri)

        if not bucket or not key:
            return None

        s3 = boto3.client("s3")
        return s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=PRESIGNED_EXPIRY
        )

    except Exception:
        return None


# @st.cache_data
# def add_presigned_links(df):
#     df = df.copy()

#     df["PDF Report"] = df["PDF Report"].apply(
#         lambda x: make_clickable("PDF", generate_presigned_url(x))
#     )

#     df["Interactive Report"] = df["Interactive Report"].apply(
#         lambda x: make_clickable("HTML", generate_presigned_url(x))
#     )

#     df["SpO2 Snapshot"] = df["SpO2 Snapshot"].apply(
#         lambda x: make_clickable("View", generate_presigned_url(x))
#     )

#     return df
@st.cache_data
def add_presigned_links(df):
    df = df.copy()

    df["PDF Report"] = df["PDF Report"].apply(generate_presigned_url)
    df["Interactive Report"] = df["Interactive Report"].apply(generate_presigned_url)
    df["SpO2 Snapshot"] = df["SpO2 Snapshot"].apply(generate_presigned_url)

    return df


def add_date_and_start_time(df):
    """
    Adds 'date' and 'start_time' columns to the DataFrame, parsed from Session_ID.
    """
    def parse_session_id(session):
        try:
            year = int(str(session)[:4])
            month = int(str(session)[4:6])
            day = int(str(session)[6:8])
            hour = int(str(session)[8:10])
            minute = int(str(session)[10:12])
            second = int(str(session)[12:])
            return date(year, month, day), time(hour, minute, second)
        except Exception:
            return date(2024, 1, 1), time(0, 0, 0)
    
    df = df.copy()
    df['date'], df['start_time'] = zip(*df['Session_ID'].map(parse_session_id))
    df["Session_ID"] = df["Session_ID"].astype(str)
    return df

def get_relevant_data(df):
    df = df[df.Date > date(2025, 1, 1)]
    df = df[df["Duration (s)"] > 30*60]
    return df

# -----------------------------
# Load Data
# -----------------------------

df = load_metadata()
print(df.head())
df["Date"] = pd.to_datetime(df["Date"]).dt.date
df["Start Time"] = pd.to_datetime(df["Start Time"]).dt.time
# df = add_date_and_start_time(df)
df = get_relevant_data(df)

# -----------------------------
# Header
# -----------------------------

st.title("Sleep Data Dashboard")

print(df.columns)
st.caption(
    f"Last updated: {df['Date'].max() if len(df) else 'N/A'}"
)

# -----------------------------
# Subject Filter
# -----------------------------

subjects = ["All Subjects"] + sorted(df["Subject_ID"].unique().tolist())

selected_subject = st.selectbox(
    "Select Subject",
    subjects
)

if selected_subject == "All Subjects":
    subject_df = df.sort_values(["Subject_ID", "Date"])
else:
    subject_df = df[df["Subject_ID"] == selected_subject].sort_values("Date")

subject_df = add_presigned_links(subject_df)


# -----------------------------
# Subject Summary
# -----------------------------

col1, col2, col3 = st.columns(3)

col1.metric("Nights Recorded", len(subject_df))

if selected_subject == "All Subjects":
    col2.metric("Unique Subjects", subject_df["Subject_ID"].nunique())
else:
    col2.metric("Avg ODI", round(subject_df["ODI"].mean(), 2))

col3.metric("Avg Hypoxic Burden", round(subject_df["Hypoxic Burden (4%)"].mean(), 2))

st.divider()

# -----------------------------
# Session Table
# -----------------------------

DISPLAY_COLUMNS = [
    "Subject_ID",
    "Session_ID",
    "Date",
    "Start Time",
    "Duration (s)",
    "ODI",
    "NST Count",
    "Desat Count (3%)",
    "Desat Count (4%)",
    "Desat Count (sub 90%)",
    "Hypoxic Burden (4%)",
    "Min SpO2",
    "T90_perc",
    "T90_min",
    "supine_proportion",
    "prone_proportion",
    "left_proportion",
    "right_proportion",
    "upright_proportion",
    "non_supine_proportion",
    "PDF Report",
    "Interactive Report",
    "SpO2 Snapshot"
]

# table_df = subject_df[DISPLAY_COLUMNS].reset_index(drop=True)

st.subheader("Nights of Sleep")

# st.dataframe(
#     table_df,
#     use_container_width=True,
#     selection_mode="single-row",
#     on_select="rerun",
#     key="sleep_table"
# )
# st.dataframe(
#     subject_df[DISPLAY_COLUMNS],
#     use_container_width=True,
#     column_config={
#         "PDF_Report": st.column_config.MarkdownColumn("PDF Report"),
#         "Interactive_Report": st.column_config.MarkdownColumn("Interactive Report"),
#         "SpO2_Snapshot": st.column_config.MarkdownColumn("SpO₂ Plot")
#     }
# )
st.dataframe(
    subject_df[DISPLAY_COLUMNS],
    use_container_width=True,
    column_config={
        "PDF Report": st.column_config.LinkColumn(
            "PDF Report", 
            display_text="PDF"
        ),
        "Interactive Report": st.column_config.LinkColumn(
            "Interactive Report", 
            display_text="HTML"
        ),
        "SpO2 Snapshot": st.column_config.LinkColumn(
            "SpO2 Snapshot", 
            display_text="View"
        )
    }
)




# -----------------------------
# Row Selection Handling
# -----------------------------

selection = st.session_state.get("sleep_table", {}).get("selection", {})

if "rows" in selection and len(selection["rows"]) > 0:
    idx = selection["rows"][0]
    row = subject_df.iloc[idx]

    st.divider()
    # st.subheader(f"Session: {row['date']}")

    # ---- Report Links ----
    col1, col2 = st.columns(2)

    with col1:
        if row["report_pdf_s3_uri"]:
            pdf_url = generate_presigned_url(row["report_pdf_s3_uri"])
            st.link_button("Open PDF Report", pdf_url)
        else:
            st.caption("PDF report not available")

    with col2:
        if row["report_html_s3_uri"]:
            html_url = generate_presigned_url(row["report_html_s3_uri"])
            st.link_button("Open HTML Report", html_url)
        else:
            st.caption("HTML report not available")

    # ---- SpO2 Plot Preview ----
    st.subheader("SpO₂ Plot")

    if pd.isna(row["spo2_plot_png_s3_uri"]) or not row["spo2_plot_png_s3_uri"]:
        st.warning("No SpO₂ plot available for this session.")
    else:
        plot_url = generate_presigned_url(row["spo2_plot_png_s3_uri"])
        st.image(plot_url, use_container_width=True)

# -----------------------------
# Trend Plots
# -----------------------------

# st.divider()
# st.subheader("Trends")

# trend_df = subject_df.sort_values("date")

# st.line_chart(
#     trend_df.set_index("date")[["ODI", "hypoxic_burden"]]
# )
