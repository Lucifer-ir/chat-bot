import asyncio
import logging
import sqlite3
import datetime
import hashlib
import os
import secrets

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
    ReplyKeyboardRemove,
)
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramAPIError
from aiogram.enums import ChatMemberStatus


# --- State ها ---
class Form(StatesGroup):
    getting_recipient_id = State()
    sending_message = State()
    getting_reply = State()
    sending_message_to_admin = State()
    replying_to_user = State()
    getting_broadcast_message = State()
    force_sub_add_channel = State()
    force_sub_add_link = State()
    force_sub_add_button_text = State()
    force_sub_remove = State()


# --- توابع پایگاه داده و هش ---
def setup_database():
    conn = sqlite3.connect("anonymous_chat.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            hashed_id TEXT PRIMARY KEY,
            user_id INTEGER UNIQUE NOT NULL,
            username TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_hashed_id TEXT,
            recipient_hashed_id TEXT,
            telegram_message_id INTEGER,
            FOREIGN KEY (sender_hashed_id) REFERENCES users(hashed_id),
            FOREIGN KEY (recipient_hashed_id) REFERENCES users(hashed_id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS force_sub_targets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target TEXT UNIQUE NOT NULL,
            type TEXT NOT NULL, -- 'channel' or 'link'
            button_text TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def get_hashed_id(user_id: int, salt: str) -> str:
    return hashlib.sha256(f"{user_id}{salt}".encode()).hexdigest()[:12]

def db_get_user_id_by_hash(hashed_id: str) -> int | None:
    conn = sqlite3.connect("anonymous_chat.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE hashed_id = ?", (hashed_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def db_get_user_by_username(username: str) -> int | None:
    conn = sqlite3.connect("anonymous_chat.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE LOWER(username) = LOWER(?)", (username,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def db_get_force_sub_targets() -> list:
    conn = sqlite3.connect("anonymous_chat.db")
    cursor = conn.cursor()
    cursor.execute("SELECT target, type, button_text FROM force_sub_targets")
    targets = cursor.fetchall()
    conn.close()
    return targets

# --- کیبوردها ---
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🔗 لینک ناشناس من")],
        [KeyboardButton(text="📞 ارتباط با ادمین"), KeyboardButton(text="📨 ارسال به کاربر")],
    ],
    resize_keyboard=True,
)

admin_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📢 پیام همگانی")],
        [KeyboardButton(text="👥 لیست کاربران"), KeyboardButton(text="📊 آمار فعالیت")],
        [KeyboardButton(text="🔒 مدیریت عضویت اجباری")],
    ],
    resize_keyboard=True,
)

force_sub_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ افزودن کانال/گروه"), KeyboardButton(text="🔗 افزودن لینک")],
        [KeyboardButton(text="➖ حذف هدف"), KeyboardButton(text="📋 لیست اهداف")],
        [KeyboardButton(text="⬅️ بازگشت به پنل")],
    ],
    resize_keyboard=True,
)

