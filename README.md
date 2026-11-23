# weather-telegram

ส่งสรุปสภาพอากาศเข้า Telegram อัตโนมัติผ่าน GitHub Actions ตอน **05:00, 11:00, 15:00, 18:00, 21:00** (เวลาไทย)
ค่าเริ่มต้น: **นครพนม (อ.เมือง)**

ข้อมูลในข้อความ: อุณหภูมิ, PM2.5/PM10, โอกาสฝน 6 ชม., ดัชนี UV, พยากรณ์วันนี้และพรุ่งนี้, ช่วงถัดไปทุก 3 ชม. และหัวข้อแจ้งเตือนเมื่อค่าเกินเกณฑ์
ใช้ [Open-Meteo](https://open-meteo.com) ไม่ต้องมี API key

## ตั้งค่า (ทำครั้งเดียว)

1. **สร้างบอท**: ใน Telegram คุยกับ [@BotFather](https://t.me/BotFather) พิมพ์ `/newbot` แล้วเก็บ **token**
2. **หา chat id**: กดส่งข้อความอะไรก็ได้หาบอทของคุณก่อน แล้วเปิด
   `https://api.telegram.org/bot<TOKEN>/getUpdates` ดูค่า `"chat":{"id": ...}`
   (ถ้าจะส่งเข้ากลุ่ม ให้เชิญบอทเข้ากลุ่ม ส่งข้อความในกลุ่ม แล้วดู id ที่ขึ้นต้นด้วย `-`)
3. **ใส่ Secrets** ที่ Settings → Secrets and variables → Actions → *Secrets*
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
4. **ทดสอบ**: แท็บ Actions → `weather-alert` → *Run workflow* ควรได้ข้อความใน Telegram ภายในไม่กี่วินาที

## เปลี่ยนพื้นที่หรือเกณฑ์ (ไม่บังคับ)

ใส่ที่ Settings → Secrets and variables → Actions → *Variables*

| ตัวแปร | ความหมาย | ค่าเริ่มต้น |
|---|---|---|
| `PLACE_NAME` | ชื่อที่แสดงในข้อความ | นครพนม (อ.เมือง) |
| `LAT`, `LON` | พิกัด | 17.4105, 104.7783 |
| `PM_THRESHOLD` | เตือนเมื่อ PM2.5 เกิน (µg/m³) | 37.5 |
| `HEAT_THRESHOLD` | เตือนเมื่ออุณหภูมิที่รู้สึกเกิน (°C) | 38 |
| `RAIN_THRESHOLD` | เตือนเมื่อโอกาสฝนใน 6 ชม. ตั้งแต่ (%) | 60 |
| `UV_THRESHOLD` | เตือนเมื่อ UV ตั้งแต่ | 8 |

## เปลี่ยนเวลาส่ง

แก้ `cron` ใน `.github/workflows/weather.yml` (เป็นเวลา UTC ให้ลบ 7 ชั่วโมงจากเวลาไทย)

## ทดสอบในเครื่อง

```bash
DRY_RUN=1 python3 weather_alert.py                       # พิมพ์ข้อความ ไม่ส่งจริง
TELEGRAM_BOT_TOKEN=xxx TELEGRAM_CHAT_ID=yyy python3 weather_alert.py
```

## ข้อควรรู้

- GitHub Actions อาจส่งช้ากว่ากำหนดประมาณ 5–30 นาทีในช่วงที่ระบบคิวยาว
- repo ที่ไม่มีการเคลื่อนไหว 60 วัน GitHub จะหยุด schedule อัตโนมัติ ต้องกดเปิดใหม่ที่แท็บ Actions (หรือ commit อะไรก็ได้)
- ค่า PM2.5 เป็นค่าจากแบบจำลอง ไม่ใช่เครื่องวัดจริง
