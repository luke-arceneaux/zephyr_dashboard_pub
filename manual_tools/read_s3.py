import os
import re
from s3_sdk import *
import json
from datetime import date, time
import numpy as np
import pandas as pd

import matplotlib.pyplot as plt

from process_raw import wav_duration_seconds, butterworth_filter, interpolate_segments

def parse_filepath(filepath):
    # e.g. raw_data/scidb/cannula/scidb_cannula_subj1447_sess1.csv
    path = os.path.basename(filepath)
    path = os.path.splitext(path)[0]
    matches = re.match(r'(.*)_(.*)_subj(.*)_sess(.*)', path)
    dataset, signal, subject, session = matches.groups()
    return dataset, signal, subject, session
    
def interpolate_spo2(spo2_raw, interp_window=30):
    if spo2_raw.shape[0] > 15:
        # spo2_raw["filtered_oxygen"] = butterworth_filter(spo2_raw["oxygen"])
        # spo2_raw["oxygen_sq"] = np.square(spo2_raw["filtered_oxygen"])
        # cond_raw = (spo2_raw["oxygen"] > 100) | (spo2_raw["oxygen"] < 50)
        # cond_art = cond_raw | (spo2_raw["oxygen_sq"] > 30)
        # cond_status = (spo2_raw["status"] != 3) | (spo2_raw["confidence"] < 90)
        # spo2_raw["artifact"] = cond_art | cond_status

        cond_raw = (spo2_raw["oxygen"] > 100) | (spo2_raw["oxygen"] < 50)
        cond_status = (spo2_raw["status"] != 3) | (spo2_raw["confidence"] < 90)
        spo2_raw["artifact"] = cond_raw | cond_status

        spo2_raw = interpolate_segments(spo2_raw, interp_window)
        
        print(f"artifacts: {spo2_raw.artifact.mean()}")
        cond_raw = (spo2_raw["oxygen"] > 100) | (spo2_raw["oxygen"] < 50)
        
    else:
        spo2_raw["artifact"] = True

    return spo2_raw

def generate_file_field_paths(subject, session, snapshot_status):
    s3_front = "s3://zephyrapptestbucket/"
    report_path = f"reports/zephyr/stereo/"
    snapshot_path = f"snapshots/zephyr/stereo/"
    filename = f"zephyr_stereo_subj{subject}_sess{session}"
    report_files = {
        "PDF Report": f"{s3_front}{report_path}{filename}.pdf",
        "Interactive Report": f"{s3_front}{report_path}{filename}.html",
    }
    if snapshot_status is not None:
        report_files["SpO2 Snapshot"] = f"{s3_front}{snapshot_path}{filename}.png"
    else:
        report_files["SpO2 Snapshot"] = "Null"
    return report_files

def generate_admin_fields(subject, session):
    # Calc date and time
    try:
        year = int(session[:4])
        month = int(session[4:6])
        day = int(session[6:8])
        hour = int(session[8:10])
        minute = int(session[10:12])
        second = int(session[12:])
        recording_date = date(year, month, day)
        start_time = time(hour, minute, second)
    except Exception as e:
        print(e)
        year = 2024
        month = 1
        day = 1
        hour = 0
        minute = 0
        second = 0
        recording_date = date(year, month, day)
        start_time = time(hour, minute, second)

    admin_fields = {
        "Subject_ID": str(subject),
        "Session_ID": str(session),
        "Date": recording_date,
        "Start Time": start_time,
    }
    return admin_fields

def calc_odi(events, time_seconds):
    if events==0 or time_seconds==0:
        return 0
    else:
        time_hours = time_seconds / 3600
        odi = events / time_hours
        return odi

def calc_T90(spo2_raw):
    mask = (spo2_raw["oxygen"] < 90)
    time_in_mask = mask.sum() / 60
    total_time_minutes = spo2_raw["time"].max()
    t90_perc = round((time_in_mask / total_time_minutes) * 100, 1)
    t90_min = round(time_in_mask/8, 1)
    return {"T90_perc": t90_perc, "T90_min": t90_min}