# --- Middleware برای عضویت اجباری ---
class SubscriptionMiddleware:
    async def __call__(self, handler, event, data):
        user = data.get('event_from_user')
        if not user or user.id == ADMIN_USER_ID:
            return await handler(event, data)

        targets = db_get_force_sub_targets()
        if not targets:
            return await handler(event, data)

        unsubscribed_targets = []
        for target, target_type, button_text in targets:
            if target_type == 'channel':
                try:
                    member = await bot.get_chat_member(chat_id=target, user_id=user.id)
                    if member.status not in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
                        unsubscribed_targets.append((target, target_type, button_text))
                except (TelegramBadRequest, TelegramAPIError):
                    logging.warning(f"Bot is not admin in {target}. Trusting user {user.id} click.")
                    unsubscribed_targets.append((target, target_type, button_text))
            else: # برای لینک‌ها
                unsubscribed_targets.append((target, target_type, button_text))

        # اگر کاربر در تمام کانال‌ها عضو بود و فقط لینک باقی مانده بود
        if not any(t[1] == 'channel' for t in unsubscribed_targets) and any(t[1] == 'link' for t in unsubscribed_targets):
            if isinstance(event, CallbackQuery) and event.data == "check_sub":
                await event.message.delete()
                await event.answer("ممنون از شما! اکنون می‌توانید از ربات استفاده کنید.", show_alert=True)
                await bot.send_message(user.id, "به ربات چت ناشناس خوش آمدید.", reply_markup=main_keyboard)
                return

        if unsubscribed_targets:
            join_buttons = [
                [InlineKeyboardButton(text=btn_text, url=f"https://t.me/{tgt.lstrip('@')}" if not tgt.startswith("http") else tgt)]
                for tgt, t_type, btn_text in targets
            ]
            join_buttons.append([InlineKeyboardButton(text="✅ عضو شدم", callback_data="check_sub")])
            keyboard = InlineKeyboardMarkup(inline_keyboard=join_buttons)

            text_to_send = "برای استفاده از ربات، لطفاً مراحل زیر را تکمیل کنید:"
            if isinstance(event, Message):
                await event.answer(text_to_send, reply_markup=keyboard)
            elif isinstance(event, CallbackQuery):
                await event.answer("شما هنوز تمام مراحل عضویت را تکمیل نکرده‌اید.", show_alert=True)
            return

        return await handler(event, data)

# --- Handlers ---

async def register_handlers(dp: Dispatcher):
    # Middleware
    dp.message.middleware(SubscriptionMiddleware())
    dp.callback_query.middleware(SubscriptionMiddleware())

    # User Handlers
    dp.message.register(command_start_handler, CommandStart())
    dp.message.register(get_my_link, F.text == "🔗 لینک ناشناس من")
    dp.message.register(contact_admin_start, F.text == "📞 ارتباط با ادمین")
    dp.message.register(forward_to_admin, Form.sending_message_to_admin)
    dp.message.register(send_to_user_start, F.text == "📨 ارسال به کاربر")
    dp.message.register(get_recipient_username, Form.getting_recipient_id)
    dp.message.register(forward_anonymous_message, Form.sending_message)
    dp.callback_query.register(handle_reply_button, F.data.startswith("reply_"))
    dp.message.register(send_reply_message, Form.getting_reply)
    dp.message.register(cancel_handler, F.text == "/cancel")
    dp.callback_query.register(check_sub_callback, F.data == "check_sub")

    # Admin Handlers
    dp.callback_query.register(handle_admin_reply_button, F.data.startswith("admin_reply_"))
    dp.message.register(send_admin_reply_to_user, Form.replying_to_user)
    dp.message.register(broadcast_start, F.from_user.id == ADMIN_USER_ID, F.text == "📢 پیام همگانی")
    dp.message.register(process_broadcast, F.from_user.id == ADMIN_USER_ID, Form.getting_broadcast_message)
    dp.message.register(get_user_list, F.from_user.id == ADMIN_USER_ID, F.text == "👥 لیست کاربران")
    dp.message.register(get_stats, F.from_user.id == ADMIN_USER_ID, F.text == "📊 آمار فعالیت")
    dp.message.register(force_sub_settings, F.from_user.id == ADMIN_USER_ID, F.text == "🔒 مدیریت عضویت اجباری")
    dp.message.register(list_force_sub_channels, F.from_user.id == ADMIN_USER_ID, F.text == "📋 لیست اهداف")
    dp.message.register(add_force_sub_channel_start, F.from_user.id == ADMIN_USER_ID, F.text == "➕ افزودن کانال/گروه")
    dp.message.register(add_force_sub_channel_get_target, Form.force_sub_add_channel)
    dp.message.register(add_force_sub_link_start, F.from_user.id == ADMIN_USER_ID, F.text == "🔗 افزودن لینک")
    dp.message.register(add_force_sub_link_get_target, Form.force_sub_add_link)
    dp.message.register(add_force_sub_get_button_text, Form.force_sub_add_button_text)
    dp.message.register(remove_force_sub_start, F.from_user.id == ADMIN_USER_ID, F.text == "➖ حذف هدف")
    dp.message.register(remove_force_sub_process, Form.force_sub_remove)
    dp.message.register(back_to_main_admin_panel, F.from_user.id == ADMIN_USER_ID, F.text == "⬅️ بازگشت به پنل")


