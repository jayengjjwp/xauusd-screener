from datetime import datetime
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

# Konfigurasi Halaman
st.set_page_config(
    page_title="XAUUSD BBMA Fuji V7 Pro Screener", page_icon="⚡", layout="wide"
)

st.title(
    "⚡ XAUUSD BBMA Fuji V7 Pro - Multi-Timeframe Screener & Risk Calculator"
)
st.markdown(
    f"📅 **Waktu Akses:** {datetime.now().strftime('%A, %d %B %Y - %H:%M')} WIB | "
    "Sistem otomatis mereplikasi logika persis dari **BBMA Fuji V7 (Oma Ally)**."
)


# -----------------------------------------------------------------
# 1. SIDEBAR PENGATURAN SISTEM
# -----------------------------------------------------------------
st.sidebar.header("⚙️ Konfigurasi Sistem Pro")

tf_package = st.sidebar.selectbox(
    "Pilih Paket Hierarki Timeframe",
    ["D1 - H4 - H1", "H4 - H1 - M15", "M15 - M5 - M1"],
    index=0,
)

if tf_package == "D1 - H4 - H1":
  tf_high, tf_mid, tf_exec = "1d", "4h", "1h"
elif tf_package == "H4 - H1 - M15":
  tf_high, tf_mid, tf_exec = "4h", "1h", "15m"
else:
  tf_high, tf_mid, tf_exec = "15m", "5m", "1m"

# Sidebar Risk Management
st.sidebar.markdown("---")
st.sidebar.header("🛡️ Money Management Settings")
balance = st.sidebar.number_input(
    "Modal Akun ($)", min_value=10.0, value=1000.0, step=100.0
)
risk_pct = st.sidebar.slider(
    "Risiko per Trade (%)", min_value=0.5, max_value=5.0, value=1.0, step=0.5
)
risk_amount = balance * (risk_pct / 100.0)
st.sidebar.info(f"💵 Batas Toleransi Risiko: **${risk_amount:,.2f}**")


# -----------------------------------------------------------------
# 2. FUNGSI PERHITUNGAN INDIKATOR BBMA FUJI V7 (PINE SCRIPT PORT)
# -----------------------------------------------------------------
def calculate_wma(series, length):
  weights = np.arange(1, length + 1)
  return series.rolling(length).apply(
      lambda x: np.dot(x, weights) / weights.sum(), raw=True
  )


@st.cache_data(ttl=60)
def fetch_tf_data(interval, period="1y"):
  tickers = ["GC=F", "XAUUSD=X", "GLD"]
  for ticker in tickers:
    try:
      df = yf.download(
          ticker, period=period, interval=interval, progress=False
      )
      if not df.empty:
        if isinstance(df.columns, pd.MultiIndex):
          clean_df = pd.DataFrame()
          clean_df["Open"] = df["Open"].iloc[:, 0]
          clean_df["High"] = df["High"].iloc[:, 0]
          clean_df["Low"] = df["Low"].iloc[:, 0]
          clean_df["Close"] = df["Close"].iloc[:, 0]
          df = clean_df
        df = df.dropna(subset=["Open", "High", "Low", "Close"])
        if not df.empty:
          return calculate_bbma_fuji(df)
    except Exception:
      continue
  return pd.DataFrame()


