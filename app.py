"""
Ola Ride Insights - Streamlit App
Run locally :  streamlit run app.py
"""
import os
import re
import sqlite3

import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components

from data_prep import CLEAN_FILE, RAW_FILE, clean_data, vehicle_images

st.set_page_config(page_title="Ola Ride Insights", page_icon="🚖", layout="wide")

# ---------------------------------------------------------------- DATA
@st.cache_data(show_spinner="Loading data...")
def load_data() -> pd.DataFrame:
    if os.path.exists(CLEAN_FILE):
        df = pd.read_csv(CLEAN_FILE)
    else:                                   # fall back to cleaning the raw file
        df = clean_data(RAW_FILE)
    df["Date"] = pd.to_datetime(df["Date"])
    return df


@st.cache_data
def load_icons() -> dict:
    try:
        return vehicle_images(RAW_FILE)
    except Exception:
        return {}


@st.cache_resource
def get_connection() -> sqlite3.Connection:
    """In-memory SQLite DB with the *full* cleaned table (for the SQL page)."""
    con = sqlite3.connect(":memory:", check_same_thread=False)
    full = load_data().copy()
    full["Date"] = full["Date"].dt.strftime("%Y-%m-%d")
    full.to_sql("ola_rides", con, index=False, if_exists="replace")
    return con


def run_sql(query: str) -> pd.DataFrame:
    return pd.read_sql_query(query, get_connection())


df_all = load_data()

# ------------------------------------------------------------- SIDEBAR
st.sidebar.title("🚖 Ola Ride Insights")
page = st.sidebar.radio(
    "Navigate",
    ["Overall", "Vehicle Type", "Revenue", "Cancellation", "Ratings",
     "SQL Insights", "Power BI Dashboard", "Data Explorer"],
)

st.sidebar.markdown("---")
st.sidebar.subheader("Filters")
min_d, max_d = df_all["Date"].min().date(), df_all["Date"].max().date()
date_range = st.sidebar.date_input("Date range", (min_d, max_d), min_d, max_d)
vehicles = st.sidebar.multiselect(
    "Vehicle type", sorted(df_all["Vehicle_Type"].unique()),
    default=sorted(df_all["Vehicle_Type"].unique()))
statuses = st.sidebar.multiselect(
    "Booking status", sorted(df_all["Booking_Status"].unique()),
    default=sorted(df_all["Booking_Status"].unique()))

if isinstance(date_range, tuple) and len(date_range) == 2:
    start, end = date_range
else:
    start = end = date_range[0] if isinstance(date_range, tuple) else date_range

df = df_all[
    df_all["Date"].between(pd.Timestamp(start), pd.Timestamp(end))
    & df_all["Vehicle_Type"].isin(vehicles)
    & df_all["Booking_Status"].isin(statuses)
]
success = df[df["Booking_Status"] == "Success"]

SQL_PAGES = {"SQL Insights", "Power BI Dashboard"}
if page not in SQL_PAGES:
    st.sidebar.caption(f"{len(df):,} of {len(df_all):,} bookings selected")
if df.empty and page not in SQL_PAGES:
    st.warning("No data for the selected filters.")
    st.stop()


def kpi_row(items):
    for col, (label, value) in zip(st.columns(len(items)), items):
        col.metric(label, value)


