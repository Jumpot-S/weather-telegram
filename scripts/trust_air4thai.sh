#!/usr/bin/env bash
# เซิร์ฟเวอร์ Air4Thai ส่งใบรับรอง SSL มาไม่ครบสาย (ขาดใบกลาง) เบราว์เซอร์ดึงใบกลางเองได้ แต่ Python/curl ทำไม่ได้
# สคริปต์นี้อ่านที่อยู่ใบกลางจาก AIA ในใบรับรองของเซิร์ฟเวอร์ ดาวน์โหลดมา แล้วรวมกับ CA ของระบบ
# จากนั้นตั้ง SSL_CERT_FILE ให้ขั้นตอนถัดไปใน workflow ใช้ตรวจใบรับรองได้ตามปกติ
# ถ้าทำไม่สำเร็จ จะไม่ล้ม workflow (สคริปต์ Python มีทางสำรองของตัวเอง)
set -u
host=air4thai.pcd.go.th
dir="${RUNNER_TEMP:-/tmp}"

openssl s_client -connect "$host:443" -servername "$host" </dev/null 2>/dev/null | openssl x509 -outform PEM > "$dir/a4t-leaf.pem" 2>/dev/null
if [ ! -s "$dir/a4t-leaf.pem" ]; then echo "อ่านใบรับรองของ $host ไม่ได้ ข้ามขั้นตอนนี้"; exit 0; fi

url=$(openssl x509 -in "$dir/a4t-leaf.pem" -noout -text | grep -m1 'CA Issuers - URI' | sed 's/.*URI://' | tr -d '\r')
if [ -z "$url" ]; then echo "ไม่พบที่อยู่ใบกลางในใบรับรอง ข้ามขั้นตอนนี้"; exit 0; fi

echo "ดาวน์โหลดใบกลางจาก $url"
if ! curl -fsSL --max-time 20 "$url" -o "$dir/a4t-inter.bin"; then echo "ดาวน์โหลดใบกลางไม่สำเร็จ ข้ามขั้นตอนนี้"; exit 0; fi
if ! openssl x509 -inform DER -in "$dir/a4t-inter.bin" -out "$dir/a4t-inter.pem" 2>/dev/null; then cp "$dir/a4t-inter.bin" "$dir/a4t-inter.pem"; fi

cat /etc/ssl/certs/ca-certificates.crt "$dir/a4t-inter.pem" > "$dir/a4t-ca.pem"
if [ -n "${GITHUB_ENV:-}" ]; then echo "SSL_CERT_FILE=$dir/a4t-ca.pem" >> "$GITHUB_ENV"; fi
echo "เพิ่มใบกลางแล้ว: $dir/a4t-ca.pem"