def calculate_bbma_fuji(df):
  if df.empty or len(df) < 50:
    return df
  df = df.copy()

  # Bollinger Bands (Length 20, Mult 2)
  BBlength = 20
  BBdev = 2.0
  df["midBB"] = df["Close"].rolling(window=BBlength).mean()
  stdev = df["Close"].rolling(window=BBlength).std()
  df["topBB"] = df["midBB"] + (BBdev * stdev)
  df["lowBB"] = df["midBB"] - (BBdev * stdev)

  # WMA sesuai script Fuji V7
  df["mahi5"] = calculate_wma(df["High"], 5)
  df["mahi10"] = calculate_wma(df["High"], 10)
  df["malo5"] = calculate_wma(df["Low"], 5)
  df["malo10"] = calculate_wma(df["Low"], 10)
  df["ema50"] = df["Close"].ewm(span=50, adjust=False).mean()

  # Shift untuk data sebelumnya ([1])
  df["mahi5_p"] = df["mahi5"].shift(1)
  df["malo5_p"] = df["malo5"].shift(1)
  df["topBB_p"] = df["topBB"].shift(1)
  df["lowBB_p"] = df["lowBB"].shift(1)

  # --- PORTING LOGIKA SINYAL DARI PINE SCRIPT ---
  # 1. Extreme
  df["ext_sell"] = (df["Close"] < df["topBB"]) & (
      (df["mahi5_p"] > df["topBB"]) | (df["mahi5"] > df["topBB"])
  )
  df["ext_buy"] = (df["Close"] > df["lowBB"]) & (
      (df["malo5_p"] < df["lowBB"]) | (df["malo5"] < df["lowBB"])
  )

  # 2. CSM / Momentum (mmt) & CSMKuat (ali)
  df["mmt_sell"] = (df["Close"] < df["lowBB"]) & (df["Open"] > df["lowBB"])
  df["mmt_buy"] = (df["Close"] > df["topBB"]) & (df["Open"] < df["topBB"])
  df["ali_sell"] = (df["Open"] < df["lowBB"]) & (df["Close"] < df["lowBB"])
  df["ali_buy"] = (df["Open"] > df["topBB"]) & (df["Close"] > df["topBB"])

  # 3. MHV
  extreme_prev_sell = df["mahi5"].shift(1) > df["topBB"].shift(1)
  extreme_prev_buy = df["malo5"].shift(1) < df["lowBB"].shift(1)
  is_csm_sell = df["Close"] < df["lowBB"]
  is_csm_buy = df["Close"] > df["topBB"]
  df["mhv_sell"] = (
      extreme_prev_sell
      & (~is_csm_sell)
      & (df["High"] < df["topBB"])
      & (df["Close"] > df["midBB"])
  )
  df["mhv_buy"] = (
      extreme_prev_buy
      & (~is_csm_buy)
      & (df["Low"] > df["lowBB"])
      & (df["Close"] < df["midBB"])
  )

  # 4. CSAK
  df["csak_sell"] = (
      (df["Close"] < df["midBB"])
      & (df["Close"] < df["mahi5"])
      & (df["Close"] < df["mahi10"])
      & (df["Close"] < df["malo5"])
      & (df["Close"] < df["malo10"])
  )
  df["csak_buy"] = (
      (df["Close"] > df["midBB"])
      & (df["Close"] > df["mahi5"])
      & (df["Close"] > df["mahi10"])
      & (df["Close"] > df["malo5"])
      & (df["Close"] > df["malo10"])
  )

  # 5. Reentry (reject_mahi / reject_malo)
  df["reject_mahi"] = (
      (df["High"] > df["mahi5"])
      & (df["Close"] < df["mahi5"])
      & (df["Close"] < df["mahi10"])
      & (df["Close"] < df["midBB"])
      & (df["mahi5"] < df["midBB"])
  )
  df["reject_malo"] = (
      (df["Low"] < df["malo5"])
      & (df["Close"] > df["malo5"])
      & (df["Close"] > df["malo10"])
      & (df["Close"] > df["midBB"])
      & (df["malo5"] > df["midBB"])
  )

  return df


def resample_to_h4(df_h1):
  if df_h1.empty:
    return pd.DataFrame()
  df_h4 = df_h1.resample("4h").agg({
      "Open": "first",
      "High": "max",
      "Low": "min",
      "Close": "last",
  })
  return calculate_bbma_fuji(df_h4.dropna())


