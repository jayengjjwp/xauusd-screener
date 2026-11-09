import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

st.set_page_config(
    page_title="XAUUSD BBMA Oma Ally Screener", layout="wide"
)

st.title("⚡ XAUUSD BBMA Oma Ally - Valid Setup & Re-Entry Screener")
st.markdown("---")


@st.cache_data(ttl=60)
def get_xauusd_data():
  try:
    df = yf.download("GC=F", period="5d", interval="1h", progress=False)
    if df.empty:
      df = yf.download(
          "XAUUSD=X", period="5d", interval="1h", progress=False
      )
    return df
  except Exception as e:
    return pd.DataFrame()


raw_data = get_xauusd_data()

if raw_data.empty:
  st.error("Gagal mengambil data live feed XAUUSD saat ini.")
else:
  if isinstance(raw_data.columns, pd.MultiIndex):
    df = pd.DataFrame()
    df["Open"] = raw_data["Open"].iloc[:, 0]
    df["High"] = raw_data["High"].iloc[:, 0]
    df["Low"] = raw_data["Low"].iloc[:, 0]
    df["Close"] = raw_data["Close"].iloc[:, 0]
  else:
    df = raw_data.copy()

  # Kalkulasi Indikator BBMA Oma Ally (Bollinger Bands 20,2 & MA 5/10)
  df["MA20"] = df["Close"].rolling(window=20).mean()
  df["STD"] = df["Close"].rolling(window=20).std()
  df["TopBB"] = df["MA20"] + (df["STD"] * 2)
  df["BottomBB"] = df["MA20"] - (df["STD"] * 2)
  df["MA5_High"] = df["High"].rolling(window=5).mean()
  df["MA5_Low"] = df["Low"].rolling(window=5).mean()

  df = df.dropna()

  if len(df) > 0:
    latest = df.iloc[-1]
    prev = df.iloc[-2]

    current_price = float(latest["Close"])
    top_bb = float(latest["TopBB"])
    bot_bb = float(latest["BottomBB"])
    mid_bb = float(latest["MA20"])
    ma5_h = float(latest["MA5_High"])
    ma5_l = float(latest["MA5_Low"])

    # Logika Deteksi Status BBMA yang Diminta
    setup_status = "WAIT & SEE (Belum Valid untuk Entry)"
    action_signal = "PANTAU / JANGAN MASUK"
    entry_zone = f"${current_price:,.2f}"
    sl = 0.0
    tp = 0.0
    keterangan = (
        "Harga berada di area tengah (Mid BB). Belum ada sentuhan ekstrem."
    )

    # Deteksi Re-Entry Sell / Extreme di Atas
    if (
        current_price >= top_bb * 0.995
        or latest["High"] >= top_bb
        or prev["High"] >= prev["TopBB"]
    ):
      setup_status = "VALID RE-ENTRY SELL / EXTREME"
      action_signal = "SELL (Cari Konfirmasi M15)"
      entry_zone = f"${top_bb - 2.0:,.2f} - ${top_bb:,.2f}"
      sl = round(top_bb + 4.0, 2)
      tp = round(mid_bb, 2)
      keterangan = (
          "Harga menguji Top BB. Valid untuk skenario Re-Entry Sell / Menunggu"
          " Penolakan."
      )

    # Deteksi Re-Entry Buy / Extreme di Bawah
    elif (
        current_price <= bot_bb * 1.005
        or latest["Low"] <= bot_bb
        or prev["Low"] <= prev["BottomBB"]
    ):
      setup_status = "VALID RE-ENTRY BUY / EXTREME"
      action_signal = "BUY (Cari Konfirmasi M15)"
      entry_zone = f"${bot_bb:,.2f} - ${bot_bb + 2.0:,.2f}"
      sl = round(bot_bb - 4.0, 2)
      tp = round(mid_bb, 2)
      keterangan = (
          "Harga menguji Bottom BB. Valid untuk skenario Re-Entry Buy / Menunggu"
          " Penolakan."
      )

    # Jika di atas Mid BB tapi belum sampai Top
    elif current_price > mid_bb:
      setup_status = "WAIT & SEE (Kecenderungan Naik)"
      action_signal = "TUNGGU RETRACEMENT KE MA5/10 LOW"
      entry_zone = f"${ma5_l:,.2f} - ${mid_bb:,.2f}"
      sl = round(bot_bb - 3.0, 2)
      tp = round(top_bb - 3.0, 2)
      keterangan = (
          "Market bullish di atas Mid BB. Tunggu harga turun mendekati MA5/10"
          " Low untuk Re-Entry Buy."
      )

    # Jika di bawah Mid BB tapi belum sampai Bottom
    else:
      setup_status = "WAIT & SEE (Kecenderungan Turun)"
      action_signal = "TUNGGU RETRACEMENT KE MA5/10 HIGH"
      entry_zone = f"${mid_bb:,.2f} - ${ma5_h:,.2f}"
      sl = round(top_bb + 3.0, 2)
      tp = round(bot_bb + 3.0, 2)
      keterangan = (
          "Market bearish di bawah Mid BB. Tunggu harga naik mendekati MA5/10"
          " High untuk Re-Entry Sell."
      )

    # Layout Metrik di Streamlit
    col1, col2, col3 = st.columns(3)
    col1.metric("Live XAUUSD Price", f"${current_price:,.2f}")
    col2.metric("Status Market BBMA", setup_status)
    col3.metric("Saran Aksi", action_signal)

    st.markdown(
        "### 📋 Tabel Validasi Setup, Zona Entry, SL, dan Take Profit"
    )

    df_display = pd.DataFrame([
        {
            "Timeframe": "H1 Intraday",
            "Status Setup": setup_status,
            "Saran Aksi": action_signal,
            "Zona Harga Entry": entry_zone,
            "Stop Loss (SL)": f"${sl:,.2f}" if sl > 0 else "-",
            "Take Profit (TP)": f"${tp:,.2f}" if tp > 0 else "-",
            "Keterangan Aturan": keterangan,
        }
    ])

    st.dataframe(df_display, use_container_width=True)

    st.markdown("### 📊 Acuan Batas Bollinger Bands & Moving Average")
    b1, b2, b3, b4 = st.columns(4)
    b1.metric("Top Bollinger Band", f"${top_bb:,.2f}")
    b2.metric("Middle BB (MA20)", f"${mid_bb:,.2f}")
    b3.metric("Bottom Bollinger Band", f"${bot_bb:,.2f}")
    b4.metric("MA5 High / Low", f"${ma5_h:,.2f} / ${ma5_l:,.2f}")

    st.info(
        "💡 **Tips Disiplin:** Jangan memaksakan entry jika status web masih"
        " menunjukkan **Wait & See**. Eksekusi hanya dilakukan jika status"
        " berubah menjadi **Valid Re-Entry Buy/Sell**."
    )
  else:
    st.warning("Data historis tidak mencukupi.")
