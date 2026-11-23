import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
import time
import io

st.set_page_config(page_title="GOLDEN SMART MONEY AI", page_icon="📈", layout="wide")

st.markdown("""
<style>
.block-container {padding-top: 1rem; padding-bottom: 2rem;}
[data-testid="stMetric"] {background: rgba(120,120,120,.07); padding: 12px; border-radius: 10px;}
.small-note {font-size: .85rem; color: #777;}
</style>
""", unsafe_allow_html=True)

st.title("📈 GOLDEN SMART MONEY AI")
st.caption("BEI Daily Stock Scanner • Uptrend • Akumulasi (proxy) • BUY zone • TP & Stop Loss")

DEFAULT = pd.DataFrame([
    ("BBCA.JK","BBCA",False), ("BBRI.JK","BBRI",False), ("BMRI.JK","BMRI",False),
    ("BBNI.JK","BBNI",False), ("TLKM.JK","TLKM",False), ("ASII.JK","ASII",False),
    ("ANTM.JK","ANTM",False), ("TINS.JK","TINS",False), ("PGEO.JK","PGEO",False),
    ("ICBP.JK","ICBP",False), ("INDF.JK","INDF",False), ("KLBF.JK","KLBF",False),
    ("UNTR.JK","UNTR",False), ("ADRO.JK","ADRO",False), ("PTBA.JK","PTBA",False),
    ("MEDC.JK","MEDC",False), ("BRIS.JK","BRIS",False), ("EXCL.JK","EXCL",False),
    ("ISAT.JK","ISAT",False), ("CPIN.JK","CPIN",False), ("JPFA.JK","JPFA",False),
], columns=["ticker", "kode", "syariah"])

def calc_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100 - 100/(1 + rs)).fillna(50)

def calc_obv(close, volume):
    direction = np.sign(close.diff()).fillna(0)
    return (direction * volume).cumsum()