def calc_position_distribution(position_raw):
    # Ensure capital positions
    position_raw["position"] = position_raw["position"].str.upper()

    # Calculate duration spent in positions
    position_raw["duration"] = position_raw["time"].diff().shift(-1)  # Duration is difference between consecutive times
    position_raw.iloc[-1, position_raw.columns.get_loc("duration")] = 0

    # Aggregate time spent in each position
    position_time = position_raw.groupby("position")["duration"].sum() / 60

    total_time_minutes = position_raw["duration"].sum() / 60
    position_stats = {
        "supine_proportion": round(position_time.get("SUPINE", 0) / total_time_minutes, 3),
        "prone_proportion": round(position_time.get("PRONE", 0) / total_time_minutes, 3),
        "left_proportion": round(position_time.get("LEFT", 0) / total_time_minutes, 3),
        "right_proportion": round(position_time.get("RIGHT", 0) / total_time_minutes, 3),
        "upright_proportion": round(position_time.get("UPRIGHT", 0) / total_time_minutes, 3),
        "non_supine_proportion": round(100 - position_time.get("SUPINE", 0) / total_time_minutes, 3)
    }
    return position_stats


def generate_spo2_snapshot(
    spo2_df,
    output_path,
    plot_size=(8, 1.5),
    dpi=250,
    y_floor=60,
    y_ceiling=100,
    threshold=90,
):
    """
    Generates and saves an SpO2 snapshot PNG from spo2_df.

    Required columns: ['time', 'oxygen']
    """

    if not {"time", "oxygen"}.issubset(spo2_df.columns):
        raise ValueError("spo2_df must contain 'time' and 'oxygen' columns")

    if len(spo2_df[spo2_df["artifact"]==False]) == 0:
        print("Empty SpO2 dataframe, skipping snapshot generation.")
        return None

    spo2_df = spo2_df.dropna(subset=["oxygen", "time"])

    below_thresh = spo2_df[spo2_df["oxygen"] < threshold]

    fig, ax = plt.subplots(figsize=plot_size)

    ax.plot(
        spo2_df["time"],
        spo2_df["oxygen"],
        linewidth=1,
        label="SpO₂"
    )

    ax.scatter(
        below_thresh["time"],
        below_thresh["oxygen"],
        marker="v",
        s=60,
        color="red",
        label=f"SpO₂ < {threshold}"
    )

    ax.set_ylabel("SpO₂ (%)", fontsize=8)
    ax.set_ylim(y_floor, y_ceiling)
    ax.set_yticks(np.arange(y_floor, y_ceiling + 1, 10))
    ax.grid(True)
    ax.tick_params(labelsize=6)

    plt.tight_layout()
    plt.savefig(output_path, dpi=dpi)
    plt.close(fig)

    return "Snapshot saved"