async def command_start_handler(message: Message, state: FSMContext) -> None:
    user = message.from_user
    hashed_id = get_hashed_id(user.id, HASH_SALT)
    
    conn = sqlite3.connect("anonymous_chat.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, hashed_id) VALUES (?, ?, ?)", (user.id, user.username, hashed_id))
    conn.commit()
    conn.close()

    if user.id == ADMIN_USER_ID:
        await message.answer("سلام ادمین! به پنل مدیریت خوش آمدید.", reply_markup=admin_keyboard)
        return

    args = message.text.split()
    if len(args) > 1:
        recipient_hashed_id = args[1]
        recipient_id = db_get_user_id_by_hash(recipient_hashed_id)
        if not recipient_id:
            await message.answer("لینک نامعتبر است یا کاربر مورد نظر دیگر در ربات حضور ندارد.", reply_markup=main_keyboard)
            return

        if recipient_id == user.id:
            await message.answer("شما نمی‌توانید به خودتان پیام ناشناس ارسال کنید!", reply_markup=main_keyboard)
            return

        await state.update_data(recipient_id=recipient_id)
        await state.set_state(Form.sending_message)
        await message.answer(
            "شما در حال ارسال پیام ناشناس هستید.\n"
            "پیام خود را (متن، عکس، ویدیو، صدا) ارسال کنید.\n\n"
            "برای لغو، دستور /cancel را ارسال کنید.",
            reply_markup=ReplyKeyboardRemove(),
        )
    else:
        await message.answer(
            f"سلام {user.first_name}!\nبه ربات چت ناشناس خوش آمدید.",
            reply_markup=main_keyboard,
        )

async def get_my_link(message: Message):
    user_hashed_id = get_hashed_id(message.from_user.id, HASH_SALT)
    bot_info = await bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={user_hashed_id}"
    await message.answer(
        "لینک ناشناس شما آماده است:\n\n"
        f"<code>{link}</code>\n\n"
        "این لینک را با دیگران به اشتراک بگذارید.",
    )

async def contact_admin_start(message: Message, state: FSMContext):
    """شروع فرآیند ارسال پیام به ادمین"""
    await state.set_state(Form.sending_message_to_admin)
    await message.answer("پیام خود را برای ارسال به ادمین وارد کنید. می‌توانید از متن، عکس، ویدیو و... استفاده کنید.", reply_markup=ReplyKeyboardRemove())

async def forward_to_admin(message: Message, state: FSMContext):
    """پیام کاربر را برای ادمین ارسال می‌کند"""
    user = message.from_user
    user_info = f"@{user.username}" if user.username else f"کاربر {user.first_name}"

    try:
        # ایجاد دکمه پاسخ برای ادمین
        reply_markup = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="✍️ پاسخ به کاربر", callback_data=f"admin_reply_{user.id}")]]
        )

        await bot.send_message(ADMIN_USER_ID, f"پیام جدید از <b>{user_info}</b> (ID: <code>{user.id}</code>):")
        await bot.copy_message(
            chat_id=ADMIN_USER_ID,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            reply_markup=reply_markup
        )
        await message.answer("پیام شما با موفقیت برای ادمین ارسال شد.", reply_markup=main_keyboard)
    except Exception as e:
        logging.error(f"Could not forward message to admin: {e}")
        await message.answer("خطایی در ارسال پیام به ادمین رخ داد. لطفاً بعداً تلاش کنید.", reply_markup=main_keyboard)
    finally:
        await state.clear()

async def send_to_user_start(message: Message, state: FSMContext):
    await state.set_state(Form.getting_recipient_id)
    await message.answer("نام کاربری تلگرام کاربر مقصد را با @ وارد کنید (مثال: @Username):")

