import streamlit as st
import pandas as pd
import sqlite3
import os
from filters import render_filters
from file_helpers import load_metadata, add_presigned_links
from config import DISPLAY_COLUMNS, GALLERY_SORT_OPTIONS

st.set_page_config(
    page_title="Sleep Data Dashboard",
    layout="wide"
)

# -----------------------------
# Notes DB Setup
# -----------------------------

NOTES_DB_PATH = "session_notes.db"

def init_notes_db():
    conn = sqlite3.connect(NOTES_DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            Subject_ID TEXT,
            Session_ID TEXT,
            Note TEXT,
            PRIMARY KEY (Subject_ID, Session_ID)
        )
    """)
    conn.commit()
    conn.close()

def get_note(subject_id, session_id):
    conn = sqlite3.connect(NOTES_DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT Note FROM notes WHERE Subject_ID=? AND Session_ID=?",
        (subject_id, session_id)
    )
    row = c.fetchone()
    conn.close()
    return row[0] if row else ""

def save_note(subject_id, session_id, note):
    conn = sqlite3.connect(NOTES_DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO notes (Subject_ID, Session_ID, Note) VALUES (?, ?, ?)",
        (subject_id, session_id, note)
    )
    conn.commit()
    conn.close()

init_notes_db()

# -----------------------------
# Archive DB Setup
# -----------------------------

def init_archive_db():
    conn = sqlite3.connect(NOTES_DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS archive (
            Subject_ID TEXT,
            Session_ID TEXT,
            archived INTEGER DEFAULT 0,
            archive_reason TEXT,
            archived_at TEXT,
            PRIMARY KEY (Subject_ID, Session_ID)
        )
    """)
    conn.commit()
    conn.close()

def set_archive(subject_id, session_id, reason, archived=True):
    import datetime
    conn = sqlite3.connect(NOTES_DB_PATH)
    c = conn.cursor()
    if archived:
        c.execute(
            "INSERT OR REPLACE INTO archive (Subject_ID, Session_ID, archived, archive_reason, archived_at) VALUES (?, ?, 1, ?, ?)",
            (subject_id, session_id, reason, datetime.datetime.now().isoformat())
        )
    else:
        c.execute(
            "INSERT OR REPLACE INTO archive (Subject_ID, Session_ID, archived, archive_reason, archived_at) VALUES (?, ?, 0, NULL, NULL)",
            (subject_id, session_id)
        )
    conn.commit()
    conn.close()

def get_archive_status():
    conn = sqlite3.connect(NOTES_DB_PATH)
    c = conn.cursor()
    c.execute("SELECT Subject_ID, Session_ID, archived, archive_reason FROM archive")
    rows = c.fetchall()
    conn.close()
    # Return as dict for fast lookup
    return {(row[0], row[1]): {'archived': bool(row[2]), 'archive_reason': row[3]} for row in rows}

init_notes_db()
init_archive_db()

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
df["SessionDateTime"] = pd.to_datetime(
    df["Date"].astype(str) + " " + df["Start Time"].astype(str),
    errors="coerce"
)
df["HypBurIndex(4%)"] = df["Hypoxic Burden (4%)"]/(df["Duration (min)"]/60)
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

if "All Subjects" not in selected_subject:
    filtered_df = filtered_df[filtered_df["Subject_ID"].isin(selected_subject)]

filtered_df = filtered_df.sort_values("SessionDateTime", ascending=False) # sort by subject ID?

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

if "All Subjects" in selected_subject:
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

st.subheader("Nights of Sleep")

show_notes = st.toggle("Show Notes", value=False)

# Merge archive status into table_df
archive_status = get_archive_status()
table_df = filtered_df[DISPLAY_COLUMNS].round(2).reset_index(drop=True)
table_df["Archived"] = table_df.apply(lambda row: archive_status.get((row["Subject_ID"], row["Session_ID"]), {}).get("archived", False), axis=1)
table_df["Archive Reason"] = table_df.apply(lambda row: archive_status.get((row["Subject_ID"], row["Session_ID"]), {}).get("archive_reason", ""), axis=1)

# Show/hide archived rows toggle
show_archived = st.toggle("Show archived data", value=False)
if not show_archived:
    table_df = table_df[~table_df["Archived"]]

if show_notes:
    def fetch_note(row):
        return get_note(row["Subject_ID"], row["Session_ID"])
    table_df["Note"] = table_df.apply(fetch_note, axis=1)

column_config = {
    "PDF Report": st.column_config.LinkColumn("PDF Report", display_text="PDF"),
    "Interactive Report": st.column_config.LinkColumn("Interactive Report", display_text="HTML"),
    "SpO2 Snapshot": st.column_config.LinkColumn("SpO2 Snapshot", display_text="View"),
}

display_df = table_df.copy()
if show_archived:
    column_config["Archived"] = st.column_config.CheckboxColumn("Archived", disabled=True)
    column_config["Archive Reason"] = st.column_config.TextColumn("Archive Reason", disabled=True)
else:
    display_df = display_df.drop(columns=["Archived", "Archive Reason"])

st.dataframe(
    display_df,
    use_container_width=True,
    column_config=column_config,
    key="sleep_table"
)