def analyze_ticker(ticker):
    hist = yf.Ticker(ticker).history(period="1y", interval="1d", auto_adjust=True)
    if hist is None or hist.empty or len(hist) < 60:
        return None

    hist = hist.dropna(subset=["Close", "High", "Low", "Volume"]).copy()
    if len(hist) < 60:
        return None

    close, high, low, volume = hist["Close"], hist["High"], hist["Low"], hist["Volume"]
    price = float(close.iloc[-1])
    ema20 = close.ewm(span=20, adjust=False).mean()
    ma50 = close.rolling(50).mean()
    ma200 = close.rolling(200).mean()
    rsi = calc_rsi(close)
    macd = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
    macd_signal = macd.ewm(span=9, adjust=False).mean()
    avgvol20 = volume.rolling(20).mean()
    volratio = float(volume.iloc[-1] / avgvol20.iloc[-1]) if pd.notna(avgvol20.iloc[-1]) and avgvol20.iloc[-1] > 0 else np.nan

    prev_close = float(close.iloc[-2])
    day_change = (price / prev_close - 1) * 100 if prev_close else 0.0

    candle_range = float(high.iloc[-1] - low.iloc[-1])
    close_location = float((price - low.iloc[-1]) / candle_range) if candle_range > 0 else 0.5

    obv = calc_obv(close, volume)
    obv_up = len(obv) >= 6 and float(obv.iloc[-1]) > float(obv.iloc[-6])

    # Chaikin Money Flow 20 hari sebagai proxy tekanan beli/jual.
    denom = (high - low).replace(0, np.nan)
    money_flow_multiplier = (((close - low) - (high - close)) / denom).fillna(0)
    money_flow_volume = money_flow_multiplier * volume
    cmf20 = float(money_flow_volume.rolling(20).sum().iloc[-1] /
                  volume.rolling(20).sum().iloc[-1]) if volume.rolling(20).sum().iloc[-1] > 0 else 0.0

    # ATR 14 untuk stop loss yang menyesuaikan volatilitas.
    prev = close.shift(1)
    tr = pd.concat([(high-low), (high-prev).abs(), (low-prev).abs()], axis=1).max(axis=1)
    atr14 = float(tr.rolling(14).mean().iloc[-1])
    recent_support = float(low.tail(10).min())
    previous_20_high = float(high.rolling(20).max().shift(1).iloc[-1])

    ema20_now, ma50_now = float(ema20.iloc[-1]), float(ma50.iloc[-1])
    ma200_now = float(ma200.iloc[-1]) if pd.notna(ma200.iloc[-1]) else np.nan
    rsi_now = float(rsi.iloc[-1])
    macd_bull = bool(macd.iloc[-1] > macd_signal.iloc[-1])
    macd_rising = bool(macd.iloc[-1] > macd.iloc[-2])

    # Score teknikal maksimal 100. Akumulasi adalah indikasi berbasis OHLCV, bukan broker flow.
    score = 0
    score += 15 if price > ema20_now else 0
    score += 15 if price > ma50_now else 0
    score += 10 if pd.notna(ma200_now) and ma50_now > ma200_now else 0
    score += 10 if 50 <= rsi_now <= 68 else (5 if 45 <= rsi_now < 50 or 68 < rsi_now <= 73 else 0)
    score += 10 if macd_bull else 0
    score += 5 if macd_rising else 0
    score += 10 if pd.notna(volratio) and volratio >= 1.5 else (5 if pd.notna(volratio) and volratio >= 1.2 else 0)
    score += 5 if close_location >= 0.65 else 0
    score += 5 if obv_up else 0
    score += 5 if cmf20 > 0 else 0
    score += 10 if price >= previous_20_high else 0

    accumulation = "Indikasi kuat" if (obv_up and cmf20 > 0 and close_location >= 0.60 and pd.notna(volratio) and volratio >= 1.2) else (
        "Mulai terbentuk" if ((obv_up and cmf20 > 0) or (close_location >= 0.70 and pd.notna(volratio) and volratio >= 1.5)) else "Belum terkonfirmasi"
    )

    uptrend = price > ema20_now and price > ma50_now and (pd.isna(ma200_now) or ma50_now > ma200_now)
    breakout = price >= previous_20_high
    if score >= 80 and uptrend and accumulation != "Belum terkonfirmasi":
        signal = "BUY CANDIDATE"
    elif score >= 70 and uptrend:
        signal = "BUY ON CONFIRMATION"
    elif score >= 55:
        signal = "WATCHLIST"
    else:
        signal = "WAIT"

    # Rencana indikatif: stop memakai support 10 hari dan ATR; jangan tempatkan stop di atas entry.
    entry_low = price * 0.995
    entry_high = price * 1.005
    atr_stop = price - (1.5 * atr14) if pd.notna(atr14) and atr14 > 0 else price * 0.97
    stop = min(atr_stop, recent_support * 0.995)
    if stop <= 0 or stop >= price:
        stop = price * 0.97
    risk_per_share = price - stop
    tp1 = price + 1.5 * risk_per_share
    tp2 = price + 2.0 * risk_per_share

    return {
        "Kode": ticker.replace(".JK", ""),
        "Harga referensi": price,
        "Perubahan harian (%)": day_change,
        "Skor": int(score),
        "Sinyal": signal,
        "Trend": "Uptrend" if uptrend else "Belum uptrend",
        "Akumulasi (proxy)": accumulation,
        "RSI14": rsi_now,
        "Volume x Avg20": volratio,
        "CMF20": cmf20,
        "OBV naik": "Ya" if obv_up else "Tidak",
        "MACD bullish": "Ya" if macd_bull else "Tidak",
        "Breakout 20D": "Ya" if breakout else "Tidak",
        "Buy zone bawah": entry_low,
        "Buy zone atas": entry_high,
        "Stop loss": stop,
        "TP1": tp1,
        "TP2": tp2,
        "Support 10D": recent_support,
        "ATR14": atr14,
        "Update data": hist.index[-1].strftime("%Y-%m-%d")
    }

with st.sidebar:
    st.header("⚙️ Pengaturan")
    mode = st.selectbox("Universe saham", ["Daftar awal + upload CSV", "Khusus Syariah (berdasarkan CSV)"])
    uploaded = st.file_uploader("Upload universe saham CSV (opsional)", type=["csv"])
    capital = st.number_input("Modal trading (Rp)", min_value=1000000, value=10000000, step=1000000, format="%d")
    risk_pct = st.slider("Risiko per transaksi (%)", 0.25, 2.0, 1.0, 0.25)
    max_positions = st.number_input("Maksimum posisi bersamaan", min_value=1, max_value=5, value=2)
    min_score = st.slider("Skor minimum", 0, 100, 60)
    validate_universe = st.button("🧪 VALIDASI TICKER YAHOO", use_container_width=True)
    run_scan = st.button("🔎 SCAN MARKET", type="primary", use_container_width=True)
    st.caption("Data harian Yahoo Finance/yfinance. Periksa tanggal update; data dapat terlambat atau tidak lengkap.")