def analyze_tf_fuji(df, role_type="TF1"):
  if df.empty or len(df) < 50:
    return {
        "price": 0.0,
        "status": "DATA KURANG",
        "bias": "NEUTRAL",
        "top_bb": 0.0,
        "bot_bb": 0.0,
        "mid_bb": 0.0,
        "ema50": 0.0,
        "detail": "Data baris kurang dari minimum.",
    }

  latest = df.iloc[-1]
  c_price = float(latest["Close"])
  top_bb = float(latest["topBB"])
  bot_bb = float(latest["lowBB"])
  mid_bb = float(latest["midBB"])
  ema50 = float(latest["ema50"])

  # Ambil status boolean dari baris terakhir
  is_ext_sell = bool(latest["ext_sell"])
  is_ext_buy = bool(latest["ext_buy"])
  is_mhv_sell = bool(latest["mhv_sell"])
  is_mhv_buy = bool(latest["mhv_buy"])
  is_csak_sell = bool(latest["csak_sell"])
  is_csak_buy = bool(latest["csak_buy"])
  is_mmt_sell = bool(latest["mmt_sell"] or latest["ali_sell"])
  is_mmt_buy = bool(latest["mmt_buy"] or latest["ali_buy"])
  is_re_sell = bool(latest["reject_mahi"])
  is_re_buy = bool(latest["reject_malo"])

  # Tentukan Bias & Status berdasarkan V7 Logic
  bias = "NEUTRAL"
  status = "NEUTRAL (Menunggu Setup)"
  detail = "Harga berada di area konsolidasi/netral."

  if is_mmt_sell or is_csak_sell or is_re_sell or is_ext_sell or is_mhv_sell:
    if (
        is_re_sell
        or is_mhv_sell
        or (c_price < mid_bb and not (is_ext_buy or is_csak_buy))
    ):
      bias = "SELL"
      if is_re_sell:
        status = "RE-ENTRY SELL VALID (MA 5/10 High)"
        detail = "Harga melakukan penolakan valid di area MA High (Fuji V7)."
      elif is_mhv_sell:
        status = "MHV SELL TERDETEKSI"
        detail = "Market Hilang Volume Sell aktif di bawah Top BB."
      elif is_mmt_sell:
        status = "MOMENTUM SELL (CSM)"
        detail = "Candle Close menembus Low BB ke bawah."
      elif is_csak_sell:
        status = "CSAK SELL"
        detail = "Candle Arah Kukuh Sell melewati Mid BB."
      else:
        status = "BEARISH BIAS (Fuji V7)"
        detail = "Struktur Sell aktif."

  if is_mmt_buy or is_csak_buy or is_re_buy or is_ext_buy or is_mhv_buy:
    if (
        is_re_buy
        or is_mhv_buy
        or (c_price > mid_bb and not (is_ext_sell or is_csak_sell))
    ):
      bias = "BUY"
      if is_re_buy:
        status = "RE-ENTRY BUY VALID (MA 5/10 Low)"
        detail = "Harga melakukan penolakan valid di area MA Low (Fuji V7)."
      elif is_mhv_buy:
        status = "MHV BUY TERDETEKSI"
        detail = "Market Hilang Volume Buy aktif di atas Low BB."
      elif is_mmt_buy:
        status = "MOMENTUM BUY (CSM)"
        detail = "Candle Close menembus Top BB ke atas."
      elif is_csak_buy:
        status = "CSAK BUY"
        detail = "Candle Arah Kukuh Buy melewati Mid BB."
      else:
        status = "BULLISH BIAS (Fuji V7)"
        detail = "Struktur Buy aktif."

  return {
      "price": c_price,
      "status": status,
      "bias": bias,
      "top_bb": top_bb,
      "bot_bb": bot_bb,
      "mid_bb": mid_bb,
      "ema50": ema50,
      "detail": detail,
  }


# -----------------------------------------------------------------
# 3. KALKULATOR RISK MANAGEMENT XAUUSD
# -----------------------------------------------------------------
def calculate_trade_levels(
    bias, current_price, top_bb, mid_bb, bot_bb, account_risk
):
  if bias == "BUY":
    entry = current_price
    sl = round(bot_bb - 3.0, 2)
    tp1 = round(mid_bb, 2)
    tp2 = round(top_bb - 4.0, 2)
    tp3 = round(top_bb, 2)
    risk_pips = round((entry - sl) * 10, 1)
    reward_pips = round((tp1 - entry) * 10, 1)
    rrr = round(reward_pips / risk_pips, 2) if risk_pips > 0 else 0.0
    lot_size = (
        round(account_risk / (risk_pips * 10), 2) if risk_pips > 0 else 0.0
    )
  elif bias == "SELL":
    entry = current_price
    sl = round(top_bb + 3.0, 2)
    tp1 = round(mid_bb, 2)
    tp2 = round(bot_bb + 4.0, 2)
    tp3 = round(bot_bb, 2)
    risk_pips = round((sl - entry) * 10, 1)
    reward_pips = round((entry - tp1) * 10, 1)
    rrr = round(reward_pips / risk_pips, 2) if risk_pips > 0 else 0.0
    lot_size = (
        round(account_risk / (risk_pips * 10), 2) if risk_pips > 0 else 0.0
    )
  else:
    entry, sl, tp1, tp2, tp3, rrr, risk_pips, lot_size = (
        0,
        0,
        0,
        0,
        0,
        0.0,
        0.0,
        0.0,
    )
  return entry, sl, tp1, tp2, tp3, rrr, risk_pips, max(lot_size, 0.01)


