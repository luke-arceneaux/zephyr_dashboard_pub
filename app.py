import streamlit as st
import pandas as pd
import boto3
from urllib.parse import urlparse
from datetime import date, time
from filters import render_filters

# -----------------------------
# Config
# -----------------------------

PRESIGNED_EXPIRY = 3600  # seconds
S3_BUCKET = "zephyrapptestbucket"
S3_METADATA_KEY = "metadata/session_metadata.csv"


st.set_page_config(
    page_title="Sleep Data Dashboard",
    layout="wide"
)

# -----------------------------
# Helpers
# -----------------------------

# @st.cache_data
# def load_metadata():
#     dtype={'Subject_ID': str, 'Session_ID': object}
#     return pd.read_csv(METADATA_PATH, dtype=dtype)

@st.cache_data(ttl=300)  # refresh every 5 minutes
def load_metadata():
    dtype = {"Subject_ID": str, "Session_ID": str}

    s3 = boto3.client("s3")

    obj = s3.get_object(
        Bucket=S3_BUCKET,
        Key=S3_METADATA_KEY
    )

    return pd.read_csv(obj["Body"], dtype=dtype)


def parse_s3_uri(uri):
    parsed = urlparse(uri)
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")
    return bucket, key

def make_clickable(label, url):
    if not url:
        return ""
    return f"[{label}]({url})"

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
    # df = df[df["Duration (s)"] > 30*60]
    return df

# -----------------------------
# Load Data
# -----------------------------

df = load_metadata()
print(df.head())
df["Date"] = pd.to_datetime(df["Date"]).dt.date
df["Start Time"] = pd.to_datetime(df["Start Time"]).dt.time
# df = add_date_and_start_time(df)
# df = get_relevant_data(df)



# -----------------------------
# Header
# -----------------------------

st.title("Sleep Data Dashboard")

print(df.columns)
st.caption(
    f"Last updated: {df['Date'].max() if len(df) else 'N/A'}"
)

# -----------------------------
# Filter
# -----------------------------

# subjects = ["All Subjects"] + sorted(df["Subject_ID"].unique().tolist())

# selected_subject = st.selectbox(
#     "Select Subject",
#     subjects
# )

start_date, end_date, min_duration, selected_subject = render_filters(df)

filtered_df = df[
    (df["Date"] >= start_date) &
    (df["Date"] <= end_date) &
    (df["Duration (min)"] >= min_duration)
]

if selected_subject == "All Subjects":
    subject_df = filtered_df.sort_values(["Subject_ID", "Date"])
else:
    subject_df = filtered_df[filtered_df["Subject_ID"] == selected_subject].sort_values("Date")

subject_df = add_presigned_links(subject_df)

st.divider()


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
    "Duration (min)",
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

table_df = subject_df[DISPLAY_COLUMNS].reset_index(drop=True)

st.subheader("Nights of Sleep")

st.dataframe(
    table_df,
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
    },
    key="sleep_table"
)




# -----------------------------
# Row Selection Handling
# -----------------------------

selection = st.session_state.get("sleep_table", {}).get("selection", {})
print(selection)

if "rows" in selection and len(selection["rows"]) > 0:
    idx = selection["rows"][0]
    row = table_df.iloc[idx]

    st.divider()
    st.subheader(f"Session: {row['Date']}")

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

st.divider()
st.subheader("SpO₂ Plot Comparison")

col1, _ = st.columns([1, 4])
with col1:
    max_plots = st.number_input(
        "Max plots to display",
        min_value=1,
        max_value=50,
        value=20,
        step=1
    )

    generate_gallery = st.button(
        "Generate SpO₂ Thumbnail Gallery",
        type="primary"
    )

if generate_gallery:
    st.session_state["show_spo2_gallery"] = True


if st.session_state.get("show_spo2_gallery", False):

    gallery_df = subject_df[
        subject_df["SpO2 Snapshot"].notna() &
        (subject_df["SpO2 Snapshot"] != "")
    ].head(max_plots)

    if gallery_df.empty:
        st.warning("No SpO₂ plots available for the current filters.")
    else:
        st.caption(
            f"Displaying {len(gallery_df)} SpO₂ plots "
            f"(filtered, capped at {max_plots})"
        )

        # ---- Thumbnail grid ----
        NUM_COLS = 4
        cols = st.columns(NUM_COLS)

        for idx, (_, row) in enumerate(gallery_df.iterrows()):
            col = cols[idx % NUM_COLS]

            with col:
                st.markdown(
                    f"**Subject: {row['Subject_ID']}**<br>{row['Date']}",
                    unsafe_allow_html=True
                )

                # plot_url = generate_presigned_url(row["SpO2 Snapshot"])
                plot_url = row["SpO2 Snapshot"] if row["SpO2 Snapshot"] else None

                if plot_url:
                    st.image(
                        plot_url,
                        use_container_width=True
                    )
                else:
                    st.caption("No plot")

# st.divider()
# st.subheader("Enlarge SpO₂ Plot")

# options = [
#     f"{row.Subject_ID} – {row.Date}"
#     for _, row in gallery_df.iterrows()
# ]

# selected = st.selectbox(
#     "Select plot to enlarge",
#     options,
#     index=0
# )

# selected_row = gallery_df.iloc[options.index(selected)]

# plot_url = generate_presigned_url(selected_row["SpO2 Snapshot"])
# st.image(plot_url, use_container_width=True)



# -----------------------------
# Trend Plots
# -----------------------------

st.divider()
st.subheader("Trends")

trend_df = subject_df.sort_values("Date")

st.line_chart(
    trend_df.set_index("Date")[["ODI", "Hypoxic Burden (4%)"]]
)
