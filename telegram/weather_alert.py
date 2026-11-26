#!/usr/bin/env python3
"""ส่งสรุปสภาพอากาศ PM2.5 ฝน UV เข้า Telegram (ใช้ Open-Meteo ไม่ต้องมี API key)

ตัวแปรสภาพแวดล้อม:
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID  (จำเป็น)
  PLACE_NAME  ชื่อสถานที่ที่แสดง   (ค่าเริ่มต้น: นครพนม (อ.เมือง))
  LAT, LON    พิกัด               (ค่าเริ่มต้น: 17.4105, 104.7783)
  PM_THRESHOLD, HEAT_THRESHOLD, RAIN_THRESHOLD, UV_THRESHOLD  เกณฑ์แจ้งเตือน
  RADAR_URL   ลิงก์เรดาร์ฝนที่แนบท้ายข้อความ (ค่าเริ่มต้น เรดาร์สกลนครสำหรับนครพนม)
  WEATHER_MODEL  แบบจำลองสภาพอากาศของ Open-Meteo เช่น ecmwf_ifs025 (เว้นว่าง = อัตโนมัติ)
  STATION_ID  รหัสสถานี Air4Thai (ค่าเริ่มต้น 88t = นครพนม อ.เมือง ถ้าเว้นว่างและเปลี่ยน LAT/LON จะเลือกสถานีที่ใกล้ที่สุดภายใน 30 กม.)
  SEND_TIMES  เวลาส่งตามเวลาไทย คั่นด้วยจุลภาค (ค่าเริ่มต้น: 05:00,11:00,15:00,18:00,21:00)
  DRY_RUN=1   พิมพ์ข้อความแทนการส่งจริง

เมื่อรันจาก schedule ของ GitHub Actions สคริปต์จะรอจนถึงเวลาไทยที่ใกล้ที่สุดใน SEND_TIMES
(workflow เริ่มก่อนเวลา 15 นาทีเพื่อชดเชยความล่าช้าของคิว) ถ้ารันช้ากว่าเวลา จะส่งทันที
"""
import html
import json
import math
import os
import ssl
import sys
import time
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BKK = timezone(timedelta(hours=7))


def env(name, default):
    v = os.getenv(name)
    return v.strip() if v and v.strip() else default


PLACE = env("PLACE_NAME", "นครพนม (อ.เมือง)")
LAT = float(env("LAT", "17.4105"))
LON = float(env("LON", "104.7783"))
DEFAULT_AREA = env("LAT", "") == "" and env("LON", "") == ""
STATION_ID = env("STATION_ID", "88t" if DEFAULT_AREA else "")
RADAR_URL = env("RADAR_URL", "https://weather.tmd.go.th/sknloop.php" if DEFAULT_AREA else "https://weather.tmd.go.th/composite/index_composite.html")
MODEL_Q = f"&models={env('WEATHER_MODEL', '')}" if env("WEATHER_MODEL", "") else ""
TH_PM = float(env("PM_THRESHOLD", "37.5"))
TH_HEAT = float(env("HEAT_THRESHOLD", "38"))
TH_RAIN = float(env("RAIN_THRESHOLD", "60"))
TH_UV = float(env("UV_THRESHOLD", "8"))

WX = {0: "ท้องฟ้าแจ่มใส", 1: "แจ่มใสเป็นส่วนใหญ่", 2: "มีเมฆบางส่วน", 3: "เมฆมาก",
      45: "มีหมอก", 48: "หมอกจัด", 51: "ฝนปรอย", 53: "ฝนปรอย", 55: "ฝนปรอยหนัก",
      56: "ฝนปรอยเยือกแข็ง", 57: "ฝนปรอยเยือกแข็ง", 61: "ฝนเล็กน้อย", 63: "ฝนปานกลาง",
      65: "ฝนหนัก", 66: "ฝนเยือกแข็ง", 67: "ฝนเยือกแข็ง", 80: "ฝนตกเป็นช่วง",
      81: "ฝนตกเป็นช่วง", 82: "ฝนตกหนักเป็นช่วง", 95: "พายุฟ้าคะนอง",
      96: "พายุฟ้าคะนองลูกเห็บ", 99: "พายุฟ้าคะนองลูกเห็บ"}

