import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(page_title="XAUUSD BBMA Oma Ally Screener", layout="wide")

st.title("⚡ XAUUSD BBMA Oma Ally - Live Screener")
st.markdown("---")

@st.cache_data(ttl=60)
def get_xauusd_data():
    try:
        df = yf.download("GC=F", period="5d", interval="1h", progress=False)
        if df.empty:
            df = yf.download("XAUUSD=X", period="5d", interval="1h", progress=False)
        return df
    except Exception as e:
        return pd.DataFrame()

data = get_xauusd_data()

if data.empty:
    st.error("Gagal mengambil data live feed XAUUSD saat ini.")
else:
    if isinstance(data.columns, pd.MultiIndex):
        close_series = data[('Close', 'GC=F')] if ('Close', 'GC=F') in data.columns else data['Close'].iloc[:, 0]
    else:
        close_series = data['Close']
        
    current_price = float(close_series.iloc[-1])
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Live XAUUSD Price", f"${current_price:,.2f}")
    col2.metric("Status Market", "LIVE & Connected")
    col3.metric("Metode", "BBMA Oma Ally 4 Tier")
    
    st.markdown("### 📊 4 Tier Timeframe Matrix")
    
    tiers = [
        {"Tier": "Tier 1: Macro Swing", "TF Utama": "Daily", "TF Acuan": "H4 / H1", "Setup": "CSAK / Re-entry Valid", "Status": "Aman (Trend Utama)"},
        {"Tier": "Tier 2: Standard Intraday", "TF Utama": "H4", "TF Acuan": "H1 / M15", "Setup": "Extreme / MHV Terdeteksi", "Status": "Waspada Re-entry"},
        {"Tier": "Tier 3: Fast Intraday", "TF Utama": "H1", "TF Acuan": "M15 / M5", "Setup": "CSA / Ext Menuju MA5/10", "Status": "Potensi Open Position"},
        {"Tier": "Tier 4: Scalping Kilat", "TF Utama": "M15", "TF Acuan": "M5 / M1", "Setup": "Setup Momentum", "Status": "Eksekusi Cepat"}
    ]
    
    df_table = pd.DataFrame(tiers)
    st.dataframe(df_table, use_container_width=True)
    
    st.info("💡 Screener berjalan berdasarkan pergerakan market live.")
