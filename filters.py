import streamlit as st
import pandas as pd

def render_filters(df):
    """
    Renders filters for session date range, minimum duration, and subject selection.
    """
    min_date_in_data = df["Date"].min()
    max_date = df["Date"].max()
    cutoff_date = pd.to_datetime("2026-01-01").date()

    # If any date in the data is after 1/1/2026, use 1/1/2026 as min, else use min_date_in_data
    if (df["Date"] > cutoff_date).any():
        default_min_date = cutoff_date
    else:
        default_min_date = min_date_in_data
    default_max_date = max_date

    df["Dataset_Subject"] = df["Dataset"].astype(str) + ":" + df["Subject_ID"].astype(str)
    ids_sorted = (
        df.groupby('Dataset_Subject')['Date'] #Subject_ID
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
            value=(default_min_date, default_max_date),
            min_value=min_date_in_data,
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
                start_date = end_date = min_date_in_data
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
        selected_subject = st.multiselect(
            "Select Subject",
            subjects, 
            default=["All Subjects"]
        )

    return start_date, end_date, min_duration, selected_subject
