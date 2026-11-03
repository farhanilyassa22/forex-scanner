import streamlit as st
import pandas as pd
import numpy as np
import requests

st.set_page_config(page_title="Forex Scanner", layout="wide")
st.markdown("""<style>.block-container{padding-top:1rem}@media(max-width:700px){.block-container{padding-left:.7rem;padding-right:.7rem}h1{font-size:1.7rem!important}}</style>""",unsafe_allow_html=True)
st.title("Forex Scanner")
st.caption("Analisa teknikal Forex dari Twelve Data. Sinyal bersifat heuristik, bukan jaminan hasil trading.")

API_KEY=st.secrets.get("TWELVE_DATA_API_KEY","")
if not API_KEY:
    st.error("API key belum diatur. Streamlit Cloud → App settings → Secrets.")
    st.code('TWELVE_DATA_API_KEY = "API_KEY_KAMU"',language="toml")
    st.stop()

PAIRS=["EUR/USD","GBP/USD","USD/JPY","AUD/USD","USD/CAD","USD/CHF","NZD/USD","EUR/JPY","GBP/JPY","XAU/USD"]
TF={"M5":"5min","M15":"15min","M30":"30min","H1":"1h","H4":"4h","D1":"1day"}

@st.cache_data(ttl=60,show_spinner=False)
def candles(symbol,interval):
    r=requests.get("https://api.twelvedata.com/time_series",params={"symbol":symbol,"interval":interval,"outputsize":250,"apikey":API_KEY,"format":"JSON"},timeout=25)
    r.raise_for_status()
    j=r.json()
    if "values" not in j: raise RuntimeError(j.get("message","Data tidak tersedia"))
    d=pd.DataFrame(j["values"])
    d["datetime"]=pd.to_datetime(d["datetime"],errors="coerce")
    for c in ["open","high","low","close"]: d[c]=pd.to_numeric(d[c],errors="coerce")
    return d.dropna().sort_values("datetime").reset_index(drop=True)

def indicators(d):
    d=d.copy()
    d["ema9"]=d.close.ewm(span=9,adjust=False).mean()
    d["ema21"]=d.close.ewm(span=21,adjust=False).mean()
    delta=d.close.diff()
    gain=delta.clip(lower=0).rolling(14).mean()
    loss=(-delta.clip(upper=0)).rolling(14).mean()
    d["rsi"]=100-100/(1+gain/loss.replace(0,np.nan))
    prev=d.close.shift()
    tr=pd.concat([d.high-d.low,(d.high-prev).abs(),(d.low-prev).abs()],axis=1).max(axis=1)
    d["atr"]=tr.rolling(14).mean()
    d["bb_mid"]=d.close.rolling(20).mean()
    sd=d.close.rolling(20).std()
    d["bb_upper"]=d.bb_mid+2*sd; d["bb_lower"]=d.bb_mid-2*sd
    return d

def signal(d):
    x=d.iloc[-1]
    if pd.isna(x.atr) or pd.isna(x.rsi): return "WAIT","Indikator belum cukup"
    if x.ema9>x.ema21 and x.close>x.ema9 and 52<=x.rsi<=70: return "BUY","EMA bullish dan RSI mendukung"
    if x.ema9<x.ema21 and x.close<x.ema9 and 30<=x.rsi<=48: return "SELL","EMA bearish dan RSI mendukung"
    if abs(x.ema9-x.ema21)/x.close<0.00015 and 45<=x.rsi<=55: return "SIDEWAYS","EMA berdekatan, RSI netral"
    return "WAIT","Belum memenuhi aturan entry"

def levels(d,s):
    x=d.iloc[-1]; entry=float(x.close); a=float(x.atr)
    if s=="BUY": return {"Entry":entry,"SL":entry-1.5*a,"TP1":entry+1.5*a,"TP2":entry+2.5*a}
    if s=="SELL": return {"Entry":entry,"SL":entry+1.5*a,"TP1":entry-1.5*a,"TP2":entry-2.5*a}
    return None

with st.sidebar:
    st.header("Filter")
    tf=st.selectbox("Timeframe",list(TF),index=2)
    pair_input=st.text_area("Pair (pisahkan koma)",", ".join(PAIRS))
    pairs=[p.strip().upper().replace(" ","") for p in pair_input.split(",") if p.strip()]
    if st.button("Refresh data"): candles.clear()

t1,t2,t3=st.tabs(["Scanner","Analisa manual","Panduan"])
with t1:
    st.subheader(f"Scan pair · {tf}")
    if st.button("Scan pair",type="primary"):
        rows=[]; bar=st.progress(0)
        for i,p in enumerate(pairs):
            try:
                d=indicators(candles(p,TF[tf])); s,why=signal(d); x=d.iloc[-1]
                rows.append({"Pair":p,"Sinyal":s,"Harga":x.close,"RSI":x.rsi,"EMA9":x.ema9,"EMA21":x.ema21,"Candle terakhir":str(x.datetime),"Catatan":why})
            except Exception as e:
                rows.append({"Pair":p,"Sinyal":"ERROR","Harga":None,"RSI":None,"EMA9":None,"EMA21":None,"Candle terakhir":"-","Catatan":str(e)})
            bar.progress((i+1)/max(len(pairs),1))
        st.session_state["scan"]=rows
    if "scan" in st.session_state:
        df=pd.DataFrame(st.session_state["scan"])
        st.dataframe(df,use_container_width=True,hide_index=True)
        a,b,c=st.columns(3)
        a.metric("BUY",int((df.Sinyal=="BUY").sum())); b.metric("SELL",int((df.Sinyal=="SELL").sum())); c.metric("WAIT / lainnya",int(len(df)-(df.Sinyal=="BUY").sum()-(df.Sinyal=="SELL").sum()))
with t2:
    p=st.selectbox("Pair analisa",pairs or PAIRS)
    tf2=st.selectbox("Timeframe analisa",list(TF),index=2,key="tfmanual")
    if st.button("Analisa pair"):
        try:
            d=indicators(candles(p,TF[tf2])); s,why=signal(d); x=d.iloc[-1]
            st.metric("Sinyal",s); st.write(why)
            lv=levels(d,s)
            if lv: st.dataframe(pd.DataFrame([lv]),use_container_width=True,hide_index=True)
            st.caption(f"Candle terakhir: {x.datetime}")
            st.line_chart(d.set_index("datetime")[["close","ema9","ema21"]].tail(150))
            st.dataframe(d[["datetime","open","high","low","close","rsi","atr"]].tail(20).sort_values("datetime",ascending=False),use_container_width=True,hide_index=True)
        except Exception as e: st.error(f"Gagal mengambil data: {e}")
with t3:
    st.write("BUY/SELL berdasarkan EMA9, EMA21, dan RSI14. WAIT berarti belum ada setup. SIDEWAYS menandai EMA berdekatan dan RSI netral.")
    st.write("Entry memakai harga candle terakhir. SL dan target dihitung dari ATR. Periksa timestamp, spread broker, dan kondisi eksekusi sebelum trading.")
    st.write("Twelve Data memiliki batas request dan kemungkinan delay. Data ini bukan tick-by-tick.")
