PRESIGNED_EXPIRY = 3600  # seconds
S3_METADATA_KEY = "metadata/session_metadata.csv"
S3_DB_BUCKET = "zephyrapptestbucket"
S3_DB_KEY = "metadata/session_notes.db"
LOCAL_DB_PATH = "session_notes.db"

DATA_SOURCES = {
    "zephyr": {
        "label": "ZEPHYR",
        "bucket": "zephyrapptestbucket",
        "metadata_key": "metadata/session_metadata.csv"
    },
    "mesa": {
        "label": "MESA",
        "bucket": "neurostimstore",
        "metadata_key": "metadata/session_metadata.csv"
    },
    "scidb": {
        "label": "SCIDB",
        "bucket": "neurostimstore",
        "metadata_key": "metadata/session_metadata.csv"
    },
    "shhs": {
        "label": "SHHS",
        "bucket": "neurostimstore",
        "metadata_key": "metadata/session_metadata.csv"
    }
}
DISPLAY_COLUMNS = [
    "Subject_ID",
    "Session_ID",
    "Dataset",
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