# -----------------------------------------------------------------
# 4. TARIK DATA & EVALUASI OTOMATIS XAUUSD
# -----------------------------------------------------------------
with st.spinner("Menganalisis logika BBMA Fuji V7 live XAUUSD..."):
  df_1h = fetch_tf_data("1h", "30d")
  df_15m = fetch_tf_data("15m", "10d")
  df_5m = fetch_tf_data("5m", "5d")
  df_1m = fetch_tf_data("1m", "2d")
  df_1d = fetch_tf_data("1d", "1y")
  df_4h = resample_to_h4(df_1h)


def evaluate_xauusd_fuji(tf1_code, tf2_code, tf3_code):
  d1 = analyze_tf_fuji(globals()[f"df_{tf1_code}"], "TF1")
  d2 = analyze_tf_fuji(globals()[f"df_{tf2_code}"], "TF2")
  d3 = analyze_tf_fuji(globals()[f"df_{tf3_code}"], "TF3")

  dominant_bias = d1["bias"]

  if dominant_bias == "NEUTRAL":
    valid_signal = "⏳ PASAR NETRAL / KONSOLIDASI"
    kesimpulan = f"ℹ️ Acuan {tf1_code.upper()} dalam posisi netral."
  else:
    valid_signal = f"🔥 SETUP FUJI V7 AKTIF ({dominant_bias})"
    kesimpulan = (
        f"✅ **Setup Terdeteksi di {tf1_code.upper()}!** Status:"
        f" {d1['status']}."
    )

  return {
      "valid_signal": valid_signal,
      "dominant_bias": dominant_bias,
      "kesimpulan": kesimpulan,
      "tf_data": {"tf1": d1, "tf2": d2, "tf3": d3},
  }


tf_labels = {
    "1d": "Daily (D1)",
    "4h": "H4",
    "1h": "H1",
    "15m": "M15",
    "5m": "M5",
    "1m": "M1",
}

# -----------------------------------------------------------------
# 5. TAMPILAN ANTARMUKA UTAMA (UI DASHBOARD)
# -----------------------------------------------------------------
live_price = df_1h["Close"].iloc[-1] if not df_1h.empty else 0.0
st.metric("Harga Live XAUUSD", f"${live_price:,.2f}")
st.markdown("---")
st.subheader(
    f"🎯 Matriks Fuji V7 BBMA XAUUSD | Paket Hirarki: {tf_package}"
)

tab1, tab2, tab3, tab4 = st.tabs([
    "D1 ➔ H4 ➔ H1",
    "H4 ➔ H1 ➔ M15",
    "H1 ➔ M15 ➔ M5",
    "M15 ➔ M5 ➔ M1",
])


