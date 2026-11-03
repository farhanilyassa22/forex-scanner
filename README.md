# Forex Scanner
Streamlit Forex technical scanner using Twelve Data.

## Setup
Install: `pip install -r requirements.txt`
Create `.streamlit/secrets.toml` with:
`TWELVE_DATA_API_KEY = "YOUR_API_KEY"`
Run: `streamlit run app.py`

For Streamlit Cloud, add the same key under App settings → Secrets.
Signals are heuristic. Verify candle timestamp, spread, and execution conditions.