async def get_recipient_username(message: Message, state: FSMContext):
    username = message.text.lstrip('@')
    recipient_id = db_get_user_by_username(username)

    if not recipient_id:
        await message.answer("کاربر یافت نشد. مطمئن شوید که کاربر مورد نظر ربات را استارت کرده است و نام کاربری را درست وارد کرده‌اید.", reply_markup=main_keyboard)
        await state.clear()
        return

    if recipient_id == message.from_user.id:
        await message.answer("شما نمی‌توانید به خودتان پیام ارسال کنید!", reply_markup=main_keyboard)
        await state.clear()
        return

    await state.update_data(recipient_id=recipient_id)
    await state.set_state(Form.sending_message)
    await message.answer(
        "کاربر یافت شد. اکنون پیام خود را برای ارسال وارد کنید.\n\n"
        "برای لغو، دستور /cancel را ارسال کنید.",
        reply_markup=ReplyKeyboardRemove()
    )

async def forward_anonymous_message(message: Message, state: FSMContext):
    data = await state.get_data()
    recipient_id = data.get("recipient_id")
    sender_hashed_id = get_hashed_id(message.from_user.id, HASH_SALT)

    if not recipient_id:
        await message.answer("خطا: کاربر مقصد مشخص نیست. لطفاً دوباره امتحان کنید.", reply_markup=main_keyboard)
        await state.clear()
        return

    try:
        sent_message = await bot.copy_message(
            chat_id=recipient_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id
        )

        conn = sqlite3.connect("anonymous_chat.db")
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO messages (sender_hashed_id, recipient_hashed_id, telegram_message_id) VALUES (?, ?, ?)",
            (sender_hashed_id, get_hashed_id(recipient_id, HASH_SALT), sent_message.message_id)
        )
        conn.commit()
        db_message_id = cursor.lastrowid
        conn.close()

        reply_markup = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="✍️ پاسخ", callback_data=f"reply_{db_message_id}")]]
        )
        await bot.edit_message_reply_markup(
            chat_id=recipient_id,
            message_id=sent_message.message_id,
            reply_markup=reply_markup
        )

        await message.answer("پیام شما با موفقیت به صورت ناشناس ارسال شد.", reply_markup=main_keyboard)

    except TelegramBadRequest as e:
        logging.error(f"Error forwarding to {recipient_id}: {e}")
        await message.answer("ارسال پیام با خطا مواجه شد. ممکن است کاربر ربات را بلاک کرده باشد یا شناسه اشتباه باشد.", reply_markup=main_keyboard)
    await state.clear()

async def handle_reply_button(callback: CallbackQuery, state: FSMContext):
    db_message_id = int(callback.data.split("_")[1])

    conn = sqlite3.connect("anonymous_chat.db")
    cursor = conn.cursor()
    cursor.execute("SELECT sender_hashed_id FROM messages WHERE id = ?", (db_message_id,))
    result = cursor.fetchone()
    conn.close()

    if not result:
        await callback.answer("خطا: این پیام در سیستم یافت نشد.", show_alert=True)
        return

    original_sender_hashed_id = result[0]
    original_sender_id = db_get_user_id_by_hash(original_sender_hashed_id)
    await state.update_data(reply_to_user_id=original_sender_id)
    await state.set_state(Form.getting_reply)

    await callback.message.answer("پاسخ خود را وارد کنید:")
    await callback.answer()

async def send_reply_message(message: Message, state: FSMContext):
    data = await state.get_data()
    reply_to_user_id = data.get("reply_to_user_id")

    if not reply_to_user_id:
        await message.answer("خطا در ارسال پاسخ. لطفاً دوباره تلاش کنید.", reply_markup=main_keyboard)
        await state.clear()
        return

    try:
        await bot.send_message(
            chat_id=reply_to_user_id,
            text=" پاسخی برای پیام ناشناس خود دریافت کردید: "
        )
        await bot.copy_message(
            chat_id=reply_to_user_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id
        )
        await message.answer("پاسخ شما با موفقیت ارسال شد.", reply_markup=main_keyboard)

    except TelegramBadRequest as e:
        logging.error(f"Error sending reply to {reply_to_user_id}: {e}")
        await message.answer("ارسال پاسخ با خطا مواجه شد.", reply_markup=main_keyboard)
    finally:
        await state.clear()

