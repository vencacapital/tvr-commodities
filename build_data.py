"""TVR Commodity Dashboard - data builder"""
import io
import os
import json
import time
import zipfile
import datetime as dt
from urllib.request import urlopen, Request
import pandas as pd

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "*/*",
}

UNIVERSE = [
    ("WTI Crude", "Energy", "CL=F", "cl.f", "067651"),
    ("Brent Crude", "Energy", "BZ=F", "cb.f", None),
    ("Natural Gas", "Energy", "NG=F", "ng.f", "023651"),
    ("RBOB Gasoline", "Energy", "RB=F", "rb.f", "111659"),
    ("Heating Oil", "Energy", "HO=F", "ho.f", "022651"),
    ("Gold", "Metals", "GC=F", "gc.f", "088691"),
    ("Silver", "Metals", "SI=F", "si.f", "084691"),
    ("Copper", "Metals", "HG=F", "hg.f", "085692"),
    ("Platinum", "Metals", "PL=F", "pl.f", "076651"),
    ("Palladium", "Metals", "PA=F", "pa.f", "075651"),
    ("Wheat (Chicago)", "Grains", "ZW=F", "zw.f", "001602"),
    ("Corn", "Grains", "ZC=F", "zc.f", "002602"),
    ("Soybeans", "Grains", "ZS=F", "zs.f", "005602"),
    ("Soybean Oil", "Grains", "ZL=F", "zl.f", "007601"),
    ("Soybean Meal", "Grains", "ZM=F", "zm.f", "026603"),
    ("Sugar", "Softs", "SB=F", "sb.f", "080732"),
    ("Coffee", "Softs", "KC=F", "kc.f", "083731"),
    ("Cocoa", "Softs", "CC=F", "cc.f", "073732"),
    ("Cotton", "Softs", "CT=F", "ct.f", "033661"),
    ("Live Cattle", "Livestock", "LE=F", "le.f", "057642"),
    ("Lean Hogs", "Livestock", "HE=F", "he.f", "054642"),
]

errors = []


def get(url, timeout=60):
    return urlopen(Request(url, headers=UA), timeout=timeout).read()


def clean(df):
    df = df.dropna(subset=["Close"])
    df = df[df["Close"] > 0]
    df["Date"] = pd.to_datetime(df["Date"]).dt.normalize()
    df = df.drop_duplicates(subset=["Date"], keep="last")
    df = df.sort_values("Date").reset_index(drop=True)
    return df


def yahoo(sym):
    q = sym.replace("=", "%3D")
    now = int(time.time())
    tail = q + "?period1=0&period2=" + str(now) + "&interval=1d"
    urls = [
        "https://query1.finance.yahoo.com/v8/finance/chart/" + tail,
        "https://query2.finance.yahoo.com/v8/finance/chart/" + tail,
    ]
    last = "unknown"
    for u in urls:
        try:
            j = json.loads(get(u).decode("utf-8", "replace"))
            res = j["chart"]["result"][0]
            df = clean(pd.DataFrame({
                "Date": pd.to_datetime(res["timestamp"], unit="s"),
                "Close": res["indicators"]["quote"][0]["close"],
            }))
            if len(df) >= 60:
                return df
            last = "only " + str(len(df)) + " rows"
        except Exception as e:
            last = str(e)
        time.sleep(1)
    raise ValueError("yahoo: " + last)


def stooq(sym):
    txt = get("https://stooq.com/q/d/l/?s=" + sym + "&i=d").decode("utf-8", "replace")
    if "Date" not in txt[:40]:
        raise ValueError("no data returned")
    df = clean(pd.read_csv(io.StringIO(txt))[["Date", "Close"]])
    if len(df) < 60:
        raise ValueError("only " + str(len(df)) + " rows")
    return df


def fetch_prices(ysym, ssym):
    try:
        return yahoo(ysym), "yahoo"
    except Exception as e1:
        try:
            return stooq(ssym), "stooq"
        except Exception as e2:
            raise ValueError(str(e1) + " | stooq: " + str(e2))


def price_on_or_before(s, target):
    w = s[s.index <= target]
    if len(w) == 0:
        return None, None
    return float(w.iloc[-1]), w.index[-1]


def price_stats(df):
    s = df.set_index("Date")["Close"]
    end = s.index[-1]
    today = pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()
    stale_days = (today - end).days
    if stale_days > 7:
        raise ValueError("stale: last price " + end.date().isoformat())
    last = float(s.iloc[-1])
    first = s.index[0]
    span_days = (end - first).days
    out = {}
    out["last"] = round(last, 4)
    out["asof"] = end.date().isoformat()
    out["hist_start"] = first.date().isoformat()
    out["hist_years"] = round(span_days / 365.25, 1)
    out["stale_days"] = int(stale_days)
    out["chg_1w"] = None
    prev, prevdate = price_on_or_before(s, end - pd.Timedelta(days=7))
    if prev and (end - prevdate).days <= 12:
        out["chg_1w"] = round((last / prev - 1) * 100, 2)
    out["chg_1m"] = None
    prev, prevdate = price_on_or_before(s, end - pd.DateOffset(months=1))
    if prev and (end - prevdate).days <= 40:
        out["chg_1m"] = round((last / prev - 1) * 100, 2)
    for yrs in (3, 5):
        key = "vs_" + str(yrs) + "y"
        out[key] = None
        if span_days >= yrs * 365 - 60:
            w = s[s.index >= end - pd.DateOffset(years=yrs)]
            if len(w) > 400:
                out[key] = round((last / float(w.mean()) - 1) * 100, 2)
    out["rank_5y"] = None
    if span_days >= 5 * 365 - 60:
        w5 = s[s.index >= end - pd.DateOffset(years=5)]
        if len(w5) > 400:
            out["rank_5y"] = round(float((w5 <= last).mean() * 100), 0)
    out["seas_avg"] = None
    out["seas_hit"] = None
    out["seas_n"] = None
    if span_days >= 8 * 365:
        m = s.resample("ME").last()
        if m.index[-1].month == end.month and m.index[-1].year == end.year:
            m = m.iloc[:-1]
        r = m.pct_change().dropna()
        r = r[r.index >= end - pd.DateOffset(years=15)]
        sel = r[r.index.month == end.month]
        if len(sel) >= 8:
            out["seas_avg"] = round(float(sel.mean() * 100), 2)
            out["seas_hit"] = round(float((sel > 0).mean() * 100), 0)
            out["seas_n"] = int(len(sel))
    return out


