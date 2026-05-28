#!/usr/bin/env python3
import csv, json, requests
from datetime import datetime, timezone
from pathlib import Path

CITIES = [
    {"name": "Istanbul",  "mgm_id": 93401, "lat": 41.01, "lon": 28.98},
    {"name": "Izmir",     "mgm_id": 93501, "lat": 38.42, "lon": 27.14},
    {"name": "Antalya",   "mgm_id": 90701, "lat": 36.88, "lon": 30.70},
    {"name": "Ankara",    "mgm_id": 90601, "lat": 39.93, "lon": 32.87},
    {"name": "Trabzon",   "mgm_id": 96101, "lat": 41.00, "lon": 39.73},
    {"name": "Erzurum",   "mgm_id": 92501, "lat": 39.91, "lon": 41.28},
    {"name": "Gaziantep", "mgm_id": 92701, "lat": 37.07, "lon": 37.38},
]

MGM_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://www.mgm.gov.tr",
    "Origin": "https://www.mgm.gov.tr",
}

DATA_DIR = Path("data")
OBS_FILE  = DATA_DIR / "observations.csv"
FC_FILE   = DATA_DIR / "forecasts.csv"

OBS_COLS = ["timestamp_utc","city","mgm_id","source","condition","temperature","cloud","precip_1h","precip_6h","humidity"]
FC_COLS  = ["collected_at_utc","city","mgm_id","forecast_for_utc","source","condition","temperature"]

def ensure_csv(path, cols):
    if not path.exists():
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(cols)

def append_rows(path, rows):
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for r in rows: w.writerow(r)

def mgm_obs(city):
    try:
        r = requests.get(f"https://servis.mgm.gov.tr/web/sondurumlar?merkezid={city['mgm_id']}",
                         headers=MGM_HEADERS, timeout=10)
        d = r.json()[0]
        return {"condition": d.get("hadiseKodu",""), "temp": d.get("sicaklik",""),
                "cloud": d.get("kapalilik",""), "p1": d.get("yagis1Saat",0),
                "p6": d.get("yagis6Saat",0), "hum": d.get("nem","")}
    except Exception as e:
        print(f"  MGM obs error {city['name']}: {e}"); return None

def mgm_forecast(city):
    try:
        r = requests.get(f"https://servis.mgm.gov.tr/web/tahminler/saatlik?merkezid={city['mgm_id']}",
                         headers=MGM_HEADERS, timeout=10)
        d = r.json()
        items = d[0]["tahmin"] if isinstance(d, list) else d["tahmin"]
        return [{"for": i["tarih"][:16], "cond": i["hadise"], "temp": i["sicaklik"]} for i in items]
    except Exception as e:
        print(f"  MGM fc error {city['name']}: {e}"); return []

def om_data(city):
    url = (f"https://api.open-meteo.com/v1/dwd-icon"
           f"?latitude={city['lat']}&longitude={city['lon']}"
           f"&current=temperature_2m,weather_code,precipitation,cloud_cover,relative_humidity_2m"
           f"&hourly=temperature_2m,weather_code,precipitation_probability,cloud_cover"
           f"&timezone=UTC&forecast_days=2")
    try:
        d = requests.get(url, timeout=10).json()
        cur = d.get("current", {})
        h   = d.get("hourly", {})
        return {
            "current": {"cond": cur.get("weather_code"), "temp": cur.get("temperature_2m"),
                        "cloud": cur.get("cloud_cover"), "p": cur.get("precipitation",0),
                        "hum": cur.get("relative_humidity_2m")},
            "hourly":  {"times": h.get("time",[]), "codes": h.get("weather_code",[]),
                        "temps": h.get("temperature_2m",[])}
        }
    except Exception as e:
        print(f"  OM error {city['name']}: {e}"); return None

def main():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")
    DATA_DIR.mkdir(exist_ok=True)
    ensure_csv(OBS_FILE, OBS_COLS)
    ensure_csv(FC_FILE,  FC_COLS)

    obs_rows, fc_rows = [], []

    for city in CITIES:
        print(f"{city['name']}...")

        o = mgm_obs(city)
        if o:
            obs_rows.append([now, city["name"], city["mgm_id"], "MGM",
                             o["condition"], o["temp"], o["cloud"], o["p1"], o["p6"], o["hum"]])

        for f in mgm_forecast(city):
            fc_rows.append([now, city["name"], city["mgm_id"],
                            f["for"], "MGM", f["cond"], f["temp"]])

        om = om_data(city)
        if om:
            c = om["current"]
            obs_rows.append([now, city["name"], city["mgm_id"], "OpenMeteo",
                             c["cond"], c["temp"], c["cloud"], c["p"], "", c["hum"]])
            h = om["hourly"]
            for t, code, temp in zip(h["times"], h["codes"], h["temps"]):
                fc_rows.append([now, city["name"], city["mgm_id"],
                                t, "OpenMeteo", code, temp])

    append_rows(OBS_FILE, obs_rows)
    append_rows(FC_FILE,  fc_rows)
    print(f"Done: {len(obs_rows)} obs, {len(fc_rows)} forecasts.")

if __name__ == "__main__":
    main()
