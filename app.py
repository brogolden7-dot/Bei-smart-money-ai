import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
import time

st.set_page_config(page_title="BEI Smart Money AI", page_icon="📈", layout="wide")

st.markdown("""
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 2rem;}
[data-testid="stMetric"] {background: rgba(120,120,120,.07); padding: 12px; border-radius: 10px;}
</style>
""", unsafe_allow_html=True)

st.title("📈 BEI SMART MONEY AI")
st.caption("AI Trading Assistant • Swing Trading 1–3 bulan • Data publik gratis")

DEFAULT = pd.DataFrame([
    ("BBCA.JK","BBCA",False), ("BBRI.JK","BBRI",False), ("BMRI.JK","BMRI",False),
    ("TLKM.JK","TLKM",False), ("ASII.JK","ASII",False), ("ANTM.JK","ANTM",False),
    ("TINS.JK","TINS",False), ("PGEO.JK","PGEO",False), ("ICBP.JK","ICBP",False),
    ("INDF.JK","INDF",False), ("KLBF.JK","KLBF",False), ("UNTR.JK","UNTR",False),
    ("ADRO.JK","ADRO",False), ("PTBA.JK","PTBA",False), ("MEDC.JK","MEDC",False),
    ("BRIS.JK","BRIS",False), ("EXCL.JK","EXCL",False), ("ISAT.JK","ISAT",False),
    ("CPIN.JK","CPIN",False), ("JPFA.JK","JPFA",False)
], columns=["ticker","kode","syariah"])

def calc_rsi(s, period=14):
    delta = s.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100/(1+rs))

def analyze(ticker):
    hist = yf.Ticker(ticker).history(period="1y", interval="1d", auto_adjust=True)
    if hist is None or hist.empty or len(hist) < 80:
        return None
    close, vol = hist["Close"], hist["Volume"]
    ema20 = close.ewm(span=20, adjust=False).mean()
    ma50 = close.rolling(50).mean()
    ma200 = close.rolling(200).mean()
    rsi = calc_rsi(close)
    macd = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
    signal = macd.ewm(span=9, adjust=False).mean()
    avgvol = vol.rolling(20).mean()
    volratio = (vol.iloc[-1] / avgvol.iloc[-1]) if avgvol.iloc[-1] and avgvol.iloc[-1] > 0 else np.nan
    # Proxy akumulasi: volume relatif + candle ditutup di bagian atas range + OBV slope.
    candle_range = (hist["High"].iloc[-1] - hist["Low"].iloc[-1])
    close_location = ((close.iloc[-1] - hist["Low"].iloc[-1]) / candle_range) if candle_range > 0 else 0.5
    obv = (np.sign(close.diff()).fillna(0) * vol).cumsum()
    obv_up = len(obv) >= 6 and obv.iloc[-1] > obv.iloc[-6]
    price = float(close.iloc[-1])
    score = 0
    score += 20 if price > ema20.iloc[-1] > ma50.iloc[-1] else (10 if price > ma50.iloc[-1] else 0)
    score += 10 if (not np.isnan(ma200.iloc[-1]) and ma50.iloc[-1] > ma200.iloc[-1]) else 0
    score += 8 if 50 <= rsi.iloc[-1] <= 70 else (4 if 45 <= rsi.iloc[-1] < 50 else 0)
    score += 7 if macd.iloc[-1] > signal.iloc[-1] else 0
    score += 5 if macd.iloc[-1] > macd.iloc[-2] else 0
    score += 8 if volratio >= 1.5 else (4 if volratio >= 1.1 else 0)
    score += 7 if close_location >= 0.7 else 0
    score += 5 if obv_up else 0
    score += 10 if price >= hist["High"].rolling(20).max().iloc[-2] else 0
    # Fundamental score is intentionally separate and may be unavailable.
    info = {}
    try:
        info = yf.Ticker(ticker).get_info() or {}
    except Exception:
        pass
    roe = info.get("returnOnEquity")
    debt_equity = info.get("debtToEquity")
    profit_margin = info.get("profitMargins")
    fund_score = 0
    fund_score += 4 if roe is not None and roe > 0.12 else (2 if roe is not None and roe > 0.05 else 0)
    fund_score += 3 if debt_equity is not None and debt_equity < 100 else (1 if debt_equity is not None and debt_equity < 200 else 0)
    fund_score += 3 if profit_margin is not None and profit_margin > 0.08 else (1 if profit_margin is not None and profit_margin > 0 else 0)
    total = min(100, score + fund_score)
    if total >= 85: signal_text = "Kandidat kuat"
    elif total >= 75: signal_text = "Bullish watchlist"
    elif total >= 60: signal_text = "Early watchlist"
    else: signal_text = "Wait"
    return {
        "Kode": ticker.replace(".JK",""), "Harga": price, "Skor": total,
        "Sinyal": signal_text, "RSI": float(rsi.iloc[-1]),
        "EMA20": float(ema20.iloc[-1]), "MA50": float(ma50.iloc[-1]),
        "MA200": float(ma200.iloc[-1]) if not np.isnan(ma200.iloc[-1]) else np.nan,
        "MACD bullish": bool(macd.iloc[-1] > signal.iloc[-1]),
        "Vol x rata-rata": float(volratio) if pd.notna(volratio) else np.nan,
        "Proxy akumulasi": "Positif" if (obv_up and close_location >= .6 and volratio >= 1.2) else "Belum kuat",
        "ROE": roe, "DER": debt_equity, "Margin laba": profit_margin,
        "Fundamental score": fund_score,
        "Update data": hist.index[-1].strftime("%Y-%m-%d")
    }

