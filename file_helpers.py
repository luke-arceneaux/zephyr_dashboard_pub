import boto3
from urllib.parse import urlparse 
import pandas as pd
import streamlit as st
from config import PRESIGNED_EXPIRY, S3_BUCKET, S3_METADATA_KEY

# @st.cache_data(ttl=300)  # refresh every 5 minutes
# def load_metadata():
#     dtype = {"Subject_ID": str, "Session_ID": str}

#     s3 = boto3.client("s3")

#     obj = s3.get_object(
#         Bucket=S3_BUCKET,
#         Key=S3_METADATA_KEY
#     )

#     return pd.read_csv(obj["Body"], dtype=dtype)

@st.cache_data(ttl=300)
def load_metadata(bucket, key):
    dtype = {"Subject_ID": str, "Session_ID": str}
    s3 = boto3.client("s3")
    obj = s3.get_object(Bucket=bucket, Key=key)
    df = pd.read_csv(obj["Body"], dtype=dtype)
    df["source"] = bucket  # Add a source column for later filtering/labeling
    return df

def parse_s3_uri(uri):
    parsed = urlparse(uri)
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")
    return bucket, key

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

@st.cache_data(ttl=PRESIGNED_EXPIRY-60)
def add_presigned_links(df):
    df = df.copy()

    df["PDF Report"] = df["PDF Report"].apply(generate_presigned_url)
    df["Interactive Report"] = df["Interactive Report"].apply(generate_presigned_url)
    df["SpO2 Snapshot"] = df["SpO2 Snapshot"].apply(generate_presigned_url)

    return df