universe = DEFAULT.copy()
if uploaded is not None:
    try:
        uploaded.seek(0)
        universe = pd.read_csv(uploaded)
        universe.columns = [str(c).strip().lower() for c in universe.columns]
        if "ticker" not in universe.columns:
            st.error("CSV wajib memiliki kolom ticker, contoh BBCA.JK")
            st.stop()
        universe["ticker"] = universe["ticker"].astype(str).str.strip().str.upper()
        if "kode" not in universe.columns:
            universe["kode"] = universe["ticker"].str.replace(".JK", "", regex=False)
        if "syariah" not in universe.columns:
            universe["syariah"] = False
        universe["syariah"] = universe["syariah"].astype(str).str.lower().isin(["true", "1", "yes", "ya"])
    except Exception as exc:
        st.error(f"Gagal membaca CSV: {exc}")
        st.stop()

if mode == "Khusus Syariah (berdasarkan CSV)":
    universe = universe[universe["syariah"] == True]

universe = universe.drop_duplicates(subset=["ticker"]).reset_index(drop=True)

st.subheader("Ringkasan konfigurasi")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Jumlah ticker", len(universe))
m2.metric("Modal", f"Rp{capital:,.0f}")
m3.metric("Risiko/transaksi", f"{risk_pct:.2f}%")
m4.metric("Risiko uang", f"Rp{capital*risk_pct/100:,.0f}")

st.info(
    "Robot ini melakukan pemindaian harian dan memberi sinyal berbasis indikator teknikal. "
    "Akumulasi hanya proxy OHLCV (OBV, CMF, volume, posisi penutupan), bukan data broker summary, "
    "foreign flow, atau bukti transaksi bandar. Tidak mengirim order otomatis."
)

if validate_universe:
    if universe.empty:
        st.warning("Universe kosong. Unggah CSV terlebih dahulu.")
    else:
        st.subheader("🧪 Validasi ketersediaan data Yahoo Finance")
        checks = []
        progress = st.progress(0)
        status = st.empty()
        tickers_check = universe["ticker"].dropna().astype(str).unique().tolist()
        for i, ticker in enumerate(tickers_check):
            status.write(f"Memeriksa {ticker} ({i+1}/{len(tickers_check)})")
            try:
                sample = yf.Ticker(ticker).history(period="10d", interval="1d", auto_adjust=True)
                ok = sample is not None and not sample.empty and "Close" in sample.columns and sample["Close"].dropna().shape[0] > 0
                checks.append({"Kode": ticker.replace(".JK", ""), "Ticker Yahoo": ticker,
                               "Status data": "TERSEDIA" if ok else "TIDAK ADA DATA",
                               "Tanggal terakhir": sample.index[-1].strftime("%Y-%m-%d") if ok else ""})
            except Exception as exc:
                checks.append({"Kode": ticker.replace(".JK", ""), "Ticker Yahoo": ticker,
                               "Status data": f"ERROR: {type(exc).__name__}", "Tanggal terakhir": ""})
            progress.progress((i+1)/len(tickers_check))
            time.sleep(0.08)
        status.empty()
        progress.empty()
        check_df = pd.DataFrame(checks)
        st.session_state["ticker_validation"] = check_df
        good = int((check_df["Status data"] == "TERSEDIA").sum())
        st.metric("Ticker dengan data tersedia", f"{good} / {len(check_df)}")

if "ticker_validation" in st.session_state:
    vdf = st.session_state["ticker_validation"]
    st.dataframe(vdf, use_container_width=True, hide_index=True)
    st.download_button("⬇️ Download hasil validasi ticker", vdf.to_csv(index=False).encode("utf-8"),
                       file_name="validasi_ticker_yahoo.csv", mime="text/csv")