def render_tab_content(tf1, tf2, tf3):
  eval_res = evaluate_xauusd_fuji(tf1, tf2, tf3)
  data = eval_res["tf_data"]
  d_exec = data["tf3"]
  execution_bias = eval_res["dominant_bias"]

  entry, sl, tp1, tp2, tp3, rrr, risk_pips, lot_size = calculate_trade_levels(
      execution_bias,
      d_exec["price"],
      d_exec["top_bb"],
      d_exec["mid_bb"],
      d_exec["bot_bb"],
      risk_amount,
  )

  col1, col2, col3, col4 = st.columns(4)
  col1.metric("Status Sinyal Fuji V7", eval_res["valid_signal"])
  col2.metric("Risk-to-Reward (RRR)", f"1 : {rrr}" if rrr > 0 else "-")
  col3.metric("Rekomendasi Lot", f"{lot_size} Lot" if lot_size > 0 else "-")
  col4.metric("Arah Keputusan", execution_bias)

  if "SETUP FUJI V7 AKTIF" in eval_res["valid_signal"]:
    st.success(eval_res["kesimpulan"])
  else:
    st.info(eval_res["kesimpulan"])

  # Tabel Matriks Timeframe
  st.markdown("#### 📌 Matriks Multi-Timeframe Berbasis Logika Fuji V7")
  matrix_rows = [
      {
          "Peran Hirarki": f"TF1 (Acuan Utama - {tf_labels[tf1]})",
          "Status / Kondisi": data["tf1"]["status"],
          "Arah Bias": data["tf1"]["bias"],
          "Top BB": f"${data['tf1']['top_bb']:,.2f}",
          "Mid BB": f"${data['tf1']['mid_bb']:,.2f}",
          "EMA 50": f"${data['tf1']['ema50']:,.2f}",
          "Bottom BB": f"${data['tf1']['bot_bb']:,.2f}",
          "Keterangan Analisis": data["tf1"]["detail"],
      },
      {
          "Peran Hirarki": f"TF2 (Konfirmasi - {tf_labels[tf2]})",
          "Status / Kondisi": data["tf2"]["status"],
          "Arah Bias": data["tf2"]["bias"],
          "Top BB": f"${data['tf2']['top_bb']:,.2f}",
          "Mid BB": f"${data['tf2']['mid_bb']:,.2f}",
          "EMA 50": f"${data['tf2']['ema50']:,.2f}",
          "Bottom BB": f"${data['tf2']['bot_bb']:,.2f}",
          "Keterangan Analisis": data["tf2"]["detail"],
      },
      {
          "Peran Hirarki": f"TF3 (Eksekusi - {tf_labels[tf3]})",
          "Status / Kondisi": data["tf3"]["status"],
          "Arah Bias": data["tf3"]["bias"],
          "Top BB": f"${data['tf3']['top_bb']:,.2f}",
          "Mid BB": f"${data['tf3']['mid_bb']:,.2f}",
          "EMA 50": f"${data['tf3']['ema50']:,.2f}",
          "Bottom BB": f"${data['tf3']['bot_bb']:,.2f}",
          "Keterangan Analisis": data["tf3"]["detail"],
      },
  ]
  st.dataframe(pd.DataFrame(matrix_rows), use_container_width=True)

  # Tabel Rencana Perdagangan & Manajemen Risiko
  icon_label = (
      "🟢"
      if execution_bias == "BUY"
      else ("🔴" if execution_bias == "SELL" else "⚪")
  )
  st.markdown(
      f"#### 📋 Rencana Eksekusi Trade & Manajemen Risiko ({icon_label}"
      f" {execution_bias})"
  )

  trade_table = pd.DataFrame([
      {
          "Parameter": "Harga Entry Saat Ini (TF3)",
          "Nilai Level Harga": f"${entry:,.2f}" if entry > 0 else "-",
      },
      {
          "Parameter": "Stop Loss (SL)",
          "Nilai Level Harga": f"${sl:,.2f}" if sl > 0 else "-",
      },
      {
          "Parameter": "Jarak Risiko",
          "Nilai Level Harga": (
              f"{risk_pips} Pips ({risk_pips*10:.0f} Points)"
              if risk_pips > 0
              else "-"
          ),
      },
      {
          "Parameter": "Take Profit 1 (Mid BB)",
          "Nilai Level Harga": f"${tp1:,.2f}" if tp1 > 0 else "-",
      },
      {
          "Parameter": "Take Profit 2 (Buffer Area)",
          "Nilai Level Harga": f"${tp2:,.2f}" if tp2 > 0 else "-",
      },
      {
          "Parameter": "Take Profit 3 (Extreme BB)",
          "Nilai Level Harga": (
              f"${tp3:,.2f}" if (tp3 is not None and tp3 > 0) else "-"
          ),
      },
  ])
  st.dataframe(trade_table, use_container_width=True)


with tab1:
  render_tab_content("1d", "4h", "1h")

with tab2:
  render_tab_content("4h", "1h", "15m")

with tab3:
  render_tab_content("1h", "15m", "5m")

with tab4:
  render_tab_content("15m", "5m", "1m")