with st.sidebar:
    st.header("⚙️ Pengaturan")
    mode = st.selectbox("Universe saham", ["Seluruh BEI (daftar yang diunggah)", "Khusus Syariah", "Semua + filter Syariah"])
    uploaded = st.file_uploader("Upload universe saham CSV (opsional)", type=["csv"])
    capital = st.number_input("Modal simulasi (Rp)", min_value=0, value=0, step=1000000, format="%d")
    risk_pct = st.slider("Risiko per transaksi (%)", 0.25, 2.0, 1.0, 0.25)
    run_scan = st.button("🔎 SCAN MARKET", type="primary", use_container_width=True)
    st.caption("Sumber: Yahoo Finance melalui yfinance. Data dapat terlambat/tidak lengkap.")

universe = DEFAULT.copy()
if uploaded:
    try:
        universe = pd.read_csv(uploaded)
        universe.columns = [c.strip().lower() for c in universe.columns]
        if "ticker" not in universe.columns:
            st.error("CSV wajib memiliki kolom ticker. Contoh: BBCA.JK")
            st.stop()
        if "kode" not in universe.columns:
            universe["kode"] = universe["ticker"].str.replace(".JK","", regex=False)
        if "syariah" not in universe.columns:
            universe["syariah"] = False
        universe["syariah"] = universe["syariah"].astype(str).str.lower().isin(["true","1","yes","ya"])
    except Exception as e:
        st.error(f"Gagal membaca CSV: {e}")
        st.stop()

if mode == "Khusus Syariah":
    universe = universe[universe["syariah"] == True]
elif mode == "Semua + filter Syariah":
    st.info("Mode ini menampilkan seluruh saham dari file universe; kolom Syariah menandai saham yang lolos daftar DES yang Anda unggah.")

st.subheader("Ringkasan")
c1,c2,c3,c4 = st.columns(4)
c1.metric("Jumlah ticker", len(universe))
c2.metric("Modal simulasi", f"Rp{capital:,.0f}" if capital else "Belum diisi")
c3.metric("Risiko/transaksi", f"{risk_pct:.2f}%")
c4.metric("Mode", "Swing 1–3 bulan")

st.info("Versi awal ini sudah menyediakan scanner teknikal dan proxy akumulasi. Penilaian fundamental memakai field yang tersedia dari Yahoo Finance; data kosong tidak dianggap bagus. Broker summary dan foreign flow belum dihitung karena tidak tersedia konsisten dari sumber gratis ini.")

