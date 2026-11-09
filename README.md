# Ola Ride Insights

## Files
- data_prep.py     : cleaning + feature engineering (creates ola_cleaned.csv)
- sql_queries.sql  : the 10 SQL questions (MySQL / SQLite compatible)
- app.py           : Streamlit app (dashboards, SQL page, Power BI embed, data explorer)
- requirements.txt

## Run locally
    pip install -r requirements.txt
    python data_prep.py          # creates ola_cleaned.csv
    streamlit run app.py

## Deploy on Streamlit Community Cloud
1. Push app.py, data_prep.py, requirements.txt, ola_cleaned.csv (and OLA_DataSet.xlsx if you want vehicle icons) to a GitHub repo.
2. Go to share.streamlit.io > New app > pick the repo, branch, main file = app.py > Deploy.
3. (Optional) App settings > Secrets:  POWERBI_URL = "https://app.powerbi.com/view?r=..."
