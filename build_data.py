"""TVR Commodity Dashboard - data builder"""
import io, json, zipfile, datetime as dt
from urllib.request import urlopen, Request
import pandas as pd
import numpy as np

UA = {"User-Agent": "Mozilla/5.0"}

# name, group, stooq symbol, CFTC contract code (None = no COT)
UNIVERSE = [
    ("WTI Crude",      "Energy",  "cl.f", "067651"),
    ("Brent Crude",    "Energy",  "cb.f", None),
    ("Natural Gas",    "Energy",  "ng.f", "023651"),
    ("RBOB Gasoline",  "Energy",  "rb.f", "111659"),
    ("Heating Oil",    "Energy",  "ho.f", "022651"),
    ("Gold",           "Metals",  "gc.f", "088691"),
    ("Silver",         "Metals",  "si.f", "084691"),
    ("Copper",         "Metals",  "hg.f", "085692"),
    ("Platinum",       "Metals",  "pl.f", "076651"),
    ("Palladium",      "Metals",  "pa.f", "075651"),
    ("Wheat (Chicago)","Grains",  "zw.f", "001602"),
    ("Corn",           "Grains",  "zc.f", "002602"),
    ("Soybeans",       "Grains",  "zs.f", "005602"),
    ("Soybean Oil",    "Grains",  "zl.f", "007601"),
    ("Soybean Meal",   "Grains",  "zm.f", "026603"),
    ("Sugar",          "Softs",   "sb.f", "080732"),
    ("Coffee",         "Softs",   "kc.f", "083731"),
    ("Cocoa",          "Softs",   "cc.f", "073732"),
    ("Cotton",         "Softs",   "ct.f", "033661"),
    ("Live Cattle",    "Livestock","le.f","057642"),
    ("Lean Hogs",      "Livestock","he.f","054642"),
]

errors = []

def get(url, timeout=90):
    return urlopen(Request(url, headers=UA), timeout=timeout).read()

def stooq(sym):
    txt = get(f"https://stooq.com/q/d/l/?s={sym}&i=d").decode("utf-8", "replace")
    if "Date" not in txt[:40]:
        raise ValueError("no data returned")
    df = pd.read_csv(io.StringIO(txt))
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.dropna(subset=["Close"]).sort_values("Date").reset_index(drop=True)
    if len(df) < 60:
        raise ValueError(f"only {len(df)} rows")
    return df[["Date", "Close"]]

def price_stats(df):
    s = df.set_index("Date")["Close"]
    last = float(s.iloc[-1])
    asof = s.index[-1].date().isoformat()
    out = {"last": round(last, 4), "asof": asof}
    out["chg_1w"] = round((last / float(s.iloc[-6]) - 1) * 100, 2) if len(s) > 6 else None
    end = s.index[-1]
    for yrs, key in ((3, "vs_3y"), (5, "vs_5y")):
        w = s[s.index >= end - pd.DateOffset(years=yrs)]
        out[key] = round((last / float(w.mean()) - 1) * 100, 2) if len(w) > 200 else None
    w5 = s[s.index >= end - pd.DateOffset(years=5)]
    out["rank_5y"] = round(float((w5 <= last).mean() * 100), 0) if len(w5) > 200 else None
    m = s.resample("ME").last()
    r = m.pct_change().dropna()
    r = r[r.index >= end - pd.DateOffset(years=15)]
    cur = end.month
    sel = r[r.index.month == cur]
    if len(sel) >= 5:
        out["seas_avg"] = round(float(sel.mean() * 100), 2)
        out["seas_hit"] = round(float((sel > 0).mean() * 100), 0)
        out["seas_n"] = int(len(sel))
    else:
        out["seas_avg"] = out["seas_hit"] = out["seas_n"] = None
    return out

def load_cot():
    frames = []
    yr = dt.date.today().year
    for y in (yr - 3, yr - 2, yr - 1, yr):
        try:
            z = zipfile.ZipFile(io.BytesIO(
                get(f"https://www.cftc.gov/files/dea/history/fut_disagg_txt_{y}.zip")))
            nm = [n for n in z.namelist() if n.lower().endswith(".txt")][0]
            frames.append(pd.read_csv(z.open(nm), low_memory=False))
        except Exception as e:
            errors.append(f"COT {y}: {e}")
    if not frames:
        return None
    df = pd.concat(frames, ignore_index=True)
    df.columns = [c.strip() for c in df.columns]
    def find(*keys):
        for c in df.columns:
            k = c.replace(" ", "_").lower()
            if all(x in k for x in keys):
                return c
        return None
    code = find("contract", "market", "code")
    date = find("report", "date") or find("as_of")
    lng = find("m_money", "long", "all")
    sht = find("m_money", "short", "all")
    if not all([code, date, lng, sht]):
        errors.append(f"COT columns not found: {code},{date},{lng},{sht}")
        return None
    df = df[[code, date, lng, sht]].copy()
    df.columns = ["code", "date", "long", "short"]
    df["code"] = df["code"].astype(str).str.strip().str.zfill(6)
    df["date"] = pd.to_datetime(df["date"], errors="coerce", format="mixed")
    df["net"] = pd.to_numeric(df["long"], errors="coerce") - pd.to_numeric(df["short"], errors="coerce")
    return df.dropna(subset=["date", "net"]).sort_values("date")

def cot_stats(cot, code):
    if cot is None or not code:
        return {}
    d = cot[cot["code"] == code]
    if d.empty:
        errors.append(f"COT code {code} not found")
        return {}
    net = float(d["net"].iloc[-1])
    return {"cot_net": int(net),
