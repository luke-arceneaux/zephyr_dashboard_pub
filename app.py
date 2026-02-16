import streamlit as st
import pandas as pd
from filters import render_filters
from file_helpers import load_metadata, add_presigned_links
from config import DISPLAY_COLUMNS

st.set_page_config(
    page_title="Sleep Data Dashboard",
    layout="wide"
)

# -----------------------------
# Load Data
# -----------------------------

df = load_metadata().copy()

# df["Date"] = pd.to_datetime(df["Date"], format="%m/%d/%Y")
df["Date"] = pd.to_datetime(
    df["Date"],
    format="mixed"
).dt.date
df["Start Time"] = pd.to_datetime(df["Start Time"], format="%H:%M:%S").dt.time

# -----------------------------
# Header
# -----------------------------

st.title("Sleep Data Dashboard")

st.caption(
    f"Last updated: {df['Date'].max() if len(df) else 'N/A'}"
)

# -----------------------------
# Filter
# -----------------------------

start_date, end_date, min_duration, selected_subject = render_filters(df)

print(f"Filters - Start: {start_date}, End: {end_date}, Min Duration: {min_duration}, Subject: {selected_subject}")

filtered_df = df[
    (df["Date"] >= start_date) &
    (df["Date"] <= end_date) &
    (df["Duration (min)"] >= min_duration)
]

if selected_subject != "All Subjects":
    filtered_df = filtered_df[filtered_df["Subject_ID"] == selected_subject]

filtered_df = filtered_df.sort_values("Date", ascending=False) # sort by subject ID?

filtered_df = add_presigned_links(filtered_df)

if filtered_df.empty:
    st.warning("No sessions match the selected filters.")
    st.stop()


st.divider()

# -----------------------------
# Subject Summary
# -----------------------------

col1, col2, col3 = st.columns(3)

col1.metric("Nights Recorded", len(filtered_df))

if selected_subject == "All Subjects":
    col2.metric("Unique Subjects", filtered_df["Subject_ID"].nunique())
else:
    if not filtered_df.empty:
        col2.metric(
            "Avg ODI",
            f"{filtered_df['ODI'].mean():.2f}",
            # f"±{filtered_df['ODI'].std():.2f}"
        )
    else:
        col2.metric("Avg ODI", "N/A")

if not filtered_df.empty:
    col3.metric(
        "Avg Hypoxic Burden",
        f"{filtered_df['Hypoxic Burden (4%)'].mean():.2f}",
        # f"±{filtered_df['Hypoxic Burden (4%)'].std():.2f}"
    )
else:
    col3.metric("Avg Hypoxic Burden", "N/A")


st.divider()

# -----------------------------
# Session Table
# -----------------------------

table_df = filtered_df[DISPLAY_COLUMNS].round(2).reset_index(drop=True)

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
# SpO₂ Plot Gallery
# -----------------------------

st.divider()
st.subheader("SpO₂ Plot Comparison")

# Plot selection
col1, _ = st.columns([1, 4])
with col1:
    max_plots = st.number_input(
        "Max plots to display",
        min_value=1,
        max_value=50,
        value=20,
        step=1
    )

    link_target = st.segmented_control(
        "Clicking thumbnails opens",
        ["Interactive HTML", "PDF Report"],
        default="Interactive HTML"
    )

    generate_gallery = st.button(
        "Generate SpO₂ Thumbnail Gallery",
        type="primary"
    )

if generate_gallery:
    st.session_state["show_spo2_gallery"] = True

# Reset gallery if filters change
if "last_filter_hash" not in st.session_state:
    st.session_state.last_filter_hash = None

filter_hash = (start_date, end_date, min_duration, selected_subject)

if filter_hash != st.session_state.last_filter_hash:
    st.session_state["show_spo2_gallery"] = False
    st.session_state.last_filter_hash = filter_hash

# Display gallery if flag is set
if st.session_state.get("show_spo2_gallery", False):

    gallery_df = filtered_df[
        filtered_df["SpO2 Snapshot"].notna() &
        (filtered_df["SpO2 Snapshot"] != "")
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

                pdf_url = row["PDF Report"]
                html_url = row["Interactive Report"]
                plot_url = row["SpO2 Snapshot"] if row["SpO2 Snapshot"] else None

                if link_target == "Interactive HTML":
                    print("Link target: Interactive HTML")
                    target_url = html_url if html_url else pdf_url
                elif link_target == "PDF Report":
                    print("Link target: PDF Report")
                    target_url = pdf_url if pdf_url else html_url
                else:
                    target_url = None

                if plot_url and target_url:
                    # st.markdown(
                    #     f"""
                    #     <a href="{pdf_url}" target="_blank">
                    #         <img src="{plot_url}" style="width:100%; border-radius:6px;" />
                    #     </a>
                    #     """,
                    #     unsafe_allow_html=True,
                    # )
                    st.markdown(
                        f"""
                        <style>
                        .spo2-thumb {{
                            border-radius:8px;
                            cursor:pointer;
                            transition: transform 0.15s ease-in-out;
                        }}
                        .spo2-thumb:hover {{
                            transform: scale(1.02);
                        }}
                        </style>

                        <a href="{target_url}" target="_blank" style="text-decoration:none;">
                            <img src="{plot_url}" class="spo2-thumb" style="width:100%;" />
                        </a>
                        """,
                        unsafe_allow_html=True
                    )
                elif plot_url:
                    st.image(plot_url, use_container_width=True)
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

# df["DateTime"] = pd.to_datetime(df["Date"] + " " + df["Start Time"])
trend_df = filtered_df.sort_values("Date")

st.line_chart(
    trend_df,
    x="Date",
    y=["ODI", "Hypoxic Burden (4%)"]
)