if run_scan:
    if universe.empty:
        st.warning("Universe kosong. Isi/unggah daftar ticker terlebih dahulu.")
    else:
        results = []
        progress = st.progress(0)
        status = st.empty()
        tickers = universe["ticker"].dropna().astype(str).unique().tolist()
        for i, ticker in enumerate(tickers):
            status.write(f"Menganalisis {ticker} ({i+1}/{len(tickers)})")
            try:
                item = analyze_ticker(ticker)
                if item:
                    match = universe.loc[universe["ticker"] == ticker, "syariah"]
                    item["Status Syariah (CSV)"] = "Ditandai Syariah pada CSV" if (len(match) and bool(match.iloc[0])) else "Belum diverifikasi"
                    results.append(item)
            except Exception as exc:
                st.caption(f"{ticker}: data gagal diambil ({type(exc).__name__})")
            progress.progress((i+1)/len(tickers))
            time.sleep(0.1)
        status.empty()
        progress.empty()
        if results:
            result_df = pd.DataFrame(results).sort_values(["Skor", "Volume x Avg20"], ascending=[False, False])
            st.session_state["scan_results"] = result_df
            st.session_state["scan_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.success(f"Scan selesai: {len(result_df)} dari {len(tickers)} ticker berhasil dianalisis.")
        else:
            st.warning("Tidak ada data berhasil diambil. Periksa ticker, koneksi, atau ketersediaan data Yahoo Finance.")

if "scan_results" in st.session_state:
    df = st.session_state["scan_results"].copy()
    st.subheader("🏆 Ranking kandidat saham")
    st.caption(f"Waktu scan: {st.session_state.get('scan_time', '-')} • Data harga terakhir: {df['Update data'].max()}")
    filtered = df[df["Skor"] >= min_score].copy()
    top = filtered.head(10)
    st.dataframe(
        top,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Skor": st.column_config.ProgressColumn("Skor", min_value=0, max_value=100),
            "Harga referensi": st.column_config.NumberColumn(format="Rp %.2f"),
            "Buy zone bawah": st.column_config.NumberColumn(format="Rp %.2f"),
            "Buy zone atas": st.column_config.NumberColumn(format="Rp %.2f"),
            "Stop loss": st.column_config.NumberColumn(format="Rp %.2f"),
            "TP1": st.column_config.NumberColumn(format="Rp %.2f"),
            "TP2": st.column_config.NumberColumn(format="Rp %.2f"),
            "Volume x Avg20": st.column_config.NumberColumn(format="%.2fx"),
            "RSI14": st.column_config.NumberColumn(format="%.1f"),
        }
    )
    st.download_button(
        "⬇️ Download hasil scan CSV",
        filtered.to_csv(index=False).encode("utf-8"),
        file_name="golden_smart_money_daily_scan.csv",
        mime="text/csv"
    )

    st.subheader("📋 Trading plan per saham")
    choices = filtered["Kode"].tolist()
    if choices:
        selected = st.selectbox("Pilih saham", choices)
        row = filtered[filtered["Kode"] == selected].iloc[0]
        entry = float(row["Harga referensi"])
        stop = float(row["Stop loss"])
        risk_per_share = max(entry - stop, 0)
        risk_cash = capital * risk_pct / 100
        lots_risk = int(risk_cash // (risk_per_share * 100)) if risk_per_share > 0 else 0
        lots_cash = int(capital // (entry * 100)) if entry > 0 else 0
        lots = max(0, min(lots_risk, lots_cash))
        allocated = lots * 100 * entry
        estimated_risk = lots * 100 * risk_per_share
        a, b, c, d = st.columns(4)
        a.metric("Harga referensi", f"Rp{entry:,.0f}")
        b.metric("Stop loss", f"Rp{stop:,.0f}")
        c.metric("TP1 / TP2", f"Rp{float(row['TP1']):,.0f} / Rp{float(row['TP2']):,.0f}")
        d.metric("Estimasi lot", f"{lots:,} lot")
        st.write(f"**Buy zone:** Rp{float(row['Buy zone bawah']):,.0f} – Rp{float(row['Buy zone atas']):,.0f}")
        st.write(f"**Alokasi dana:** Rp{allocated:,.0f} • **Estimasi risiko:** Rp{estimated_risk:,.0f} (belum termasuk fee dan slippage)")
        if row["Sinyal"] == "BUY CANDIDATE":
            st.success("Kandidat BUY: tunggu konfirmasi harga dan likuiditas pada sesi berikutnya.")
        elif row["Sinyal"] == "BUY ON CONFIRMATION":
            st.info("Belum entry langsung: tunggu breakout/retest dan konfirmasi volume.")
        else:
            st.warning("Watchlist saja. Jangan entry sebelum syarat tren dan akumulasi membaik.")
        st.caption("Buy zone adalah rentang indikatif sekitar harga penutupan terakhir, bukan limit order yang dijamin terisi.")
    else:
        st.warning("Tidak ada saham yang memenuhi skor minimum. Turunkan skor minimum hanya untuk memperluas watchlist, bukan untuk memaksakan entry.")

st.divider()
st.caption(
    "GOLDEN SMART MONEY AI • Prototype v0.3 • Sinyal bersifat edukatif, bukan rekomendasi investasi. "
    "Validasi harga, likuiditas, spread, berita, dan tanggal data sebelum transaksi."
)
