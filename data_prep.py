"""
data_prep.py  -  Cleaning & preprocessing for the Ola Ride Insights project
Run directly to create  ola_cleaned.csv :   python data_prep.py
"""
import pandas as pd
import numpy as np

RAW_FILE = "OLA_DataSet.xlsx"
CLEAN_FILE = "ola_cleaned.csv"


def clean_data(raw_file: str = RAW_FILE) -> pd.DataFrame:
    df = pd.read_excel(raw_file, sheet_name="July")

    # 1. Standardise column names (no spaces)
    df.columns = df.columns.str.strip().str.replace(" ", "_")

    # 2. Remove duplicates (Booking_ID must be unique)
    df = df.drop_duplicates(subset="Booking_ID")

    # 3. Fix data types
    df["Date"] = pd.to_datetime(df["Date"])
    df["Time"] = df["Time"].astype(str)                       # HH:MM:SS
    df["Hour"] = pd.to_datetime(df["Time"], format="%H:%M:%S").dt.hour

    # 4. Strip whitespace in text columns
    text_cols = df.select_dtypes(include=["object", "string"]).columns
    for c in text_cols:
        df[c] = df[c].astype("string").str.strip()

    # 5. Missing values
    #    - NaN in V_TAT / C_TAT / ratings / payment method / incomplete flag are
    #      *structural*: they only exist for completed (Success) rides.
    #      They are kept as NULL (not filled with 0) so averages stay correct.
    #    - Ride_Distance = 0 for non-completed rides -> treat as NULL as well.
    df.loc[df["Booking_Status"] != "Success", "Ride_Distance"] = np.nan

    # 6. Derived features
    df["Day"] = df["Date"].dt.day
    df["Day_Name"] = df["Date"].dt.day_name()
    df["Week"] = df["Date"].dt.isocalendar().week.astype(int)
    df["Is_Weekend"] = df["Date"].dt.dayofweek >= 5
    df["Time_Slot"] = pd.cut(
        df["Hour"], bins=[-1, 5, 11, 16, 20, 23],
        labels=["Night (0-5)", "Morning (6-11)", "Afternoon (12-16)",
                "Evening (17-20)", "Late Night (21-23)"])
    df["Time_Slot"] = df["Time_Slot"].astype(str)

    # 7. Drop the image-url column (kept in a lookup dict for the app instead)
    df = df.drop(columns=["Vehicle_Images"], errors="ignore")

    # SQL-friendly date string
    df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
    return df.reset_index(drop=True)


def vehicle_images(raw_file: str = RAW_FILE) -> dict:
    """Vehicle_Type -> icon url, from Sheet2 of the workbook."""
    s = pd.read_excel(raw_file, sheet_name="Sheet2", header=None).dropna()
    return dict(zip(s[0], s[1]))


if __name__ == "__main__":
    data = clean_data()
    data.to_csv(CLEAN_FILE, index=False)
    print("Saved", CLEAN_FILE, data.shape)
    print(data.isna().sum())
