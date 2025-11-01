#!/bin/bash

echo "--- شروع نصب و راه‌اندازی ربات چت ناشناس ---"

# بررسی دسترسی روت
if [ "$EUID" -ne 0 ]; then
  echo "خطا: لطفاً این اسکریپت را با دسترسی sudo یا به عنوان کاربر root اجرا کنید."
  exit 1
fi

echo "مرحله ۱: به‌روزرسانی سیستم و نصب نیازمندی‌ها..."
apt update > /dev/null 2>&1
apt install -y python3-pip python3-venv git > /dev/null 2>&1
echo "✅ نیازمندی‌های سیستم نصب شد."

echo "مرحله ۲: ایجاد محیط مجازی پایتون..."
python3 -m venv venv
source venv/bin/activate
echo "✅ محیط مجازی ایجاد و فعال شد."

echo "مرحله ۳: نصب کتابخانه‌های پایتون..."
pip install -r requirements.txt > /dev/null 2>&1
echo "✅ کتابخانه‌های پایتون نصب شدند."

echo "مرحله ۴: ایجاد فایل پیکربندی (config.py)..."

read -p "لطفاً توکن ربات تلگرام خود را وارد کنید: " BOT_TOKEN
read -p "لطفاً شناسه عددی (User ID) ادمین را وارد کنید: " ADMIN_ID

if [ -z "$BOT_TOKEN" ] || ! [[ "$ADMIN_ID" =~ ^[0-9]+$ ]]; then
    echo "خطا: توکن یا شناسه ادمین نامعتبر است. نصب متوقف شد."
    exit 1
fi

HASH_SALT=$(python3 -c 'import secrets; print(secrets.token_hex(32))')

cat << EOF > config.py
# --- تنظیمات اصلی ربات ---

TELEGRAM_BOT_TOKEN = "$BOT_TOKEN"
ADMIN_USER_ID = $ADMIN_ID
HASH_SALT = "$HASH_SALT"
EOF

echo "✅ فایل config.py با موفقیت ایجاد شد."

echo "مرحله ۵: ایجاد سرویس systemd برای اجرای دائمی ربات..."

PROJECT_PATH=$(pwd)
SERVICE_FILE="/etc/systemd/system/anonymous_bot.service"

cat << EOF > $SERVICE_FILE
[Unit]
Description=Anonymous Telegram Bot Service
After=network.target

[Service]
User=$(whoami)
Group=$(id -gn $(whoami))
WorkingDirectory=$PROJECT_PATH
ExecStart=$PROJECT_PATH/venv/bin/python $PROJECT_PATH/anonymous_bot_aiogram.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

echo "✅ فایل سرویس systemd ایجاد شد."

echo "مرحله ۶: فعال‌سازی و اجرای سرویس..."
systemctl daemon-reload
systemctl enable anonymous_bot.service
systemctl start anonymous_bot.service

echo "🎉 نصب با موفقیت به پایان رسید!"
echo "ربات شما اکنون به صورت دائمی در حال اجرا است."
echo "برای بررسی وضعیت ربات، از دستور زیر استفاده کنید:"
echo "sudo systemctl status anonymous_bot.service"