import streamlit as st
import pandas as pd


def render_filters(df):

    # ---- Date Range Filter ----
    # min_date = df["Date"].min()
    min_date = pd.to_datetime("2025-01-01").date()  # Set to fixed date for consistency
    max_date = df["Date"].max()

    date_range = st.date_input(
        "Session Date Range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )

    # Handle single-date edge case
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date = end_date = date_range

    # ---- Minimum Duration Filter (minutes) ----
    min_duration = st.number_input(
        "Minimum Duration (minutes)",
        min_value=0,
        max_value=int(df["Duration (min)"].max()),
        value=30,
        step=5
    )

    return start_date, end_date, min_duration
