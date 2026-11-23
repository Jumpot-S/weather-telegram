# weather-telegram

เฝ้าฟ้า: ดูสภาพอากาศ PM2.5 ฝน UV ของจังหวัดที่คุณอยู่ ทั้งแบบ **เว็บแอป** และ **แจ้งเตือนเข้า Telegram** อัตโนมัติ
ค่าเริ่มต้น: **นครพนม (อ.เมือง)** · ข้อมูลจาก [Open-Meteo](https://open-meteo.com) ไม่ต้องมี API key

```
.
├── docs/
│   └── index.html            เว็บแอป (ไฟล์เดียว เลือกได้ 77 จังหวัด)
├── telegram/
│   └── weather_alert.py      สคริปต์ส่งสรุปเข้า Telegram
├── .github/workflows/
│   └── weather.yml           ตั้งเวลาส่ง 05:00 11:00 15:00 18:00 21:00 (เวลาไทย)
└── README.md
```

## 1) เว็บแอป (`docs/`)

เปิดไฟล์ `docs/index.html` ในเบราว์เซอร์ได้เลย หรือเผยแพร่ฟรีด้วย GitHub Pages:
Settings → Pages → Source: *Deploy from a branch* → Branch: `main` โฟลเดอร์ `/docs` → Save
แล้วเข้าที่ `https://jumpot-s.github.io/weather-telegram/`

แสดงอุณหภูมิ, PM2.5/PM10, โอกาสฝน, UV, กราฟ 24 ชม., พยากรณ์ 7 วัน และตั้งเกณฑ์เตือนเองได้
(แจ้งเตือนบนเบราว์เซอร์ทำงานเฉพาะเมื่อเปิดหน้านี้ค้างไว้)

## 2) แจ้งเตือน Telegram (`telegram/` + GitHub Actions)

ข้อความมีอุณหภูมิ, PM2.5, โอกาสฝน 6 ชม., UV, พยากรณ์วันนี้/พรุ่งนี้ และหัวข้อแจ้งเตือนเมื่อค่าเกินเกณฑ์

### ตั้งค่า (ทำครั้งเดียว)

1. **สร้างบอท**: คุยกับ [@BotFather](https://t.me/BotFather) พิมพ์ `/newbot` แล้วเก็บ **token**
2. **หา chat id**: ส่งข้อความหาบอทหนึ่งครั้ง แล้วเปิด
   `https://api.telegram.org/bot<TOKEN>/getUpdates` ดูค่า `"chat":{"id": ...}`
   (ส่งเข้ากลุ่ม: เชิญบอทเข้ากลุ่ม ส่งข้อความในกลุ่ม แล้วดู id ที่ขึ้นต้นด้วย `-`)
3. **ใส่ Secrets** ที่ Settings → Secrets and variables → Actions → *Secrets*
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
4. **ทดสอบ**: แท็บ Actions → `weather-alert` → *Run workflow*

### เปลี่ยนพื้นที่หรือเกณฑ์ (ไม่บังคับ)

ใส่ที่ Settings → Secrets and variables → Actions → *Variables*

| ตัวแปร | ความหมาย | ค่าเริ่มต้น |
|---|---|---|
| `PLACE_NAME` | ชื่อที่แสดงในข้อความ | นครพนม (อ.เมือง) |
| `LAT`, `LON` | พิกัด | 17.4105, 104.7783 |
| `PM_THRESHOLD` | เตือนเมื่อ PM2.5 เกิน (µg/m³) | 37.5 |
| `HEAT_THRESHOLD` | เตือนเมื่ออุณหภูมิที่รู้สึกเกิน (°C) | 38 |
| `RAIN_THRESHOLD` | เตือนเมื่อโอกาสฝนใน 6 ชม. ตั้งแต่ (%) | 60 |
| `UV_THRESHOLD` | เตือนเมื่อ UV ตั้งแต่ | 8 |

### เปลี่ยนเวลาส่ง

แก้ `cron` ใน `.github/workflows/weather.yml` (เวลา UTC = เวลาไทย ลบ 7 ชั่วโมง)

### ทดสอบในเครื่อง

```bash
DRY_RUN=1 python3 telegram/weather_alert.py
TELEGRAM_BOT_TOKEN=xxx TELEGRAM_CHAT_ID=yyy python3 telegram/weather_alert.py
```

## ข้อควรรู้

- GitHub Actions อาจส่งช้ากว่ากำหนดประมาณ 5–30 นาที
- repo ที่ไม่มีการเคลื่อนไหว 60 วัน GitHub จะหยุด schedule อัตโนมัติ ต้องกดเปิดใหม่ที่แท็บ Actions
- ค่า PM2.5 เป็นค่าจากแบบจำลอง ไม่ใช่เครื่องวัดจริง ควรเทียบกับ Air4Thai
