# 🤖 ربات چت ناشناس پیشرفته (Advanced Anonymous Chat Bot)

[![Python Version](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Framework](https://img.shields.io/badge/Framework-aiogram%203-green.svg)](https://github.com/aiogram/aiogram)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

این یک ربات تلگرامی پیشرفته برای ایجاد چت ناشناس است که با استفاده از کتابخانه `aiogram` در پایتون توسعه داده شده است. ربات دارای پنل مدیریت قدرتمند، سیستم عضویت اجباری هوشمند و پایگاه داده امن مبتنی بر هش می‌باشد.

---

## 🚀 ویژگی‌های کلیدی

### 👤 برای کاربران

- **لینک ناشناس اختصاصی:** هر کاربر یک لینک منحصر به فرد و هش شده دریافت می‌کند تا دیگران بتوانند به صورت ناشناس به او پیام دهند.
- **ارسال انواع پیام:** قابلیت ارسال متن، عکس، ویدیو و پیام صوتی به صورت ناشناس.
- **قابلیت پاسخ (Reply):** کاربران می‌توانند به پیام‌های ناشناسی که دریافت می‌کنند، پاسخ دهند.
- **مشاهده پیام‌ها:** مشاهده لیستی از آخرین پیام‌های دریافت شده.

### 👑 برای ادمین

- **پنل مدیریت پیشرفته:** دسترسی به پنل مدیریت کامل با شناسه عددی ادمین.
- **پیام همگانی (Broadcast):** ارسال پیام به تمام کاربران ربات.
- **آمار دقیق فعالیت:** مشاهده آمار کاربران جدید (روزانه، هفتگی، ماهانه، سالانه) و آمار کلی.
- **مدیریت عضویت اجباری (قفل کانال):**
  - افزودن/حذف نامحدود کانال، گروه یا لینک‌های خارجی (مانند سایت).
  - قابلیت تعیین متن دلخواه برای دکمه هر هدف.
  - **بررسی هوشمند عضویت:** اگر ربات در کانال/گروه ادمین باشد، عضویت واقعی کاربر را چک می‌کند؛ در غیر این صورت یا برای لینک‌ها، به کلیک کاربر اعتماد می‌کند.

### 🔐 امنیت

- **پایگاه داده امن:** تمام شناسه‌های کاربران در پایگاه داده به صورت **هش شده** با `Salt` ذخیره می‌شوند تا حریم خصوصی کاربران حفظ شود.

---

## 🛠️ تکنولوژی‌های استفاده شده

- **زبان:** Python 3.9+
- **فریمورک تلگرام:** `aiogram 3.x`
- **پایگاه داده:** `SQLite` (با استفاده از `aiosqlite` برای عملیات ناهمگام)
- **استقرار:** اسکریپت نصب خودکار برای سرورهای لینوکس (مبتنی بر `systemd`).

---

## ⚙️ راهنمای نصب و راه‌اندازی روی سرور لینوکس

این ربات برای استقرار آسان روی سرورهای لینوکسی (مانند Ubuntu) طراحی شده است.

1.  **کلون کردن پروژه:**
    ابتدا پروژه را از گیت‌هاب روی سرور خود کلون کنید.
    ```bash
    git clone <Your-Repository-URL>
    cd <repository-name>
    ```

2.  **اجرای اسکریپت نصب:**
    به اسکریپت `setup.sh` دسترسی اجرایی داده و آن را با `sudo` اجرا کنید.
    ```bash
    chmod +x setup.sh
    sudo ./setup.sh
    ```

3.  **وارد کردن اطلاعات:**
    اسکریپت از شما موارد زیر را به صورت تعاملی می‌پرسد:
    - **توکن ربات تلگرام:** توکن ربات خود را که از `@BotFather` گرفته‌اید، وارد کنید.
    - **شناسه عددی ادمین:** شناسه عددی اکانت تلگرام خود را وارد کنید.

پس از وارد کردن اطلاعات، اسکریپت به صورت خودکار:
- نیازمندی‌های سیستم را نصب می‌کند.
- محیط مجازی پایتون را می‌سازد و کتابخانه‌ها را نصب می‌کند.
- فایل `config.py` را با اطلاعات شما و یک `HASH_SALT` امن ایجاد می‌کند.
- یک سرویس `systemd` به نام `anonymous_bot.service` برای اجرای دائمی ربات ایجاد و فعال می‌کند.

4.  **بررسی وضعیت ربات:**
    برای اطمینان از اینکه ربات به درستی در حال اجراست، از دستور زیر استفاده کنید:
    ```bash
    sudo systemctl status anonymous_bot.service
    ```
    اگر همه چیز درست باشد، باید خروجی `active (running)` را به رنگ سبز مشاهده کنید.

---

## 🇺🇸 English Version

### 🤖 Advanced Anonymous Chat Bot

This is an advanced anonymous chat bot for Telegram, developed using the `aiogram` library in Python. The bot features a powerful admin panel, a smart force-subscription system, and a secure hash-based database.

### 🚀 Key Features

#### 👤 For Users

- **Unique Anonymous Link:** Each user gets a unique, hashed link to share, allowing others to send them anonymous messages.
- **Multimedia Support:** Ability to send text, photos, videos, and voice messages anonymously.
- **Reply Functionality:** Users can reply to the anonymous messages they receive.
- **View Messages:** Users can view a list of their latest received messages.

#### 👑 For Admins

- **Advanced Admin Panel:** Full access to a management panel via the admin's numeric ID.
- **Broadcast:** Send a message to all bot users.
- **Detailed Activity Stats:** View statistics for new users (daily, weekly, monthly, yearly) and overall totals.
- **Force Subscription Management:**
  - Add/remove an unlimited number of channels, groups, or external links (e.g., websites).
  - Ability to set custom button text for each target.
  - **Smart Membership Check:** If the bot is an admin in a channel/group, it verifies actual membership. Otherwise, or for links, it operates on a trust-based "I have subscribed" click.

### 🔐 Security

- **Secure Database:** All user IDs are stored in the database as **salted hashes** to protect user privacy.

---

### 🛠️ Tech Stack

- **Language:** Python 3.9+
- **Telegram Framework:** `aiogram 3.x`
- **Database:** `SQLite` (using `aiosqlite` for asynchronous operations)
- **Deployment:** Automated setup script for Linux servers (based on `systemd`).

---

### ⚙️ Installation and Setup on a Linux Server

This bot is designed for easy deployment on Linux servers (e.g., Ubuntu).

1.  **Clone the Project:**
    First, clone the project from GitHub onto your server.
    ```bash
    git clone <Your-Repository-URL>
    cd <repository-name>
    ```

2.  **Run the Setup Script:**
    Give the `setup.sh` script executable permissions and run it with `sudo`.
    ```bash
    chmod +x setup.sh
    sudo ./setup.sh
    ```

3.  **Enter Your Credentials:**
    The script will interactively ask for the following:
    - **Telegram Bot Token:** Enter your bot token from `@BotFather`.
    - **Admin's Numeric ID:** Enter your own numeric Telegram user ID.

    After you provide the information, the script will automatically:
    - Install system dependencies.
    - Create a Python virtual environment and install the required libraries.
    - Create a `config.py` file with your credentials and a secure `HASH_SALT`.
    - Create and enable a `systemd` service named `anonymous_bot.service` to run the bot persistently.

4.  **Check the Bot's Status:**
    To ensure the bot is running correctly, use the following command:
    ```bash
    sudo systemctl status anonymous_bot.service
    ```
    If everything is correct, you should see an `active (running)` status in green.