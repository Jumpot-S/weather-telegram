#!/usr/bin/env python3
"""ส่งสรุปสภาพอากาศ PM2.5 ฝน UV เข้า Telegram (ใช้ Open-Meteo ไม่ต้องมี API key)

ตัวแปรสภาพแวดล้อม:
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID  (จำเป็น)
  PLACE_NAME  ชื่อสถานที่ที่แสดง   (ค่าเริ่มต้น: นครพนม (อ.เมือง))
  LAT, LON    พิกัด               (ค่าเริ่มต้น: 17.4105, 104.7783)
  PM_THRESHOLD, HEAT_THRESHOLD, RAIN_THRESHOLD, UV_THRESHOLD  เกณฑ์แจ้งเตือน
  SEND_TIMES  เวลาส่งตามเวลาไทย คั่นด้วยจุลภาค (ค่าเริ่มต้น: 05:00,11:00,15:00,18:00,21:00)
  DRY_RUN=1   พิมพ์ข้อความแทนการส่งจริง

เมื่อรันจาก schedule ของ GitHub Actions สคริปต์จะรอจนถึงเวลาไทยที่ใกล้ที่สุดใน SEND_TIMES
(workflow เริ่มก่อนเวลา 15 นาทีเพื่อชดเชยความล่าช้าของคิว) ถ้ารันช้ากว่าเวลา จะส่งทันที
"""
import html
import json
import os
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
        "https://api.open-meteo.com/v1/forecast?" + q
        + "&current=temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,weather_code,wind_speed_10m"
        + "&hourly=temperature_2m,apparent_temperature,precipitation_probability,uv_index,weather_code"
        + "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum,uv_index_max"
        + "&forecast_days=2")
    a = get_json("https://air-quality-api.open-meteo.com/v1/air-quality?" + q
                 + "&current=pm2_5,pm10&hourly=pm2_5&forecast_days=2")
    return w, a


def pm_level(v):
    return next(l for l in PM_LEVELS if v <= l[0])


def uv_label(v):
    return next(l[1] for l in UV_LEVELS if v < l[0])


def r0(v):
    return "–" if v is None else str(round(v))


def build(w, a):
    now = datetime.now(BKK)
    lines = [f"🌤 <b>{html.escape(PLACE)}</b> · {now:%H:%M} น."]
    alerts = []

    if w:
        c = w["current"]
        h = w["hourly"]
        idx = h["time"].index(c["time"][:13] + ":00") if c["time"][:13] + ":00" in h["time"] else 0
        lines.append(f"🌡 <b>{r0(c['temperature_2m'])}°C</b> (รู้สึก {r0(c['apparent_temperature'])}°C) · {WX.get(c['weather_code'], '–')}")
        lines.append(f"💧 ความชื้น {r0(c['relative_humidity_2m'])}% · 🌬 ลม {r0(c['wind_speed_10m'])} กม./ชม.")
    else:
        idx = 0
        lines.append("⚠️ ดึงข้อมูลสภาพอากาศไม่สำเร็จ")

    lines.append("")
    if a and a.get("current") and a["current"].get("pm2_5") is not None:
        v = a["current"]["pm2_5"]
        _, ico, label, tip = pm_level(v)
        lines.append(f"{ico} <b>PM2.5 {v:.1f} µg/m³</b> · {label}")
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
    lines += ["", "<i>PM2.5 เป็นค่าจากแบบจำลอง เทียบกับ Air4Thai ก่อนตัดสินใจเรื่องสุขภาพ</i>"]
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
    text = build(w, a)
    if os.getenv("DRY_RUN"):
        print(text)
        return
    send(text)
    print("sent")


if __name__ == "__main__":
    main()