def load_cot():
    frames = []
    yr = dt.date.today().year
    for y in (yr - 3, yr - 2, yr - 1, yr):
        try:
            raw = get("https://www.cftc.gov/files/dea/history/fut_disagg_txt_" + str(y) + ".zip", 120)
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
    df = df.dropna(subset=["date", "net"]).sort_values("date")
    print("COT rows loaded: " + str(len(df)))
    return df


def cot_stats(cot, code):
    out = {}
    if cot is None or not code:
        return out
    d = cot[cot["code"] == code]
    if d.empty:
        errors.append("COT code " + str(code) + " not found")
        return out
    net = float(d["net"].iloc[-1])
    prev = float(d["net"].iloc[-2]) if len(d) > 1 else None
    w = d[d["date"] >= d["date"].iloc[-1] - pd.DateOffset(years=3)]
    out["cot_net"] = int(net)
    out["cot_chg"] = int(net - prev) if prev is not None else None
    out["cot_rank_3y"] = round(float((w["net"] <= net).mean() * 100), 0)
    out["cot_n"] = int(len(w))
    out["cot_date"] = d["date"].iloc[-1].date().isoformat()
    return out


def main():
    cot = load_cot()
    rows = []
    for name, group, ysym, ssym, code in UNIVERSE:
        try:
            df, src = fetch_prices(ysym, ssym)
            r = {}
            r["name"] = name
            r["group"] = group
            r["source"] = src
            r.update(price_stats(df))
            r.update(cot_stats(cot, code))
            rows.append(r)
            print("OK   " + name.ljust(17) + " last " + str(r["last"]).rjust(10)
                  + "  1w " + str(r["chg_1w"]).rjust(7) + "%  seas " + str(r["seas_avg"]).rjust(7)
                  + "  cotN " + str(r.get("cot_n", "-")))
        except Exception as e:
            errors.append(name + ": " + str(e))
            print("FAIL " + name + ": " + str(e))
        time.sleep(1)
    out = {}
    out["generated_utc"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    out["month"] = dt.date.today().strftime("%B")
    out["rows"] = rows
    out["errors"] = errors
        os.makedirs("data", exist_ok=True)
    with open("data/pending.json", "w") as f:
        json.dump(out, f, indent=1)
    print("")
    print("--- DIAGNOSTIC REPORT ---")
    print(str(len(rows)) + " of " + str(len(UNIVERSE)) + " instruments built")
    print(str(len([x for x in rows if "cot_net" in x])) + " have COT data")
    print(str(len([x for x in rows if x.get("seas_avg") is not None])) + " have seasonality")
        for e in errors:
        print("ISSUE: " + e)
    return rows


def validate(rows):
    """Refuse to publish data that fails basic sanity checks."""
    fatal = []
    warn = []
    expected = len(UNIVERSE)

    if len(rows) < expected - 2:
        fatal.append("only " + str(len(rows)) + " of " + str(expected) + " instruments built")

    stale = [r["name"] for r in rows if r.get("stale_days", 0) > 5]
    if len(stale) > 3:
        fatal.append("stale prices: " + ", ".join(stale))
    elif stale:
        warn.append("stale prices: " + ", ".join(stale))

    nocot = [r["name"] for r in rows if "cot_net" not in r and r["name"] != "Brent Crude"]
    if len(nocot) > 3:
        fatal.append("missing COT: " + ", ".join(nocot))
    elif nocot:
        warn.append("missing COT: " + ", ".join(nocot))

    noseas = [r["name"] for r in rows if r.get("seas_avg") is None]
    if len(noseas) > 3:
        fatal.append("missing seasonality: " + ", ".join(noseas))
    elif noseas:
        warn.append("missing seasonality: " + ", ".join(noseas))

    for r in rows:
        w = r.get("chg_1w")
        if w is not None and abs(w) > 35:
            fatal.append(r["name"] + " 1w move of " + str(w) + "% is implausible")
        elif w is not None and abs(w) > 15:
            warn.append(r["name"] + " 1w move " + str(w) + "%")
        if r.get("last") is not None and r["last"] <= 0:
            fatal.append(r["name"] + " price is " + str(r["last"]))

    print("")
    print("--- VALIDATION ---")
    for w in warn:
        print("WARN:  " + w)
    for f in fatal:
        print("FATAL: " + f)
    if not warn and not fatal:
        print("All checks passed.")
    return fatal


rows = main()
problems = validate(rows)
if problems:
    print("")
    print("Data NOT published - previous good data left in place.")
    raise SystemExit(1)
print("")
import shutil
shutil.move("data/pending.json", "data/commodities.json")
print("Data published.")