# ------------------------------------------------------------- PAGES
if page == "Overall":
    st.title("📊 Overall Summary")
    kpi_row([
        ("Total Bookings", f"{len(df):,}"),
        ("Successful Rides", f"{len(success):,}"),
        ("Success Rate", f"{len(success) / len(df):.1%}"),
        ("Revenue (Success)", f"₹{success['Booking_Value'].sum():,.0f}"),
        ("Avg Distance", f"{success['Ride_Distance'].mean():.1f} km"),
    ])

    st.subheader("Ride Volume Over Time")
    daily = df.groupby("Date").size().reset_index(name="Rides")
    st.plotly_chart(px.line(daily, x="Date", y="Rides", markers=True),
                    use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Booking Status Breakdown")
        s = df["Booking_Status"].value_counts().reset_index()
        s.columns = ["Booking_Status", "Count"]
        st.plotly_chart(px.pie(s, names="Booking_Status", values="Count", hole=0.45),
                        use_container_width=True)
    with c2:
        st.subheader("Peak Demand Hours")
        h = df.groupby("Hour").size().reset_index(name="Rides")
        st.plotly_chart(px.bar(h, x="Hour", y="Rides"), use_container_width=True)

    st.subheader("Demand Heatmap (Day of week x Hour)")
    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    heat = df.pivot_table(index="Day_Name", columns="Hour", values="Booking_ID",
                          aggfunc="count").reindex(order)
    st.plotly_chart(px.imshow(heat, aspect="auto", color_continuous_scale="YlOrRd"),
                    use_container_width=True)

elif page == "Vehicle Type":
    st.title("🚗 Vehicle Type Analysis")
    icons = load_icons()
    if icons:
        cols = st.columns(len(icons))
        for col, (name, url) in zip(cols, icons.items()):
            col.image(url, width=48)
            col.caption(name)

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Top 5 Vehicle Types by Ride Distance")
        d = (success.groupby("Vehicle_Type")["Ride_Distance"].sum()
             .nlargest(5).reset_index())
        st.plotly_chart(px.bar(d, x="Vehicle_Type", y="Ride_Distance",
                               text_auto=".3s", color="Vehicle_Type"),
                        use_container_width=True)
    with c2:
        st.subheader("Average Ride Distance by Vehicle")
        d = success.groupby("Vehicle_Type")["Ride_Distance"].mean().reset_index()
        st.plotly_chart(px.bar(d, x="Vehicle_Type", y="Ride_Distance",
                               text_auto=".1f", color="Vehicle_Type"),
                        use_container_width=True)

    st.subheader("Bookings by Vehicle and Status")
    d = df.groupby(["Vehicle_Type", "Booking_Status"]).size().reset_index(name="Count")
    st.plotly_chart(px.bar(d, x="Vehicle_Type", y="Count", color="Booking_Status",
                           barmode="stack"), use_container_width=True)

elif page == "Revenue":
    st.title("💰 Revenue Analysis")
    kpi_row([
        ("Total Revenue", f"₹{success['Booking_Value'].sum():,.0f}"),
        ("Avg Booking Value", f"₹{success['Booking_Value'].mean():,.0f}"),
        ("Revenue / km", f"₹{success['Booking_Value'].sum() / success['Ride_Distance'].sum():,.2f}"),
    ])
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Revenue by Payment Method")
        d = success.groupby("Payment_Method")["Booking_Value"].sum().reset_index()
        st.plotly_chart(px.pie(d, names="Payment_Method", values="Booking_Value", hole=0.4),
                        use_container_width=True)
    with c2:
        st.subheader("Top 5 Customers by Total Booking Value")
        d = (success.groupby("Customer_ID")["Booking_Value"].sum()
             .nlargest(5).reset_index())
        st.plotly_chart(px.bar(d, x="Customer_ID", y="Booking_Value", text_auto=True),
                        use_container_width=True)

    st.subheader("Ride Distance Distribution Per Day")
    d = success.groupby("Date")["Ride_Distance"].sum().reset_index()
    st.plotly_chart(px.bar(d, x="Date", y="Ride_Distance"), use_container_width=True)

    st.subheader("Daily Revenue")
    d = success.groupby("Date")["Booking_Value"].sum().reset_index()
    st.plotly_chart(px.line(d, x="Date", y="Booking_Value", markers=True),
                    use_container_width=True)

elif page == "Cancellation":
    st.title("❌ Cancellation Analysis")
    canc_c = df[df["Booking_Status"] == "Canceled by Customer"]
    canc_d = df[df["Booking_Status"] == "Canceled by Driver"]
    kpi_row([
        ("Cancelled by Customer", f"{len(canc_c):,}"),
        ("Cancelled by Driver", f"{len(canc_d):,}"),
        ("Driver Not Found", f"{(df['Booking_Status'] == 'Driver Not Found').sum():,}"),
        ("Cancellation Rate",
         f"{(len(canc_c) + len(canc_d)) / len(df):.1%}"),
    ])
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Customer Cancellation Reasons")
        d = canc_c["Canceled_Rides_by_Customer"].value_counts().reset_index()
        d.columns = ["Reason", "Count"]
        st.plotly_chart(px.bar(d, x="Count", y="Reason", orientation="h", text_auto=True),
                        use_container_width=True)
    with c2:
        st.subheader("Driver Cancellation Reasons")
        d = canc_d["Canceled_Rides_by_Driver"].value_counts().reset_index()
        d.columns = ["Reason", "Count"]
        st.plotly_chart(px.bar(d, x="Count", y="Reason", orientation="h", text_auto=True),
                        use_container_width=True)

    st.subheader("Incomplete Ride Reasons")
    d = df["Incomplete_Rides_Reason"].dropna().value_counts().reset_index()
    d.columns = ["Reason", "Count"]
    if not d.empty:
        st.plotly_chart(px.pie(d, names="Reason", values="Count"), use_container_width=True)

elif page == "Ratings":
    st.title("⭐ Ratings Analysis")
    kpi_row([
        ("Avg Driver Rating", f"{success['Driver_Ratings'].mean():.2f}"),
        ("Avg Customer Rating", f"{success['Customer_Rating'].mean():.2f}"),
    ])
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Driver Ratings Distribution")
        st.plotly_chart(px.histogram(success, x="Driver_Ratings", nbins=20),
                        use_container_width=True)
    with c2:
        st.subheader("Customer Ratings Distribution")
        st.plotly_chart(px.histogram(success, x="Customer_Rating", nbins=20),
                        use_container_width=True)

    st.subheader("Average Ratings by Vehicle Type")
    d = (success.groupby("Vehicle_Type")[["Driver_Ratings", "Customer_Rating"]]
         .mean().reset_index().melt("Vehicle_Type", var_name="Type", value_name="Avg Rating"))
    st.plotly_chart(px.bar(d, x="Vehicle_Type", y="Avg Rating", color="Type",
                           barmode="group", range_y=[0, 5], text_auto=".2f"),
                    use_container_width=True)

    st.subheader("Customer vs Driver Ratings")
    sample = success.sample(min(5000, len(success)), random_state=1)
    st.plotly_chart(px.scatter(sample, x="Driver_Ratings", y="Customer_Rating",
                               color="Vehicle_Type", opacity=0.5),
                    use_container_width=True)

elif page == "SQL Insights":
    st.title("🧮 SQL Insights")
    st.caption("Queries run on the full cleaned dataset (table: `ola_rides`), "
               "independent of the sidebar filters.")

    QUERIES = {
        "1. All successful bookings":
            "SELECT * FROM ola_rides WHERE Booking_Status = 'Success'",
        "2. Average ride distance per vehicle type":
            "SELECT Vehicle_Type, ROUND(AVG(Ride_Distance),2) AS Avg_Ride_Distance "
            "FROM ola_rides WHERE Booking_Status='Success' GROUP BY Vehicle_Type "
            "ORDER BY Avg_Ride_Distance DESC",
        "3. Total rides cancelled by customers":
            "SELECT COUNT(*) AS Cancelled_By_Customer FROM ola_rides "
            "WHERE Booking_Status='Canceled by Customer'",
        "4. Top 5 customers by number of rides":
            "SELECT Customer_ID, COUNT(Booking_ID) AS Total_Rides FROM ola_rides "
            "GROUP BY Customer_ID ORDER BY Total_Rides DESC, Customer_ID LIMIT 5",
        "5. Driver cancellations: personal & car related issues":
            "SELECT COUNT(*) AS Driver_Cancel_Personal_Car_Issue FROM ola_rides "
            "WHERE Canceled_Rides_by_Driver='Personal & Car related issue'",
        "6. Max / min driver rating for Prime Sedan":
            "SELECT MAX(Driver_Ratings) AS Max_Driver_Rating, "
            "MIN(Driver_Ratings) AS Min_Driver_Rating FROM ola_rides "
            "WHERE Vehicle_Type='Prime Sedan' AND Driver_Ratings IS NOT NULL",
        "7. Rides paid using UPI":
            "SELECT * FROM ola_rides WHERE Payment_Method='UPI'",
        "8. Average customer rating per vehicle type":
            "SELECT Vehicle_Type, ROUND(AVG(Customer_Rating),2) AS Avg_Customer_Rating "
            "FROM ola_rides WHERE Customer_Rating IS NOT NULL GROUP BY Vehicle_Type "
            "ORDER BY Avg_Customer_Rating DESC",
        "9. Total booking value of successful rides":
            "SELECT SUM(Booking_Value) AS Total_Booking_Value FROM ola_rides "
            "WHERE Booking_Status='Success'",
        "10. Incomplete rides with reason":
            "SELECT Booking_ID, Customer_ID, Vehicle_Type, Incomplete_Rides, "
            "Incomplete_Rides_Reason FROM ola_rides WHERE Incomplete_Rides='Yes'",
    }

    choice = st.selectbox("Choose a question", list(QUERIES))
    st.code(QUERIES[choice], language="sql")
    result = run_sql(QUERIES[choice])
    st.write(f"**Result** ({len(result):,} rows)")
    st.dataframe(result.head(1000), use_container_width=True)
    st.download_button("Download result (CSV)", result.to_csv(index=False),
                       "query_result.csv", "text/csv")

    st.markdown("---")
    st.subheader("Write your own query")
    custom = st.text_area("SELECT-only SQL", "SELECT Vehicle_Type, COUNT(*) AS rides "
                          "FROM ola_rides GROUP BY Vehicle_Type", height=120)
    if st.button("Run query"):
        if not re.match(r"^\s*select\b", custom, re.I) or ";" in custom.strip().rstrip(";"):
            st.error("Only a single SELECT statement is allowed.")
        else:
            try:
                out = run_sql(custom)
                st.dataframe(out.head(1000), use_container_width=True)
            except Exception as e:
                st.error(f"Query error: {e}")

elif page == "Power BI Dashboard":
    st.title("📈 Power BI Dashboard")
    st.write("Publish your report in Power BI Service (**File > Embed report > "
             "Publish to web (public)**), then paste the embed URL below.")
    try:
        default_url = st.secrets["POWERBI_URL"]
    except Exception:
        default_url = ""
    url = st.text_input("Power BI embed URL", default_url,
                        placeholder="https://app.powerbi.com/view?r=...")
    if url.startswith("https://app.powerbi.com"):
        components.iframe(url, height=700, scrolling=True)
    else:
        st.info("Paste a valid https://app.powerbi.com/... link to display the dashboard.")

elif page == "Data Explorer":
    st.title("🔎 Data Explorer")
    q = st.text_input("Search (Booking ID, Customer ID, pickup or drop location)")
    view = df
    if q:
        mask = (view["Booking_ID"].str.contains(q, case=False, na=False)
                | view["Customer_ID"].str.contains(q, case=False, na=False)
                | view["Pickup_Location"].str.contains(q, case=False, na=False)
                | view["Drop_Location"].str.contains(q, case=False, na=False))
        view = view[mask]
    st.write(f"{len(view):,} rows")
    st.dataframe(view.head(2000), use_container_width=True)
    st.download_button("Download filtered data (CSV)", view.to_csv(index=False),
                       "ola_filtered.csv", "text/csv")