def generate_metrics(s3, subject, session):
    """
    Orchestrate metric generation for single subject, session pair
    """
    admin = generate_admin_fields(subject, session)
    if admin["Date"] <= date(2025, 11, 20):
        return {**admin, "Duration (s)": 0}
    
    filename = f"zephyr_stereo_subj{subject}_sess{session}"
    # raw paths
    spo2_raw_path = f"zephyr/oxygen/{filename.replace('stereo', 'oxygen')}.csv"
    position_raw_path = f"zephyr/gravity/{filename.replace('stereo', 'gravity')}.csv"
    audio_raw_path = f"zephyr/stereo/{filename}.wav"

    # annot paths
    nst_annot_path = f"nst_annot/zephyr/oxygen/{filename}.csv"
    desat_annot_path_3 = f"desat_annot/zephyr/gravity/{filename.replace('stereo', 'oxygen')}_3p.csv"
    desat_annot_path_4 = f"desat_annot/zephyr/gravity/{filename.replace('stereo', 'oxygen')}.csv" 
    desat_annot_path_90 = f"desat_annot/zephyr/gravity/{filename.replace('stereo', 'oxygen')}_90.csv"   
  
    # Raw file reads
    try:
        spo2_raw, _ = s3.get_file_df(spo2_raw_path)
        spo2_raw.columns = spo2_raw.columns.str.strip().str.lower()
        if spo2_raw.empty:
            spo2_raw = pd.DataFrame([{
                "time": 0,
                "heartrate": 0,
                "oxygen": 0,
                "confidence": 0,
                "status": 0
            }])
        spo2_raw= spo2_raw.dropna(subset=['oxygen']).reset_index(drop=True)
    except Exception as e:
        print(f"Error reading {spo2_raw_path}: {e}")
        spo2_raw = pd.DataFrame([{
            "time": 0,
            "heartrate": 0,
            "oxygen": 0,
            "confidence": 0,
            "status": 0
        }])

    try:
        position_raw, _ = s3.get_file_df(position_raw_path)
        position_raw.columns = position_raw.columns.str.strip().str.lower()
        if position_raw.empty:
            position_raw = pd.DataFrame([{
                "time": 0,
                "x-axis": 0,
                "y-axis": 0,
                "z-axis": 0,
                "position": "UPRIGHT"
            }])
    except Exception as e:
        print(f"Error reading {position_raw_path}: {e}")
        position_raw = pd.DataFrame([{
                "time": 0,
                "x-axis": 0,
                "y-axis": 0,
                "z-axis": 0,
                "position": "UPRIGHT"
            }])
        
    # Duration
    try:
        audio_filename = s3.get_file_wav(audio_raw_path)
        audio_duration = wav_duration_seconds(audio_filename)
    except Exception as e:
        print(f"Error reading {audio_raw_path}: {e}")
        audio_duration = 0

    spo2_duration = spo2_raw['time'].max()
    position_duration = position_raw['time'].max()
    print(f"Durations - Audio: {audio_duration}, SpO2: {spo2_duration}, Position: {position_duration}")
    sleep_duration = max(audio_duration, spo2_duration, position_duration)

    # Early Exit
    if sleep_duration == 0:
        return {'Duration (s)': 0}

    # Interpolate SpO2 (for SpO2 metrics)
    spo2_raw = interpolate_spo2(spo2_raw, interp_window=30)

    # Generate SpO2 Snapshot
    img_path = f"snapshots/zephyr/stereo/zephyr_stereo_subj{subject}_sess{session}.png"
    snapshot_status = generate_spo2_snapshot(spo2_raw, img_path)

    if snapshot_status is not None: 
        s3.upload_file(
            file_name=img_path,
            upload_file_name=img_path,   # or different S3 key if you want
            content_type="image/png"
        )
        os.remove(img_path)

    # Annotation file reads
    annot_path_list = [nst_annot_path, desat_annot_path_3, desat_annot_path_4, desat_annot_path_90]
    annot_files = []
    for i, annot_file in enumerate(annot_path_list):
        try:
            annot_data = s3.get_file_df(annot_file)
        except:
            if i == 0:
                annot_data = pd.DataFrame([{"start": 0, "duration": 0}])
            elif i == 3: 
                annot_data = pd.DataFrame([
                    {
                        'Start': 0,
                        'End': 0,
                        'Duration(s)': 0,
                        'Min SpO2': 100,
                        'Artifact Proportion': 0,
                        'Hypoxic Burden 90(%-sec)': 0,
                        'Hypoxic Burden 90(%min/hr)': 0
                    }
                ])
            else:
                annot_data = pd.DataFrame([
                    {
                        'Start': 0,
                        'End': 0,
                        'Duration(s)': 0,
                        'Depth': 0,
                        'SpO2 Peak': 100,
                        'SpO2 Dip': 100,
                        'Hypoxic Burden(%-sec)': 0,
                        'Hypoxic Burden(%min/hr)': 0,
                        'Hypoxic Burden 90(%-sec)': 0,
                        'Hypoxic Burden 90(%min/hr)': 0,
                        'Threshold': 0
                    }
                ])
        annot_files.append(annot_data)
    nst_annot, desat_annot_3, desat_annot_4, desat_annot_90 = annot_files

    # Event Counts
    nst_count = len(nst_annot)
    desat_count_3 = len(desat_annot_3)
    desat_count_4 = len(desat_annot_4)
    desat_count_90 = len(desat_annot_90)

    # ODI
    odi = calc_odi(nst_count, sleep_duration)

    # Hypoxic Burden
    hypox_burden = desat_annot_4.loc[:,"Hypoxic Burden(%-sec)"].sum()/60

    # Position Distribution
    position_distribution = calc_position_distribution(position_raw)

    # SpO2 Metrics
    min_spo2 = round(spo2_raw["oxygen"][spo2_raw["oxygen"] > 0].min(), 1)
    t90 = calc_T90(spo2_raw)
    spo2_metrics = {"Min SpO2": min_spo2, **t90}

    # File Fields
    file_fields = generate_file_field_paths(subject, session, snapshot_status)

    base_metrics = {
        "Duration (s)": sleep_duration,
        "ODI": odi,
        "NST Count": nst_count,
        "Desat Count (3%)": desat_count_3,
        "Desat Count (4%)": desat_count_4,
        "Desat Count (sub 90%)": desat_count_90,
        "Hypoxic Burden (4%)": hypox_burden,
    }
    
    row = {
        **admin,
        **base_metrics, 
        **spo2_metrics, 
        **position_distribution,
        **file_fields
    }

    return row