async def cancel_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    keyboard = admin_keyboard if message.from_user.id == ADMIN_USER_ID else main_keyboard
    await message.answer("عملیات لغو شد. به منوی اصلی بازگشتید.", reply_markup=keyboard)

async def handle_admin_reply_button(callback: CallbackQuery, state: FSMContext):
    """هندلر دکمه پاسخ ادمین به کاربر"""
    if callback.from_user.id != ADMIN_USER_ID:
        await callback.answer("این دکمه مخصوص ادمین است.", show_alert=True)
        return

    user_id_to_reply = int(callback.data.split("_")[2])
    await state.update_data(user_id_to_reply=user_id_to_reply)
    await state.set_state(Form.replying_to_user)
    await callback.message.answer(f"در حال پاسخ به کاربر با شناسه <code>{user_id_to_reply}</code>. پیام خود را ارسال کنید:")
    await callback.answer()

async def send_admin_reply_to_user(message: Message, state: FSMContext):
    """ارسال پیام پاسخ ادمین به کاربر"""
    data = await state.get_data()
    user_id = data.get("user_id_to_reply")

    if not user_id:
        await message.answer("خطا: شناسه کاربر برای پاسخ مشخص نیست.", reply_markup=admin_keyboard)
        await state.clear()
        return

    try:
        await bot.send_message(user_id, " پاسخی از طرف ادمین دریافت کردید: ")
        await bot.copy_message(user_id, from_chat_id=message.chat.id, message_id=message.message_id)
        await message.answer(f"پاسخ شما برای کاربر <code>{user_id}</code> ارسال شد.", reply_markup=admin_keyboard)
    except Exception as e:
        await message.answer(f"ارسال پیام به کاربر <code>{user_id}</code> ناموفق بود. خطا: {e}", reply_markup=admin_keyboard)
    finally:
        await state.clear()

async def broadcast_start(message: Message, state: FSMContext):
    await state.set_state(Form.getting_broadcast_message)
    await message.answer("پیامی که می‌خواهید برای همه کاربران ارسال شود را وارد کنید:")