# เกณฑ์ PM2.5 กรมควบคุมมลพิษ (µg/m³)
PM_LEVELS = [
    (15, "🟢", "ดีมาก", "อากาศดี ทำกิจกรรมกลางแจ้งได้ตามปกติ"),
    (25, "🟢", "ดี", "ทำกิจกรรมกลางแจ้งได้"),
    (37.5, "🟡", "ปานกลาง", "กลุ่มเสี่ยงควรสังเกตอาการ"),
    (75, "🟠", "เริ่มมีผลต่อสุขภาพ", "ควรสวมหน้ากาก N95 เมื่อออกนอกอาคาร ลดกิจกรรมกลางแจ้ง"),
    (float("inf"), "🔴", "มีผลต่อสุขภาพ", "งดกิจกรรมกลางแจ้ง สวมหน้ากาก N95 และอยู่ในห้องปิด"),
]
UV_LEVELS = [(3, "ต่ำ"), (6, "ปานกลาง"), (8, "สูง"), (11, "สูงมาก"), (float("inf"), "อันตราย")]


def get_json(url, tries=3):
    last = None
    for i in range(tries):
        try:
            with urlopen(Request(url, headers={"User-Agent": "weather-telegram/1.0"}), timeout=20) as r:
                return json.load(r)
        except (URLError, HTTPError, TimeoutError, ValueError) as e:
            last = e
            time.sleep(2 * (i + 1))
    print(f"fetch failed: {url.split('?')[0]} -> {last}", file=sys.stderr)
    return None


def fetch():
    q = urlencode({"latitude": LAT, "longitude": LON, "timezone": "Asia/Bangkok"})
    w = get_json(
        "https://api.open-meteo.com/v1/forecast?" + q + MODEL_Q
        + "&current=temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,weather_code,wind_speed_10m"
        + "&hourly=temperature_2m,apparent_temperature,precipitation_probability,uv_index,weather_code"
        + "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum,uv_index_max"
        + "&forecast_days=2")
    a = get_json("https://air-quality-api.open-meteo.com/v1/air-quality?" + q
                 + "&current=pm2_5,pm10&hourly=pm2_5&forecast_days=2")
    return w, a


A4T = "air4thai.pcd.go.th/services/getNewAQI_JSON.php"


def num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f >= 0 else None


def km(lat1, lon1, lat2, lon2):
    r = math.radians
    a = math.sin(r(lat2 - lat1) / 2) ** 2 + math.cos(r(lat1)) * math.cos(r(lat2)) * math.sin(r(lon2 - lon1) / 2) ** 2
    return 12742 * math.asin(math.sqrt(a))


def fetch_air4thai():
    """ดึงค่าจากสถานีตรวจวัดจริงของกรมควบคุมมลพิษ

    เซิร์ฟเวอร์ Air4Thai ส่งใบรับรอง SSL ไม่ครบสาย ลองตรวจใบรับรองตามปกติก่อน (workflow เพิ่มใบกลางให้แล้ว)
    ถ้ายังไม่ผ่าน จึงลองแบบไม่ตรวจใบรับรองเป็นทางสุดท้าย ข้อมูลนี้เป็นค่าคุณภาพอากาศสาธารณะ อ่านอย่างเดียว
    """
    loose = ssl.create_default_context()
    loose.check_hostname = False
    loose.verify_mode = ssl.CERT_NONE
    for label, ctx in (("verified", None), ("unverified", loose)):
        try:
            req = Request(f"https://{A4T}", headers={"User-Agent": "weather-telegram/1.0"})
            with urlopen(req, timeout=25, context=ctx) as r:
                d = json.load(r)
            if d.get("stations"):
                if label == "unverified":
                    print("เตือน: ดึง Air4Thai โดยไม่ตรวจใบรับรอง SSL (เซิร์ฟเวอร์ส่งใบรับรองไม่ครบ)", file=sys.stderr)
                return d["stations"]
        except (URLError, HTTPError, TimeoutError, ValueError, ssl.SSLError, OSError) as e:
            print(f"air4thai {label} failed: {e}", file=sys.stderr)
    return None


def fresh(st):
    if st and st.get("age") is not None and st["age"] > 24:
        print(f"ข้อมูลสถานี {st['id']} เก่าเกิน 24 ชม. ใช้ค่าแบบจำลองแทน", file=sys.stderr)
        return None
    return st


def pick_station(stations):
    if not stations:
        return None
    ok = []
    for s in stations:
        try:
            pm = num(s["AQILast"]["PM25"]["value"])
            la, lo = float(s["lat"]), float(s["long"])
        except (KeyError, TypeError, ValueError):
            continue
        if pm is not None:
            ok.append((s, km(LAT, LON, la, lo)))
    if STATION_ID:
        for s, d in ok:
            if s.get("stationID") == STATION_ID:
                return fresh(build_station(s, d))
        print(f"ไม่พบข้อมูลสถานี {STATION_ID} ใน Air4Thai ตอนนี้", file=sys.stderr)
    near = sorted((x for x in ok if x[1] <= 30), key=lambda x: x[1])
    return fresh(build_station(*near[0])) if near and not STATION_ID else None


