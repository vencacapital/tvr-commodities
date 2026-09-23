"""TVR Commodity Dashboard - data builder"""
import io
import os
import json
import zipfile
import datetime as dt
from urllib.request import urlopen, Request
import pandas as pd

UA = {"User-Agent": "Mozilla/5.0"}

UNIVERSE = [
    ("WTI Crude", "Energy", "cl.f", "067651"),
    ("Brent Crude", "Energy", "cb.f", None),
    ("Natural Gas", "Energy", "ng.f", "023651"),
    ("RBOB Gasoline", "Energy", "rb.f", "111659"),
    ("Heating Oil", "Energy", "ho.f", "022651"),
    ("Gold", "Metals", "gc.f", "088691"),
    ("Silver", "Metals", "si.f", "084691"),
    ("Copper", "Metals", "hg.f", "085692"),
    ("Platinum", "Metals", "pl.f", "076651"),
    ("Palladium", "Metals", "pa.f", "075651"),
    ("Wheat (Chicago)", "Grains", "zw.f", "001602"),
    ("Corn", "Grains", "zc.f", "002602"),
    ("Soybeans", "Grains", "zs.f", "005602"),
    ("Soybean Oil", "Grains", "zl.f", "007601"),
    ("Soybean Meal", "Grains", "zm.f", "026603"),
    ("Sugar", "Softs", "sb.f", "080732"),
    ("Coffee", "Softs", "kc.f", "083731"),
    ("Cocoa", "Softs", "cc.f", "073732"),
    ("Cotton", "Softs", "ct.f", "033661"),
    ("Live Cattle", "Livestock", "le.f", "057642"),
    ("Lean Hogs", "Livestock", "he.f", "054642"),
]

errors = []


def get(url, timeout=90):
    return urlopen(Request(url, headers=UA), timeout=timeout).read()


def stooq(sym):
    txt = get("https://stooq.com/q/d/l/?s=" + sym + "&i=d").decode("utf-8", "replace")
    if "Date" not in txt[:40]:
        raise ValueError("no data returned")
    df = pd.read_csv(io.StringIO(txt))
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.dropna(subset=["Close"]).sort_values("Date").reset_index(drop=True)
    if len(df) < 60:
        raise ValueError("only " + str(len(df)) + " rows")
    return df[["Date", "Close"]]


def price_stats(df):
    s = df.set_index("Date")["Close"]
    last = float(s.iloc[-1])
    end = s.index[-1]
    out = {}
    out["last"] = round(last, 4)
    out["asof"] = end.date().isoformat()
    out["chg_1w"] = None
    if len(s) > 6:
        out["chg_1w"] = round((last / float(s.iloc[-6]) - 1) * 100, 2)
    for yrs in (3, 5):
        key = "vs_" + str(yrs) + "y"
        w = s[s.index >= end - pd.DateOffset(years=yrs)]
        out[key] = None
        if len(w) > 200:
            out[key] = round((last / float(w.mean()) - 1) * 100, 2)
    w5 = s[s.index >= end - pd.DateOffset(years=5)]
    out["rank_5y"] = None
    if len(w5) > 200:
        out["rank_5y"] = round(float((w5 <= last).mean() * 100), 0)
    m = s.resample("ME").last()
    r = m.pct_change().dropna()
    r = r[r.index >= end - pd.DateOffset(years=15)]
    sel = r[r.index.month == end.month]
    out["seas_avg"] = None
    out["seas_hit"] = None
    out["seas_n"] = None
    if len(sel) >= 5:
        out["seas_avg"] = round(float(sel.mean() * 100), 2)
        out["seas_hit"] = round(float((sel > 0).mean() * 100), 0)
        out["seas_n"] = int(len(sel))
    return out


def load_cot():
    frames = []
    yr = dt.date.today().year
    for y in (yr - 3, yr - 2, yr - 1, yr):
        try:
            raw = get("https://www.cftc.gov/files/dea/history/fut_disagg_txt_" + str(y) + ".zip")
            z = zipfile.ZipFile(io.BytesIO(raw))
            names = [n for n in z.namelist() if n.lower().endswith(".txt")]
            frames.append(pd.read_csv(z.open(names[0]), low_memory=False))
        except Exception as e:
            errors.append("COT " + str(y) + ": " + str(e))
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
    date = find("report", "date")
    if date is None:
        date = find("as_of")
    lng = find("m_money", "long", "all")
    sht = find("m_money", "short", "all")
    if code is None or date is None or lng is None or sht is None:
        errors.append("COT columns not found")
        return None
    df = df[[code, date, lng, sht]].copy()
    df.columns = ["code", "date", "long", "short"]
    df["code"] = df["code"].astype(str).str.strip().str.zfill(6)
    df["date"] = pd.to_datetime(df["date"], errors="coerce", format="mixed")
    df["net"] = pd.to_numeric(df["long"], errors="coerce") - pd.to_numeric(df["short"], errors="coerce")
    return df.dropna(subset=["date", "net"]).sort_values("date")


def cot_stats(cot, code):
    out = {}
    if cot is None or not code:
        return out
    d = cot[cot["code"] == code]
    if d.empty:
        errors.append("COT code " + str(code) + " not found")
        return out
    net = float(d["net"].iloc[-1])
    out["cot_net"] = int(net)
    out["cot_rank_3y"] = round(float((d["net"] <= net).mean() * 100), 0)
    out["cot_date"] = d["date"].iloc[-1].date().isoformat()
    return out


def main():
    cot = load_cot()
    rows = []
    for name, group, sym, code in UNIVERSE:
        try:
            r = {}
            r["name"] = name
            r["group"] = group
            r.update(price_stats(stooq(sym)))
            r.update(cot_stats(cot, code))
            rows.append(r)
            print("OK   " + name)
        except Exception as e:
            errors.append(name + " (" + sym + "): " + str(e))
            print("FAIL " + name + ": " + str(e))
    out = {}
    out["generated_utc"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    out["month"] = dt.date.today().strftime("%B")
    out["rows"] = rows
    out["errors"] = errors
    os.makedirs("data", exist_ok=True)
    with open("data/commodities.json", "w") as f:
        json.dump(out, f, indent=1)
    print("")
    print("--- DIAGNOSTIC REPORT ---")
    print(str(len(rows)) + " of " + str(len(UNIVERSE)) + " instruments built")
    for e in errors:
        print("ISSUE: " + e)


main()
