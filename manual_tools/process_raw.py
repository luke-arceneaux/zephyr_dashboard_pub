import numpy as np
import pandas as pd
from scipy.signal import butter, filtfilt
from wave import open as open_wave

def wav_duration_seconds(wav_file):
    with open_wave(wav_file, "rb") as wf:
        nframes = wf.getnframes()
        sample_rate = wf.getframerate()
        return nframes / sample_rate
    
def interpolate_segments(df, max_sec=5): 
        max_length = max_sec * 8 #8Hz
        mask = df["artifact"].to_numpy()
        spo2_values = df["oxygen"].copy()
        if "heartrate" in df.columns:
            hr_values = df["heartrate"].copy()

        i = 0
        while i < len(mask):
            if mask[i]:  # Found a True segment
                start = i
                while i < len(mask) and mask[i]:  # Find the end of the True segment
                    i += 1
                
                left_idx = start - 1
                right_idx = i
                
                # Heart Rate Interpolation (No max length)
                if "heartrate" in df.columns:
                    if 0 <= left_idx < len(hr_values) and right_idx < len(hr_values):
                        x = [left_idx, right_idx]
                        y = [hr_values.iloc[left_idx], hr_values.iloc[right_idx]]
                        interp_values = np.interp(range(start, i), x, y)
                        hr_values.iloc[start:i] = interp_values
                    else:
                        # can't interpolate, so skip
                        pass 
                
                
                length = i - start
                # SpO2 Interpolation (max_length)
                if length <= max_length:
                    if 0 <= left_idx < len(spo2_values) and right_idx < len(spo2_values):
                        x = [left_idx, right_idx]
                        y = [spo2_values.iloc[left_idx], spo2_values.iloc[right_idx]]
                        interp_values = np.interp(range(start, i), x, y)
                        spo2_values.iloc[start:i] = interp_values
                        df["artifact"].iloc[start:i] = False
                    else:
                        # can't interpolate, so skip
                        pass 

            else:
                i += 1

        df["oxygen"] = spo2_values
        if "heartrate" in df.columns:
            df["heartrate"] = hr_values
        return df


def get_sample_rate(df):
    sample_rate = int(1 / (df.iloc[1]["time"] - df.iloc[0]["time"]))
    return sample_rate

def get_sample_rate_series(series):
    sample_rate = int(1 / (series.index[1] - series.index[0]))
    return sample_rate

def butterworth_filter(data, cutoff=1, order=4, pass_type="high"):
    print("-------------------SpO2 Butterworth Filter---------------------")
    sr = get_sample_rate_series(data)  # spo2 sample rate
    print(f"Sample Rate: {sr} Hz")
    nyquist = 0.5 * sr/2  # Nyquist frequency, spo2 sample rate
    normal_cutoff = cutoff / nyquist  # Normalize cutoff frequency
    b, a = butter(order, normal_cutoff, btype=pass_type, analog=False)
    return filtfilt(b, a, data)

if __name__ == "__main__":
    # old = pd.read_csv("zephyr_stereo_metadata_0.csv", dtype={"Session_ID": str})
    # new = pd.read_csv("zephyr_stereo_metadata_int.csv", dtype={"Session_ID": str})
    # new_id = pd.read_csv("zephyr_stereo_metadata_int_m.csv", dtype={"Session_ID": str})

    # new["Session_ID"] = new_id["Session_ID"].astype(str)
    # file = pd.concat([old, new], ignore_index=True)

    # file.to_csv("zephyr_stereo_metadata_fixed.csv", index=False)

    old = pd.read_csv("../session_metadata.csv", dtype={"Session_ID": str})
    old['version'] = 1.0
    old.to_csv("../session_metadata_v1.csv", index=False)