def age_hours(date, time_):
    try:
        t = datetime.strptime(f"{date} {time_}", "%Y-%m-%d %H:%M").replace(tzinfo=BKK)
    except ValueError:
        return None
    return (datetime.now(BKK) - t).total_seconds() / 3600


def build_station(s, d):
    L = s["AQILast"]
    return {"id": s.get("stationID"), "area": s.get("areaTH") or s.get("nameTH") or "",
            "pm25": num(L["PM25"]["value"]), "pm10": num((L.get("PM10") or {}).get("value")),
            "aqi": num((L.get("AQI") or {}).get("aqi")), "date": L.get("date", ""), "time": L.get("time", ""), "km": d,
            "age": age_hours(L.get("date", ""), L.get("time", ""))}


def pm_level(v):
    return next(l for l in PM_LEVELS if v <= l[0])


def uv_label(v):
    return next(l[1] for l in UV_LEVELS if v < l[0])


def hum_label(h):
    if h is None:
        return ""
    for limit, text in ((30, "แห้งมาก 🏜️"), (40, "ค่อนข้างแห้ง 🙂"), (61, "กำลังสบาย 😊"), (71, "เริ่มชื้น 😅"), (86, "ชื้นอบอ้าว 🥵")):
        if h < limit:
            return text
    return "ชื้นมาก 💦"


def r0(v):
    return "–" if v is None else str(round(v))


def build(w, a, st=None):
    now = datetime.now(BKK)
    lines = [f"🌤 <b>{html.escape(PLACE)}</b> · {now:%H:%M} น."]
    alerts = []

    if w:
        c = w["current"]
        h = w["hourly"]
        idx = h["time"].index(c["time"][:13] + ":00") if c["time"][:13] + ":00" in h["time"] else 0
        lines.append(f"🌡 <b>{r0(c['temperature_2m'])}°C</b> (รู้สึก {r0(c['apparent_temperature'])}°C) · {WX.get(c['weather_code'], '–')}")
        lines.append(f"💧 ความชื้น {r0(c['relative_humidity_2m'])}% ({hum_label(c['relative_humidity_2m'])}) · 🌬 ลม {r0(c['wind_speed_10m'])} กม./ชม.")
    else:
        idx = 0
        lines.append("⚠️ ดึงข้อมูลสภาพอากาศไม่สำเร็จ")

    lines.append("")
    model_pm = a["current"].get("pm2_5") if a and a.get("current") else None
    v = st["pm25"] if st and st.get("pm25") is not None else model_pm
    if v is not None:
        _, ico, label, tip = pm_level(v)
        if st and st.get("pm25") is not None:
            extra = f" · AQI {r0(st['aqi'])}" if st.get("aqi") is not None else ""
            lines.append(f"{ico} <b>PM2.5 {v:.1f} µg/m³</b> เฉลี่ย 24 ชม. · {label}{extra}")
            lines.append(f"📍 สถานี {html.escape(st['area'])} ({html.escape(st['date'])} {html.escape(st['time'])} น.)")
            if st.get("age") is not None and st["age"] > 6:
                lines.append(f"⚠️ ข้อมูลสถานีล่าช้าประมาณ {st['age']:.0f} ชั่วโมง")
        else:
            lines.append(f"{ico} <b>PM2.5 {v:.1f} µg/m³</b> · {label} <i>(แบบจำลอง)</i>")
        if v > TH_PM:
            alerts.append(f"PM2.5 สูง ({label}): {tip}")
    else:
        lines.append("😷 PM2.5: ไม่มีข้อมูล")

    if w:
        pr = h["precipitation_probability"][idx:idx + 6]
        pmax = max(pr) if pr else 0
        k = next((i for i, x in enumerate(pr) if x >= 50), None)
        start = f" (เริ่มราว {h['time'][idx + k][11:16]} น.)" if k is not None else ""
        lines.append(f"☔ ฝนใน 6 ชม.: <b>{r0(pmax)}%</b>{start}")
        if pmax >= TH_RAIN:
            k2 = next(i for i, x in enumerate(pr) if x >= TH_RAIN)
            alerts.append(f"มีโอกาสฝนตก {r0(pmax)}% เริ่มราว {h['time'][idx + k2][11:16]} น. พกร่มหรือเสื้อกันฝน")

        uvmax = w["daily"]["uv_index_max"][0]
        lines.append(f"☀️ UV สูงสุดวันนี้ {r0(uvmax)} ({uv_label(uvmax)})")
        uv12 = max(h["uv_index"][idx:idx + 12] or [0])
        if uv12 >= TH_UV:
            alerts.append(f"UV {r0(uv12)} ({uv_label(uv12)}) ทาครีมกันแดด สวมหมวกเมื่ออยู่กลางแจ้ง")

        ap12 = max(h["apparent_temperature"][idx:idx + 12] or [0])
        if ap12 >= TH_HEAT:
            alerts.append(f"อากาศร้อน รู้สึกเหมือน {r0(ap12)}°C ภายใน 12 ชม. ดื่มน้ำบ่อยๆ เลี่ยงแดดจัด 11:00–15:00")

        d = w["daily"]
        lines.append(f"📅 วันนี้ {r0(d['temperature_2m_min'][0])}°–{r0(d['temperature_2m_max'][0])}° · ฝนสูงสุด {r0(d['precipitation_probability_max'][0])}% ({d['precipitation_sum'][0]:.1f} มม.)")
        lines.append(f"📅 พรุ่งนี้ {r0(d['temperature_2m_min'][1])}°–{r0(d['temperature_2m_max'][1])}° · ฝนสูงสุด {r0(d['precipitation_probability_max'][1])}%")

        nxt = []
        for off in (3, 6, 9, 12):
            j = idx + off
            if j < len(h["time"]):
                nxt.append(f"{h['time'][j][11:16]} {r0(h['temperature_2m'][j])}° ฝน {r0(h['precipitation_probability'][j])}%")
        if nxt:
            lines += ["", "⏭ <b>ช่วงถัดไป</b>"] + [f"  {x}" for x in nxt]

    if alerts:
        lines += ["", "⚠️ <b>แจ้งเตือน</b>"] + [f"• {html.escape(x)}" for x in alerts]
    else:
        lines += ["", "✅ ไม่มีสิ่งผิดปกติตามเกณฑ์ที่ตั้งไว้"]
    lines += ["", f'🌧 <a href="{html.escape(RADAR_URL)}">ดูเรดาร์ฝน (กรมอุตุนิยมวิทยา)</a>']
    if st and st.get("pm25") is not None:
        lines += ["", "<i>PM2.5 จากสถานีตรวจวัด Air4Thai (กรมควบคุมมลพิษ) สภาพอากาศจาก Open-Meteo</i>"]
    else:
        lines += ["", "<i>PM2.5 เป็นค่าจากแบบจำลอง ไม่ใช่เครื่องวัดจริง เทียบกับ Air4Thai ก่อนตัดสินใจเรื่องสุขภาพ</i>"]
    return "\n".join(lines)