if run_scan:
    if universe.empty:
        st.warning("Universe kosong. Upload CSV saham terlebih dahulu.")
    else:
        results = []
        progress = st.progress(0)
        status = st.empty()
        rows = universe["ticker"].dropna().astype(str).unique().tolist()
        for i, ticker in enumerate(rows):
            status.write(f"Menganalisis {ticker} ({i+1}/{len(rows)})")
            try:
                result = analyze(ticker)
                if result:
                    if "syariah" in universe.columns:
                        match = universe.loc[universe["ticker"] == ticker, "syariah"]
                        result["Status Syariah (CSV)"] = "Terverifikasi DES" if (len(match) and bool(match.iloc[0])) else "Belum diverifikasi"
                    results.append(result)
            except Exception:
                pass
            progress.progress((i+1)/len(rows))
            time.sleep(0.15)
        status.empty()
        progress.empty()
        if results:
            df = pd.DataFrame(results).sort_values("Skor", ascending=False)
            st.session_state["scan_results"] = df
            st.success(f"Scan selesai: {len(df)} saham berhasil dianalisis.")
        else:
            st.warning("Tidak ada data yang berhasil diambil. Coba lagi nanti atau periksa format ticker.")

if "scan_results" in st.session_state:
    df = st.session_state["scan_results"]
    st.subheader("🏆 Hasil Stock Screener")
    min_score = st.slider("Skor minimum", 0, 100, 60)
    show = df[df["Skor"] >= min_score]
    st.dataframe(show, use_container_width=True, hide_index=True,
                 column_config={"Harga": st.column_config.NumberColumn(format="Rp %.2f"),
                                "Skor": st.column_config.ProgressColumn(min_value=0,max_value=100),
                                "RSI": st.column_config.NumberColumn(format="%.1f"),
                                "Vol x rata-rata": st.column_config.NumberColumn(format="%.2fx")})
    st.download_button("⬇️ Download hasil CSV", show.to_csv(index=False).encode("utf-8"),
                       file_name="hasil_screening_bei.csv", mime="text/csv")
    choice = st.selectbox("Pilih saham untuk trading plan", show["Kode"].tolist() if not show.empty else [])
    if choice:
        row = show[show["Kode"] == choice].iloc[0]
        entry = float(row["Harga"])
        stop = entry * 0.95
        tp1, tp2, tp3 = entry*1.05, entry*1.10, entry*1.15
        st.subheader(f"📋 Trading Plan: {choice}")
        a,b,c,d = st.columns(4)
        a.metric("Harga referensi", f"Rp{entry:,.0f}")
        b.metric("Buy zone indikatif", f"Rp{entry*.99:,.0f}–{entry*1.01:,.0f}")
        c.metric("Stop loss simulasi", f"Rp{stop:,.0f}")
        d.metric("Risk/reward TP1", "1 : 1")
        st.write(f"TP1 **Rp{tp1:,.0f}** • TP2 **Rp{tp2:,.0f}** • TP3 **Rp{tp3:,.0f}**")
        if capital > 0:
            risk_cash = capital * risk_pct / 100
            risk_per_share = max(entry-stop, 1)
            lots_by_risk = int(risk_cash / (risk_per_share*100))
            lots_by_cash = int(capital / (entry*100))
            lots = min(lots_by_risk, lots_by_cash)
            st.metric("Estimasi lot maksimum (risiko)", f"{lots:,} lot")
            st.caption(f"Estimasi risiko uang Rp{risk_cash:,.0f}, belum memperhitungkan fee dan slippage. Jumlah lot juga dibatasi dana tersedia.")
        st.warning("Trading plan ini hanya simulasi berbasis persentase, belum memakai support/resistance aktual. Validasi chart dan likuiditas sebelum transaksi.")

st.divider()
st.caption("BEI SMART MONEY AI • Prototype v0.1 • Bukan rekomendasi investasi. Gunakan data terbaru dan lakukan verifikasi mandiri.")
