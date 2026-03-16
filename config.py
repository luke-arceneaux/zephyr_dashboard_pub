PRESIGNED_EXPIRY = 3600  # seconds
S3_BUCKET = "zephyrapptestbucket"
S3_METADATA_KEY = "metadata/session_metadata.csv"
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
    "HypBurIndex(4%)",
    # "Hypoxic Burden (4%)",
    "Min SpO2",
    "T90_perc",
    "T90_min",
    "supine_proportion",
    "PDF Report",
    "Interactive Report",
    # "SpO2 Snapshot"
]
GALLERY_SORT_OPTIONS = {
    "Most Recent": "SessionDateTime",
    "Duration": "Duration (min)",
    "ODI": "ODI",
    "Hypoxic Burden (4%)": "HypBurIndex(4%)",
    "T90 (%)": "T90_perc",
}