def send(text):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat:
        sys.exit("ต้องตั้งค่า TELEGRAM_BOT_TOKEN และ TELEGRAM_CHAT_ID")
    data = urlencode({"chat_id": chat, "text": text, "parse_mode": "HTML",
                      "disable_web_page_preview": "true"}).encode()
    for i in range(3):
        try:
            with urlopen(Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data), timeout=20) as r:
                if json.load(r).get("ok"):
                    return
        except HTTPError as e:
            print(f"telegram HTTP {e.code}: {e.read().decode(errors='replace')[:200]}", file=sys.stderr)
            if e.code in (400, 401, 403, 404):
                break  # token/chat ผิด ไม่ต้องลองซ้ำ
        except (URLError, TimeoutError) as e:
            print(f"telegram error: {e}", file=sys.stderr)
        time.sleep(2 * (i + 1))
    sys.exit("ส่งข้อความ Telegram ไม่สำเร็จ")


def wait_for_slot(max_wait=20 * 60):
    """รอถึงเวลาไทยที่กำหนด (เฉพาะเมื่อรันจาก schedule) เพื่อให้ข้อความตรงเวลา"""
    if os.getenv("GITHUB_EVENT_NAME") != "schedule":
        return
    slots = []
    for t in env("SEND_TIMES", "05:00,11:00,15:00,18:00,21:00").split(","):
        try:
            hh, mm = t.strip().split(":")
            slots.append((int(hh), int(mm)))
        except ValueError:
            continue
    now = datetime.now(BKK)
    waits = []
    for hh, mm in slots:
        target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if target < now - timedelta(minutes=1):
            target += timedelta(days=1)
        waits.append((target - now).total_seconds())
    if not waits:
        return
    wait = min(waits)
    if 0 < wait <= max_wait:
        print(f"รอ {wait:.0f} วินาทีจนถึงเวลาส่ง (เวลาไทย)", flush=True)
        time.sleep(wait)


def main():
    wait_for_slot()
    w, a = fetch()
    if not w and not a:
        sys.exit("ดึงข้อมูลจาก Open-Meteo ไม่สำเร็จ")
    st = pick_station(fetch_air4thai())
    text = build(w, a, st)
    if os.getenv("DRY_RUN"):
        print(text)
        return
    send(text)
    print("sent")


if __name__ == "__main__":
    main()
