import streamlit as st
import pandas as pd

def render_filters(df):
    """
    Renders filters for session date range, minimum duration, and subject selection.
    """
    # min_date = df["Date"].min()
    min_date = pd.to_datetime("2026-01-01").date()  # Set to fixed date for consistency
    max_date = df["Date"].max()

    ids_sorted = (
        df.groupby('Subject_ID')['Date']
        .max()                 # most recent date per ID
        .sort_values(ascending=False)
        .index
        .tolist()
    )
    subjects = ["All Subjects"] + ids_sorted

    col1, col2, col3 = st.columns(3)
    with col1:
        date_range = st.date_input(
            "Session Date Range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date
        )
        # Handle single-date edge case
        # if isinstance(date_range, tuple) and len(date_range) == 2:
        #     start_date, end_date = date_range
        # else:
        #     start_date = end_date = date_range

        if isinstance(date_range, (tuple, list)):
            if len(date_range) == 2:
                start_date, end_date = date_range
            elif len(date_range) == 1:
                start_date = end_date = date_range[0]
            else:
                start_date = end_date = min_date
        else:
            start_date = end_date = date_range

    with col2:
        min_duration = st.number_input(
            "Minimum Duration (minutes)",
            min_value=0,
            max_value=int(df["Duration (min)"].max()),
            value=30,
            step=5
        )
    with col3:
        subjects = ["All Subjects"] + sorted(df["Subject_ID"].unique().tolist())
        selected_subject = st.multiselect(
            "Select Subject",
            subjects, 
            default=["All Subjects"]
        )

    return start_date, end_date, min_duration, selected_subject