def generate_missing(s3, subject, session, duration):

    admin = generate_admin_fields(subject, session)
    # annot paths
    filename = f"zephyr_stereo_subj{subject}_sess{session}"
    nst_annot_path = f"nst_annot/zephyr/stereo/{filename}.csv"
    desat_annot_path_3 = f"desat_annot/zephyr/stereo/{filename.replace('stereo', 'oxygen')}_3p.csv"
    desat_annot_path_4 = f"desat_annot/zephyr/stereo/{filename.replace('stereo', 'oxygen')}.csv" 
    desat_annot_path_90 = f"desat_annot/zephyr/stereo/{filename.replace('stereo', 'oxygen')}_90.csv"   
  

    # Annotation file reads
    annot_path_list = [nst_annot_path, desat_annot_path_3, desat_annot_path_4, desat_annot_path_90]
    annot_files = []
    for i, annot_file in enumerate(annot_path_list):
        try:
            annot_data, _ = s3.get_file_df(annot_file)
        except:
            print("failed to read annot file:", annot_file)
            annot_data = pd.DataFrame()
        annot_files.append(annot_data)
    nst_annot, desat_annot_3, desat_annot_4, desat_annot_90 = annot_files

    # Event Counts
    nst_count = len(nst_annot)
    desat_count_3 = len(desat_annot_3)
    desat_count_4 = len(desat_annot_4)
    desat_count_90 = len(desat_annot_90)

    # ODI
    odi = round(calc_odi(nst_count, duration), 1)

    # Hypoxic Burden
    try:
        hypox_burden = round(desat_annot_4.loc[:,"Hypoxic Burden(%-sec)"].sum()/60, 1)
    except:
        hypox_burden = 0

    dictionary = {
        "ODI": odi,
        "NST Count": nst_count,
        "Desat Count (3%)": desat_count_3,
        "Desat Count (4%)": desat_count_4,
        "Desat Count (sub 90%)": desat_count_90,
        "Hypoxic Burden (4%)": hypox_burden,
    }
    result = {**admin, **dictionary}

    return result

if __name__ == "__main__":
    prefix = "nst_annot/zephyr/stereo"
    BUCKET_NAME = "zephyrapptestbucket"
    s3 = S3Client(
        ACCESS_KEY=ACCESS_KEY, SECRET_KEY=SECRET_KEY, BUCKET_NAME=BUCKET_NAME
    )

    ids = s3.get_subject_session_ids(prefix)
    # with open("ids.json", "w") as file:
    #     json.dump(ids, file, indent=4)

    generated_id = pd.read_csv("zephyr_stereo_metadata_int_m.csv", dtype={"Subject_ID": str, "Session_ID": str})
    generated = pd.read_csv("zephyr_stereo_metadata.csv", dtype={"Subject_ID": str, "Session_ID": str})

    metadata_rows = []
    
    i = 0
    for subject, session in ids[i:]:
        print(f"Subject: {subject}, Session: {session}")

        if (str(subject), str(session)) not in zip(generated_id["Subject_ID"], generated_id["Session_ID"]):
            continue
        else:
            print("running")

        generated_row = generated[
            (generated["Subject_ID"] == str(subject)) & 
            (generated["Session_ID"] == str(session))
        ]
        # duration = generated_row["Duration (s)"].values[0]
        # print("duration:", duration)
        spo2_status = generated_row["SpO2 Snapshot"].values
        # print("spo2_status:", spo2_status)
        if len(spo2_status) > 0:
            if spo2_status[0] != "Null":
                spo2_status = "Pass"
            else:
                spo2_status = None
        else:
            spo2_status = None

        # row = generate_metrics(s3, subject, session)
        # row = generate_missing(s3, subject, session, duration=duration)
        row = generate_file_field_paths(subject, session, spo2_status)
        # if row["Duration (s)"] == 0:
        #     continue

        print("Generated Row:", row)
        metadata_rows.append(row)
        i += 1
        if i % 100 == 0:
            print(f"Processed {i} subjects/sessions")
            # Save intermediate results
            intermediate_df = pd.DataFrame(metadata_rows)
            intermediate_df.to_csv(f"zephyr_stereo_metadata_int_{i}.csv", index=False)

    metadata_df = pd.DataFrame(metadata_rows)
    metadata_df.to_csv("zephyr_stereo_metadata_int_links.csv", index=False)