# -----------------------------
# Editor
# -----------------------------

st.divider()

with st.expander("Session Notes & Archive", expanded=False):
    session_options = [
        f"Subject {row.Subject_ID} | Session {row.Session_ID} | {row.Date}"
        for _, row in table_df.iterrows()
    ]

    if not session_options:
        st.info("No sessions available.")
    else:
        selected = st.selectbox("Select session", session_options, key="notes_archive_select")
        sel_idx = session_options.index(selected)
        sel_row = table_df.iloc[sel_idx]
        subj_id = sel_row["Subject_ID"]
        sess_id = sel_row["Session_ID"]
        is_archived = sel_row["Archived"]
        archive_reason = sel_row["Archive Reason"]

        tab_notes, tab_archive = st.tabs(["Notes", "Archive"])

        with tab_notes:
            existing_note = get_note(subj_id, sess_id)
            note = st.text_area("Note", value=existing_note, height=100, label_visibility="collapsed")
            if st.button("Save Note", key="save_note_btn"):
                save_note(subj_id, sess_id, note)
                st.success("Note saved.")

        with tab_archive:
            if not is_archived:
                st.info("This session is not archived.")
                reason = st.text_area("Reason for archiving", value="", height=60)
                if st.button("Archive Session", key="archive_btn"):
                    if reason.strip():
                        set_archive(subj_id, sess_id, reason, archived=True)
                        st.success("Session archived.")
                        st.rerun()
                    else:
                        st.warning("Please provide a reason to archive.")
            else:
                st.info(f"This session is archived. Reason: {archive_reason}")
                if st.button("Unarchive Session", key="unarchive_btn"):
                    set_archive(subj_id, sess_id, reason=None, archived=False)
                    st.success("Session unarchived.")
                    st.rerun()

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

    sort_label = st.selectbox(
        "Sort gallery by",
        options=list(GALLERY_SORT_OPTIONS.keys()),
        index=0
    )

    sort_desc = st.toggle(
        "Descending (highest / newest first)",
        value=True
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
    sort_col = GALLERY_SORT_OPTIONS[sort_label]

    gallery_df = filtered_df[
        filtered_df["SpO2 Snapshot"].notna() &
        (filtered_df["SpO2 Snapshot"] != "")
    ].sort_values(
        by=sort_col,
        ascending=not sort_desc,
        na_position="last"
    ).head(max_plots)

    filter_hash = (
        start_date,
        end_date,
        min_duration,
        tuple(selected_subject),
        sort_label,
        sort_desc
    )

    if gallery_df.empty:
        st.warning("No SpO₂ plots available for the current filters.")
    else:
        # st.caption(
        #     f"Displaying {len(gallery_df)} SpO₂ plots "
        #     f"(filtered, capped at {max_plots})"
        # )
        st.caption(
            f"Displaying {len(gallery_df)} SpO₂ plots • "
            f"Sorted by {sort_label} "
            f"({'desc' if sort_desc else 'asc'})"
        )

        # ---- Thumbnail grid ----
        NUM_COLS = 4
        cols = st.columns(NUM_COLS)

        for idx, (_, row) in enumerate(gallery_df.iterrows()):
            col = cols[idx % NUM_COLS]

            with col:
                # st.markdown(
                #     f"**Subject: {row['Subject_ID']}**<br>{row['Date']}",
                #     unsafe_allow_html=True
                # )
                with col:
                    # st.markdown(
                    #     f"""
                    #     <div style="margin-bottom:4px;">
                    #         <b>Subject:</b> {row['Subject_ID']}<br>
                    #         <b>Date:</b> {row['Date']} | <b>Start:</b> {row['Start Time']}
                    #     </div>
                    #     <div style="font-size:0.85rem; line-height:1.4;">
                    #         Duration: {row['Duration (min)']/60:.1f} hrs<br>
                    #         ODI: {row['ODI']:.2f} | Hypoxic Burden: {row['Hypoxic Burden (4%)']:.2f} | T90%: {row['T90_perc']:.2f}%
                    #     </div>
                    #     """,
                    #     unsafe_allow_html=True
                    # )
                    device_id = row.get("Device_ID", "")
                    device_str = "" if (device_id is None or str(device_id).strip().lower() == "nan") else str(device_id).strip()

                    st.markdown(
                        f"""
                        <div style="margin-bottom:4px;">
                            <b>Subject:</b> {row['Subject_ID']}<br>
                            <b>Date:</b> {row['Date']} | <b>Start:</b> {row['Start Time']}<br>
                            <b>Device:</b> {device_str if device_str else '<span style="color:#aaa;">—</span>'}
                        </div>
                        <div style="font-size:0.85rem; line-height:1.4;">
                            Duration: {row['Duration (min)']/60:.1f} hrs<br>
                            ODI: {row['ODI']:.2f} | Hypoxic Burden: {row['Hypoxic Burden (4%)']:.2f} | T90%: {row['T90_perc']:.2f}%
                        </div>
                        """,
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
trend_df = filtered_df.sort_values("SessionDateTime").copy()

st.line_chart(
    trend_df,
    x="SessionDateTime",
    y=["ODI", "Hypoxic Burden (4%)"]
)