async def process_broadcast(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("در حال ارسال پیام همگانی...")

    conn = sqlite3.connect("anonymous_chat.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    conn.close()

    sent_count = 0
    failed_count = 0
    for user in users:
        try:
            await bot.copy_message(
                chat_id=user[0],
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )
            sent_count += 1
            await asyncio.sleep(0.1)
        except TelegramForbiddenError:
            failed_count += 1
        except Exception as e:
            failed_count += 1
            logging.error(f"Broadcast error to user {user[0]}: {e}")

    await message.answer(
        f"پیام همگانی با موفقیت به {sent_count} کاربر ارسال شد.\n"
        f"ارسال به {failed_count} کاربر ناموفق بود (کاربرانی که ربات را بلاک کرده‌اند).",
        reply_markup=admin_keyboard
    )

async def get_user_list(message: Message):
    conn = sqlite3.connect("anonymous_chat.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username FROM users")
    users = cursor.fetchall()
    conn.close()

    user_list_text = f"تعداد کل کاربران: {len(users)}\n\n"
    for uid, uname in users[:20]:
        user_list_text += f"• <code>{uid}</code> - @{uname or 'None'}\n"

    await message.answer(user_list_text)

async def get_stats(message: Message):
    conn = sqlite3.connect("anonymous_chat.db")
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM messages")
        total_messages = cursor.fetchone()[0]

        today = datetime.date.today()
        start_of_week = today - datetime.timedelta(days=today.weekday())
        start_of_month = today.replace(day=1)
        start_of_year = today.replace(month=1, day=1)

        cursor.execute("SELECT COUNT(*) FROM users WHERE DATE(created_at) = ?", (today,))
        today_users = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM users WHERE DATE(created_at) >= ?", (start_of_week,))
        week_users = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM users WHERE DATE(created_at) >= ?", (start_of_month,))
        month_users = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM users WHERE DATE(created_at) >= ?", (start_of_year,))
        year_users = cursor.fetchone()[0]

        stats_text = (
            f"<b>📊 آمار کلی ربات:</b>\n\n"
            f"👤 تعداد کل کاربران: {total_users}\n"
            f"✉️ تعداد کل پیام‌ها: {total_messages}\n\n"
            f"<b>📈 آمار کاربران جدید:</b>\n"
            f"▫️ امروز: {today_users} نفر\n"
            f"▫️ این هفته: {week_users} نفر\n"
            f"▫️ این ماه: {month_users} نفر\n"
            f"▫️ امسال: {year_users} نفر"
        )
        await message.answer(stats_text)
    except Exception as e:
        logging.error(f"Error getting stats: {e}")
        await message.answer("خطایی در دریافت آمار رخ داد.")
    finally:
        conn.close()

async def force_sub_settings(message: Message):
    await message.answer("منوی مدیریت عضویت اجباری:", reply_markup=force_sub_keyboard)

async def list_force_sub_channels(message: Message):
    targets = db_get_force_sub_targets()
    if not targets:
        await message.answer("هیچ هدفی برای عضویت اجباری تنظیم نشده است.")
        return
    
    text = "لیست اهداف عضویت اجباری:\n\n"
    for target, type, button_text in targets:
        text += f"• <b>هدف:</b> <code>{target}</code>\n  <b>نوع:</b> {type}\n  <b>متن دکمه:</b> {button_text}\n"
    await message.answer(text)

async def add_force_sub_channel_start(message: Message, state: FSMContext):
    await state.set_state(Form.force_sub_add_channel)
    await message.answer("نام کاربری کانال/گروه را با @ وارد کنید (مثال: @mychannel):", reply_markup=ReplyKeyboardRemove())

async def add_force_sub_channel_get_target(message: Message, state: FSMContext):
    if not message.text.startswith('@'):
        await message.answer("نام کاربری باید با @ شروع شود. لطفاً دوباره تلاش کنید.")
        return
    await state.update_data(target=message.text, type='channel')
    await state.set_state(Form.force_sub_add_button_text)
    await message.answer("متن دکمه عضویت را وارد کنید (مثال: عضویت در کانال ما):", reply_markup=ReplyKeyboardRemove())

async def add_force_sub_link_start(message: Message, state: FSMContext):
    await state.set_state(Form.force_sub_add_link)
    await message.answer("لینک کامل سایت یا صفحه اجتماعی را وارد کنید (مثال: https://example.com):", reply_markup=ReplyKeyboardRemove())

async def add_force_sub_link_get_target(message: Message, state: FSMContext):
    if not message.text.startswith('http'):
        await message.answer("لینک نامعتبر است. لطفاً لینک کامل را وارد کنید.")
        return
    await state.update_data(target=message.text, type='link')
    await state.set_state(Form.force_sub_add_button_text)
    await message.answer("متن دکمه را وارد کنید (مثال: بازدید از سایت):", reply_markup=ReplyKeyboardRemove())

async def add_force_sub_get_button_text(message: Message, state: FSMContext):
    data = await state.get_data()
    target = data.get("target")
    target_type = data.get("type")
    button_text = message.text

    if not all([target, target_type, button_text]):
        await message.answer("خطایی در فرآیند رخ داد. لطفاً دوباره تلاش کنید.", reply_markup=force_sub_keyboard)
        await state.clear()
        return

    conn = sqlite3.connect("anonymous_chat.db")
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO force_sub_targets (target, type, button_text) VALUES (?, ?, ?)",
            (target, target_type, button_text)
        )
        conn.commit()
        await message.answer(f"هدف '{target}' با موفقیت اضافه شد.", reply_markup=force_sub_keyboard)
    except sqlite3.IntegrityError:
        await message.answer("این هدف قبلاً در سیستم ثبت شده است.", reply_markup=force_sub_keyboard)
    finally:
        conn.close()
        await state.clear()

async def remove_force_sub_start(message: Message, state: FSMContext):
    await state.set_state(Form.force_sub_remove)
    await message.answer("آدرس هدفی که می‌خواهید حذف شود را وارد کنید:")

async def remove_force_sub_process(message: Message, state: FSMContext):
    target = message.text
    conn = sqlite3.connect("anonymous_chat.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM force_sub_targets WHERE target = ?", (target,))
    conn.commit()
    
    if cursor.rowcount > 0:
        await message.answer(f"هدف '{target}' با موفقیت حذف شد.", reply_markup=force_sub_keyboard)
    else:
        await message.answer("این هدف در لیست وجود ندارد.", reply_markup=force_sub_keyboard)
    
    conn.close()
    await state.clear()

async def back_to_main_admin_panel(message: Message):
    await message.answer("به پنل اصلی مدیریت بازگشتید.", reply_markup=admin_keyboard)

async def check_sub_callback(callback: CallbackQuery):
    targets = db_get_force_sub_targets()
    is_subscribed_to_all = True
    for target, target_type, button_text in targets:
        if target_type == 'channel':
            try:
                member = await bot.get_chat_member(chat_id=target, user_id=callback.from_user.id)
                if member.status not in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
                    is_subscribed_to_all = False
                    break
            except (TelegramBadRequest, TelegramAPIError):
                logging.warning(f"Bot is not admin in {target}. Trusting user {callback.from_user.id} click for check.")
                pass
            except Exception as e:
                logging.error(f"Error in check_sub_callback for {target}: {e}")
                await callback.answer("خطایی در بررسی عضویت رخ داد.", show_alert=True)
                return

    if is_subscribed_to_all:
        await callback.message.delete()
        await callback.answer("عضویت شما تایید شد. اکنون می‌توانید از ربات استفاده کنید.", show_alert=True)
        await bot.send_message(callback.from_user.id, "به ربات چت ناشناس خوش آمدید.", reply_markup=main_keyboard)
    else:
        await callback.answer("شما هنوز در تمام کانال‌ها عضو نشده‌اید!", show_alert=True)

async def set_bot_description():
    try:
        await bot.set_my_description("💬 با من می‌تونی به صورت ناشناس برای دوستات پیام بفرستی! لینک خودت رو بساز و برای بقیه بفرست.")
        logging.info("Bot description set successfully.")
    except Exception as e:
        logging.error(f"Could not set bot description: {e}")

def setup_bot():
    print("--- شروع نصب ربات چت ناشناس ---")
    
    token = input("1. لطفا توکن ربات تلگرام خود را وارد کنید: ")
    admin_id = input("2. لطفا شناسه عددی (User ID) ادمین را وارد کنید: ")
    
    if not token or not admin_id.isdigit():
        print("خطا: توکن یا شناسه ادمین نامعتبر است. نصب متوقف شد.")
        return

    salt = secrets.token_hex(32)

    config_content = f"""# --- تنظیمات اصلی ربات ---

TELEGRAM_BOT_TOKEN = "{token}"
ADMIN_USER_ID = {admin_id}
HASH_SALT = "{salt}"
"""
    with open("config.py", "w", encoding="utf-8") as f:
        f.write(config_content)
    
    print("\nفایل 'config.py' با موفقیت ایجاد شد.")
    print("نصب با موفقیت انجام شد. اکنون می‌توانید ربات را اجرا کنید.")

async def main() -> None:
    global bot, dp
    
    bot = Bot(token=TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()
    
    await register_handlers(dp)

    setup_database()
    await set_bot_description()
    await dp.start_polling(bot)

if __name__ == "__main__":
    if not os.path.exists('config.py'):
        setup_bot()
    else:
        from config import TELEGRAM_BOT_TOKEN, ADMIN_USER_ID, HASH_SALT
        asyncio.run(main())