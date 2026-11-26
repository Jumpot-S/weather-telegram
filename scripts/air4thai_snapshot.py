#!/usr/bin/env python3
"""ดึงข้อมูลสถานีตรวจวัดจาก Air4Thai แล้วเก็บเฉพาะฟิลด์ที่เว็บแอปใช้ลงไฟล์ JSON

ใช้โดย workflow air4thai-cache.yml เพื่อให้หน้าเว็บอ่านข้อมูลได้ แม้เบราว์เซอร์ดึงจาก Air4Thai ตรงไม่ได้ (เช่นติด CORS)
วิธีใช้: python3 scripts/air4thai_snapshot.py OUTPUT.json
"""
import json
import ssl
import sys
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

URL = "air4thai.pcd.go.th/services/getNewAQI_JSON.php"


def fetch():
    for scheme in ("https", "http"):
        try:
            with urlopen(Request(f"{scheme}://{URL}", headers={"User-Agent": "weather-telegram/1.0"}), timeout=30) as r:
                d = json.load(r)
            if d.get("stations"):
                return d["stations"]
        except (URLError, HTTPError, TimeoutError, ValueError, ssl.SSLError, OSError) as e:
            print(f"{scheme} failed: {e}", file=sys.stderr)
    return None


def pick(d, *keys):
    return {k: d[k] for k in keys if isinstance(d, dict) and k in d}


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: air4thai_snapshot.py OUTPUT.json")
    stations = fetch()
    if not stations:
        sys.exit("ดึงข้อมูลจาก Air4Thai ไม่สำเร็จ")
    out = []
    for s in stations:
        L = s.get("AQILast") or {}
        if not (L.get("PM25") or {}).get("value"):
            continue
        out.append({**pick(s, "stationID", "nameTH", "areaTH", "lat", "long"),
                    "AQILast": {**pick(L, "date", "time"),
                                "PM25": pick(L["PM25"], "value", "aqi", "color_id"),
                                "PM10": pick(L.get("PM10"), "value"),
                                "AQI": pick(L.get("AQI"), "aqi", "param")}})
    now = datetime.now(timezone(timedelta(hours=7)))
    with open(sys.argv[1], "w", encoding="utf-8") as f:
        json.dump({"updated": now.isoformat(timespec="minutes"), "stations": out}, f, ensure_ascii=False, separators=(",", ":"))
    print(f"saved {len(out)} stations")


if __name__ == "__main__":
    main()
