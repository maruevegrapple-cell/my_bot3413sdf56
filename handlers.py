import asyncio
import time
import random
import logging
import io
import string
import os
import requests
import traceback
import json
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from io import BytesIO

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile, FSInputFile
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import (
    MAIN_ADMIN_ID,
    BOT_USERNAME,
    VIDEO_PRICE,
    BONUS_AMOUNT,
    BONUS_COOLDOWN,
    REF_BONUS,
    REF_PERCENT,
    CHANNEL_ID,
    SUBSCRIBE_BONUS,
    ANON_CHAT_LINK,
    PRIVATE_PRICE_USD,
    PRIVATE_PRICE_STARS,
    SUBSCRIPTIONS,
    CANDY_PACKS,
    SPAM_COOLDOWN,
    LOLZ_MERCHANT_SECRET_KEY,
    LOLZ_MERCHANT_ID,
    MAX_MIRRORS_PER_USER
)

from db import (
    cursor, conn, get_mandatory_channels, add_mandatory_channel, remove_mandatory_channel,
    has_received_subscribe_bonus, mark_subscribe_bonus_received,
    is_admin, is_main_admin, can_manage_admins, get_all_admins, add_admin, remove_admin,
    set_main_admin, get_main_admin_id,
    get_total_users, get_verified_users, get_users_with_balance, get_total_balance,
    get_max_balance, get_avg_balance, get_video_count, get_watched_stats,
    get_payments_stats, get_promo_stats, get_bonus_stats, get_referral_stats,
    update_user_balance, get_user, get_user_payments, get_referrals_count,
    get_top_referrers, get_top_balances, add_payment, mark_payment_paid, get_payment,
    add_promo_code, get_promo_code, use_promo_code, check_promo_used,
    update_last_bonus, add_video, mark_video_watched, get_user_watched_videos,
    get_pending_referrer_bonus, clear_pending_referrer_bonus,
    get_active_tasks, get_task, add_task, remove_task, update_task,
    get_user_task_status, submit_task, approve_task, reject_task,
    get_pending_tasks, get_user_completed_tasks, can_complete_task, get_user_completed_count,
    get_user_task_records, delete_user_task_record, get_task_record_by_id, delete_task_record_by_id,
    has_private_access, add_private_purchase, mark_private_paid, get_private_purchase,
    get_user_subscription, get_user_subscriptions, add_subscription, remove_subscription, check_and_give_daily_bonus, get_all_active_subscriptions,
    rate_video, get_video_rating, get_user_video_rating, get_videos_sorted_by_rating, get_video_count_for_user,
    TASK_CATEGORIES, get_active_tasks_by_category,
    add_lolz_payment, mark_lolz_payment_paid, get_lolz_payment,
    get_user_language_db, set_user_language_db,
    get_battlepass, update_battlepass, create_battlepass, add_battlepass_exp_db,
    claim_hourly_exp_db, claim_battlepass_reward_db, activate_premium_battlepass_db,
    get_auto_tasks, get_auto_task, add_auto_task, remove_auto_task, update_auto_task,
    get_user_auto_task_status, submit_auto_task, get_pending_auto_tasks,
    approve_auto_task, reject_auto_task, get_auto_tasks_by_category,
    get_auto_task_record_by_id, delete_auto_task_record_by_id,
    get_user_mirror_bots_db, add_mirror_bot_db, remove_mirror_bot_db, toggle_mirror_bot_db,
    get_mirror_bot_by_token_db, get_mirror_bot_by_id
)

from keyboards import (
    fake_menu, main_menu, video_menu, get_admin_menu, 
    confirm_menu, subscribe_menu, op_menu, admin_manage_menu,
    get_task_action_menu, admin_tasks_keyboard,
    private_pay_menu, get_private_crypto_menu, subscriptions_menu,
    get_requests_menu, get_request_action_menu, rework_confirm_menu,
    get_categories_menu, get_tasks_menu_by_category, get_category_management_menu,
    get_tasks_by_category_menu, get_move_category_menu,
    task_category_keyboard,
    get_shop_menu, get_payment_methods_menu, get_crypto_currency_menu,
    get_invoice_payment_menu, get_stars_payment_menu, get_stars_approve_menu,
    language_keyboard,
    get_battlepass_menu, get_battlepass_info_text, get_battlepass_premium_menu,
    get_battlepass_tasks_menu,
    get_auto_categories_menu, get_auto_tasks_menu_by_category, get_auto_task_action_menu,
    admin_auto_tasks_keyboard, get_auto_category_management_menu, get_auto_tasks_by_category_menu,
    get_move_auto_category_menu, auto_task_category_keyboard, get_auto_requests_menu, get_auto_request_action_menu,
    get_mirror_menu, get_my_mirrors_keyboard, get_mirror_details_keyboard, get_mirror_info_text, get_mirror_create_instruction,
    get_mirrors_admin_menu,
    get_main_menu  # <--- ДОБАВЬ ЭТУ СТРОКУ
)

from payments import (
    create_invoice, 
    check_invoice, 
    AVAILABLE_ASSETS, 
    get_asset_icon,
    get_exchange_rates,
    convert_usd_to_crypto,
    PACKS,
    stars_payment_requests,
    add_stars_payment_request,
    get_stars_payment_request,
    approve_stars_payment,
    reject_stars_payment,
    activate_premium_battlepass_payment
)

from locales import get_text, set_user_language, get_user_language
from battlepass import BATTLEPASS_LEVELS, MAX_LEVEL, PREMIUM_PRICE_STARS, PREMIUM_PRICE_USD

from mirrors import (
    start_mirror_bot, stop_mirror_bot, add_mirror_bot_by_user, remove_mirror_bot_by_user,
    get_all_mirror_bots, remove_mirror_bot, stop_all_mirror_bots, start_all_mirror_bots
)

try:
    from lolz_payments import create_lolz_invoice, check_lolz_payment
    LOLZ_AVAILABLE = True
except ImportError:
    LOLZ_AVAILABLE = False
    print("⚠️ Lolz payments not available")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = Router()

# ========== ТЕСТОВЫЙ ХЭНДЛЕР ДЛЯ ДЕБАГА ==========
@router.message(CommandStart())
async def test_start_handler(message: Message):
    await message.answer("✅ ТЕСТ: Бот получил команду /start и отвечает!")
    logger.info(f"🔵🔵🔵 ТЕСТОВЫЙ ХЭНДЛЕР СРАБОТАЛ ДЛЯ {message.from_user.id}")


TEMP_DIR = "temp_videos"
os.makedirs(TEMP_DIR, exist_ok=True)

SUGGESTION_REWARD = 3

suggested_videos = {}
suggestion_mode = set()
user_last_action = {}

pending_invoices = {}

ANON_CHAT_RESPONSES = [
    "👤 Незнакомец: Привет! Как дела?",
    "👤 Незнакомец: Я тоже люблю смотреть видео!",
    "👤 Незнакомец: Ты откуда?",
    "👤 Незнакомец: Классный бот, правда?",
    "👤 Незнакомец: Давай дружить!",
    "👤 Незнакомец: У тебя есть любимое видео?",
    "👤 Незнакомец: Мне нравится этот бот!",
    "👤 Незнакомец: Какой твой любимый фильм?",
    "👤 Незнакомец: Ты давно пользуешься ботом?",
    "👤 Незнакомец: Сегодня хороший день!",
    "👤 Незнакомец: Я из другого города...",
    "👤 Незнакомец: Расскажи о себе!",
    "👤 Незнакомец: 😊",
    "👤 Незнакомец: Круто!",
    "👤 Незнакомец: Понял, принял.",
    "👤 Незнакомец: Ого, интересно!",
    "👤 Незнакомец: Я тоже так думаю.",
    "👤 Незнакомец: Ахаха, смешно 😄",
    "👤 Незнакомец: Да ну!",
    "👤 Незнакомец: Серьёзно?",
    "👤 Незнакомец: Собеседник покинул чат...",
    "👤 Незнакомец: Извини, мне пора идти. Пока!",
    "👤 Незнакомец: Был рад пообщаться!",
    "👤 Незнакомец: Может ещё поболтаем позже?",
    "👤 Незнакомец: Ты классный собеседник!",
    "👤 Незнакомец: Удачи тебе!",
    "👤 Незнакомец: Пока-пока! 👋",
]

class PromoStates(StatesGroup):
    waiting_for_promo = State()

class AdminStates(StatesGroup):
    waiting_for_broadcast = State()
    waiting_for_broadcast_confirm = State()
    waiting_for_add_balance_user = State()
    waiting_for_add_balance_amount = State()
    waiting_for_remove_balance_user = State()
    waiting_for_remove_balance_amount = State()
    waiting_for_add_promo_code = State()
    waiting_for_add_promo_reward = State()
    waiting_for_add_promo_uses = State()
    waiting_for_support_reply = State()
    waiting_for_add_admin_id = State()
    waiting_for_add_admin_username = State()
    waiting_for_add_admin_permissions = State()
    waiting_for_remove_admin_id = State()
    waiting_for_cloud_url = State()
    waiting_for_payment_search = State()
    waiting_for_top_refs = State()
    waiting_for_user_search = State()
    waiting_for_user_info = State()
    waiting_for_rework_message = State()
    waiting_for_subscription_user = State()
    waiting_for_subscription_type = State()
    waiting_for_active_subscriptions = State()
    waiting_for_edit_task_id = State()
    waiting_for_edit_task_title = State()
    waiting_for_edit_task_description = State()
    waiting_for_edit_task_reward = State()
    waiting_for_edit_task_max_completions = State()
    waiting_for_edit_task_category = State()
    waiting_for_user_subscriptions = State()
    waiting_for_rework_confirm = State()
    waiting_for_task_category = State()
    waiting_for_auto_edit_task_id = State()
    waiting_for_auto_edit_task_title = State()
    waiting_for_auto_edit_task_description = State()
    waiting_for_auto_edit_task_reward = State()
    waiting_for_auto_edit_task_max_completions = State()
    waiting_for_auto_edit_task_category = State()
    waiting_for_mirror_token = State()

class CaptchaStates(StatesGroup):
    waiting_for_captcha = State()

class MathCaptchaStates(StatesGroup):
    waiting_for_math_captcha = State()

class SubscribeStates(StatesGroup):
    waiting_for_subscribe = State()
    waiting_for_support_message = State()
    waiting_for_support_photo = State()

class CustomPayStates(StatesGroup):
    waiting_for_amount = State()

class OpStates(StatesGroup):
    waiting_for_channel_id = State()
    waiting_for_channel_name = State()
    waiting_for_channel_link = State()

class CreateTaskStates(StatesGroup):
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_reward = State()
    waiting_for_max_completions = State()
    waiting_for_category = State()

class CreateAutoTaskStates(StatesGroup):
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_reward = State()
    waiting_for_max_completions = State()
    waiting_for_category = State()

class TaskStates(StatesGroup):
    waiting_for_task_photo = State()

class AdminTaskStates(StatesGroup):
    waiting_for_task_id_to_delete = State()

class AdminAutoTaskStates(StatesGroup):
    waiting_for_task_id_to_delete = State()

class AdminRequestStates(StatesGroup):
    waiting_for_rework_text = State()
    waiting_for_rework_confirm = State()

class FakeChatStates(StatesGroup):
    waiting_for_anon_message = State()

class MirrorStates(StatesGroup):
    waiting_for_token = State()

captcha_data = {}
captcha_attempts = {}
math_captcha_data = {}
math_captcha_attempts = {}
banned_users = {}
broadcast_mode = set()
custom_pay_wait = set()
current_video_id = {}
anon_chat_sessions = {}

async def check_spam(user_id: int) -> bool:
    now = time.time()
    last = user_last_action.get(user_id, 0)
    if now - last < SPAM_COOLDOWN:
        return True
    user_last_action[user_id] = now
    return False

def is_banned(user_id: int) -> tuple:
    if user_id in banned_users:
        ban_until = banned_users[user_id]
        if datetime.now() < ban_until:
            return True, ban_until
        else:
            del banned_users[user_id]
    return False, None

async def check_subscription(bot, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status not in ["left", "kicked"]
    except:
        return False

def has_referrer(user_id: int) -> bool:
    cursor.execute("SELECT referrer FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    return row and row["referrer"] is not None

def is_verified(user_id: int) -> bool:
    cursor.execute("SELECT is_verified FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    return row and row["is_verified"] == 1

def generate_ref_code(length=6):
    chars = string.ascii_uppercase + string.digits
    chars = chars.replace('O', '').replace('0', '').replace('I', '').replace('1', '')
    while True:
        code = ''.join(random.choices(chars, k=length))
        cursor.execute("SELECT user_id FROM users WHERE ref_code = ?", (code,))
        if not cursor.fetchone():
            return code

def check_admin_access(user_id: int, require_main: bool = False, require_manage: bool = False) -> tuple:
    if is_main_admin(user_id):
        return True, True, True, True
    if is_admin(user_id):
        can_manage = can_manage_admins(user_id)
        if require_main:
            return False, True, False, can_manage
        if require_manage and not can_manage:
            return False, True, False, can_manage
        return True, True, False, can_manage
    return False, False, False, False

async def safe_answer(call: CallbackQuery, text: str = None, show_alert: bool = False):
    try:
        if text:
            await call.answer(text, show_alert=show_alert)
        else:
            await call.answer()
    except:
        pass

async def check_access(bot, user_id: int, state: FSMContext, message: Message = None, call: CallbackQuery = None) -> bool:
    if check_admin_access(user_id)[0]:
        return True
    if not is_verified(user_id):
        if message:
            await message.answer(get_text(user_id, "verification_required"))
        elif call:
            await safe_answer(call, get_text(user_id, "verification_required"), show_alert=True)
        return False
    is_subscribed = await check_subscription(bot, user_id)
    if not is_subscribed:
        await state.set_state(SubscribeStates.waiting_for_subscribe)
        if message:
            await message.answer(
                get_text(user_id, "subscribe_required").format(SUBSCRIBE_BONUS),
                reply_markup=subscribe_menu
            )
        elif call:
            await call.message.answer(
                get_text(user_id, "subscribe_required").format(SUBSCRIBE_BONUS),
                reply_markup=subscribe_menu
            )
        return False
    return True

def generate_captcha_image() -> tuple:
    length = 4
    chars = string.ascii_uppercase + string.digits
    exclude = ['O', '0', 'I', '1', 'S', '5', 'Z', '2']
    for c in exclude:
        chars = chars.replace(c, '')
    code = ''.join(random.choices(chars, k=length))
    width, height = 800, 300
    image = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(image)
    draw.rectangle([(0, 0), (width, height)], fill=(255, 255, 255))
    for i in range(0, width, 50):
        draw.line([(i, 0), (i, height)], fill=(230, 230, 230), width=1)
    for i in range(0, height, 50):
        draw.line([(0, i), (width, i)], fill=(230, 230, 230), width=1)
    font = None
    try:
        font_paths = [
            "C:\\Windows\\Fonts\\Arial.ttf",
            "C:\\Windows\\Fonts\\Impact.ttf",
            "C:\\Windows\\Fonts\\arialbd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "arial.ttf"
        ]
        for path in font_paths:
            if os.path.exists(path):
                font = ImageFont.truetype(path, 80)
                break
    except:
        font = None
    if font is None:
        font = ImageFont.load_default()
    colors = [(0, 0, 0), (0, 0, 150), (150, 0, 0), (0, 150, 0)]
    positions = [(120, 100), (270, 100), (420, 100), (570, 100)]
    for i, char in enumerate(code):
        x, y = positions[i]
        color = colors[i % len(colors)]
        if font != ImageFont.load_default():
            for dx in [-2, -1, 0, 1, 2]:
                for dy in [-2, -1, 0, 1, 2]:
                    if dx != 0 or dy != 0:
                        draw.text((x + dx, y + dy), char, fill=(200, 200, 200), font=font)
            draw.text((x, y), char, fill=color, font=font)
        else:
            for dx in range(-3, 4):
                for dy in range(-3, 4):
                    draw.text((x + dx, y + dy), char, fill=color, font=font)
    for _ in range(100):
        x = random.randint(0, width)
        y = random.randint(0, height)
        draw.point((x, y), fill=(100, 100, 100))
    bio = io.BytesIO()
    image.save(bio, 'PNG', quality=95)
    bio.seek(0)
    return bio.getvalue(), code

def generate_math_captcha() -> tuple:
    operations = ['+', '-', '*']
    op = random.choice(operations)
    
    if op == '+':
        a = random.randint(10, 50)
        b = random.randint(5, 30)
        answer = a + b
        text = f"{a} + {b} = ?"
    elif op == '-':
        a = random.randint(20, 60)
        b = random.randint(5, a - 5)
        answer = a - b
        text = f"{a} - {b} = ?"
    else:
        a = random.randint(2, 10)
        b = random.randint(2, 10)
        answer = a * b
        text = f"{a} × {b} = ?"
    
    return text, answer

@router.message(F.forward_from | F.forward_from_chat)
async def block_forward(message: Message):
    await message.delete()

@router.message(F.video)
async def handle_video(message: Message, bot: Bot):
    user_id = message.from_user.id
    has_access, _, _, _ = check_admin_access(user_id)
    if has_access:
        await upload_video(message)
    else:
        await handle_suggestion_video(message, bot)

async def upload_video(message: Message):
    user_id = message.from_user.id
    logger.info(f"📹 Админ {user_id} загружает видео")
    file_id = message.video.file_id
    file_name = message.video.file_name if message.video.file_name else "без названия"
    file_size = message.video.file_size
    duration = message.video.duration
    try:
        cursor.execute("SELECT id FROM videos WHERE file_id = ?", (file_id,))
        existing = cursor.fetchone()
        if existing:
            await message.answer(
                f"⚠️ <b>Это видео уже есть в базе!</b>\n\n"
                f"🆔 <b>ID в базе:</b> {existing['id']}\n"
                f"📹 <b>File ID:</b> <code>{file_id}</code>"
            )
            return
        cursor.execute("INSERT INTO videos (file_id) VALUES (?)", (file_id,))
        conn.commit()
        cursor.execute("SELECT id FROM videos WHERE file_id = ?", (file_id,))
        video = cursor.fetchone()
        video_id = video['id'] if video else "неизвестно"
        cursor.execute("SELECT COUNT(*) as count FROM videos")
        total_videos = cursor.fetchone()["count"]
        cursor.execute("INSERT OR IGNORE INTO video_stats (video_id) VALUES (?)", (video_id,))
        conn.commit()
        await message.answer(
            f"✅ <b>ВИДЕО УСПЕШНО ДОБАВЛЕНО!</b>\n\n"
            f"📹 <b>Название:</b> {file_name}\n"
            f"🆔 <b>File ID:</b> <code>{file_id}</code>\n"
            f"🔢 <b>Номер в базе:</b> {video_id}\n"
            f"⏱ <b>Длительность:</b> {duration} сек\n"
            f"📊 <b>Размер:</b> {file_size // 1024} KB\n"
            f"🎥 <b>Всего видео в базе:</b> {total_videos}"
        )
    except Exception as e:
        logger.error(f"❌ Ошибка при добавлении видео: {e}")
        await message.answer(f"❌ Ошибка при добавлении видео: {e}")

@router.callback_query(F.data == "suggestion")
async def suggestion_start(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    if await check_spam(user_id):
        await safe_answer(call, get_text(user_id, "spam_warning"), show_alert=True)
        return
    if not await check_access(call.bot, user_id, state, call=call):
        return
    await safe_answer(call)
    suggestion_mode.add(user_id)
    await call.message.answer(
        "🎬 <b>ПРЕДЛОЖКА</b>\n\n"
        "📹 Отправьте видео, которое хотите предложить для добавления в бота.\n\n"
        "✅ Если видео одобрят, вы получите +3 🍬\n"
        "❌ Если отклонят, вы получите уведомление\n\n"
        "⏳ Режим предложки активен 5 минут"
    )
    async def exit_suggestion_mode():
        await asyncio.sleep(300)
        if user_id in suggestion_mode:
            suggestion_mode.discard(user_id)
            try:
                await call.message.answer("⏰ Время вышло. Режим предложки отключен.")
            except:
                pass
    asyncio.create_task(exit_suggestion_mode())

async def handle_suggestion_video(message: Message, bot: Bot):
    user_id = message.from_user.id
    if user_id not in suggestion_mode:
        return
    suggestion_mode.discard(user_id)
    username = message.from_user.username or "нет username"
    file_id = message.video.file_id
    file_name = message.video.file_name or "без названия"
    duration = message.video.duration
    file_size = message.video.file_size
    if file_size > 50 * 1024 * 1024:
        await message.answer("❌ Видео слишком большое. Максимальный размер: 50MB")
        return
    short_id = file_id[-8:]
    suggested_videos[short_id] = {
        "user_id": user_id,
        "username": username,
        "file_name": file_name,
        "duration": duration,
        "message_id": message.message_id,
        "file_id": file_id
    }
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    balance = user["balance"] if user else 0
    admins = get_all_admins()
    admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Одобрить", callback_data=f"app_{short_id}"),
         InlineKeyboardButton(text="❌ Отклонить", callback_data=f"rej_{short_id}")]
    ])
    sent_count = 0
    for admin in admins:
        admin_id = admin["user_id"]
        try:
            await bot.send_video(
                admin_id,
                video=file_id,
                caption=(
                    f"🎬 <b>НОВОЕ ПРЕДЛОЖЕННОЕ ВИДЕО</b>\n\n"
                    f"👤 От: @{username}\n"
                    f"🆔 ID: <code>{user_id}</code>\n"
                    f"📝 Название: {file_name}\n"
                    f"⏱ Длительность: {duration} сек\n"
                    f"💰 Баланс пользователя: {balance} 🍬\n\n"
                    f"Выберите действие:"
                ),
                reply_markup=admin_keyboard
            )
            sent_count += 1
        except:
            pass
    if sent_count > 0:
        await message.answer("✅ <b>Видео отправлено на модерацию!</b>")
    else:
        await message.answer("❌ Ошибка при отправке видео.")
        if short_id in suggested_videos:
            del suggested_videos[short_id]

@router.callback_query(F.data.startswith("app_"))
async def suggest_approve(call: CallbackQuery, state: FSMContext, bot: Bot):
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    short_id = call.data.replace("app_", "")
    video_data = suggested_videos.get(short_id)
    if not video_data:
        await safe_answer(call, "❌ Видео не найдено", show_alert=True)
        await call.message.delete()
        return
    file_id = video_data["file_id"]
    user_id = video_data["user_id"]
    try:
        cursor.execute("INSERT INTO videos (file_id) VALUES (?)", (file_id,))
        video_id = cursor.lastrowid
        cursor.execute("INSERT INTO video_stats (video_id) VALUES (?)", (video_id,))
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (SUGGESTION_REWARD, user_id))
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        new_balance = cursor.fetchone()["balance"]
        conn.commit()
        try:
            await bot.send_message(
                user_id,
                f"✅ <b>Видео одобрено!</b>\n\n"
                f"🎁 Начислено +{SUGGESTION_REWARD} 🍬\n"
                f"💰 Текущий баланс: {new_balance} 🍬"
            )
        except:
            pass
        await safe_answer(call, f"✅ Видео одобрено! +{SUGGESTION_REWARD} 🍬")
        await call.message.delete()
    except Exception as e:
        logger.error(f"Ошибка при одобрении: {e}")
        await safe_answer(call, "❌ Ошибка", show_alert=True)
    if short_id in suggested_videos:
        del suggested_videos[short_id]

@router.callback_query(F.data.startswith("rej_"))
async def suggest_reject(call: CallbackQuery, state: FSMContext, bot: Bot):
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    short_id = call.data.replace("rej_", "")
    video_data = suggested_videos.get(short_id)
    if not video_data:
        await safe_answer(call, "❌ Видео не найдено", show_alert=True)
        await call.message.delete()
        return
    user_id = video_data["user_id"]
    try:
        await bot.send_message(
            user_id,
            f"❌ <b>Видео отклонено</b>\n\n"
            f"Попробуйте предложить другое видео."
        )
        await safe_answer(call, "❌ Видео отклонено")
        await call.message.delete()
    except:
        pass
    if short_id in suggested_videos:
        del suggested_videos[short_id]

@router.callback_query(F.data == "admin_upload_url")
async def admin_upload_url(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    has_access, _, _, _ = check_admin_access(user_id)
    if not has_access:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    await safe_answer(call)
    await state.set_state(AdminStates.waiting_for_cloud_url)
    await call.message.answer(
        "🔗 <b>Загрузка видео по ссылке</b>\n\n"
        "Отправьте ссылку на видео.\n\n"
        "Поддерживаются прямые ссылки на .mp4, Google Drive, Dropbox"
    )

@router.message(AdminStates.waiting_for_cloud_url)
async def process_video_url(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    has_access, _, _, _ = check_admin_access(user_id)
    if not has_access:
        return
    url = message.text.strip()
    await state.clear()
    status_msg = await message.answer("🔄 Обрабатываю ссылку...")
    filename = None
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, stream=True, headers=headers, allow_redirects=True, timeout=30)
        if response.status_code != 200:
            await status_msg.edit_text(f"❌ Ошибка доступа к ссылке (код {response.status_code})")
            return
        content_type = response.headers.get('content-type', '')
        content_length = int(response.headers.get('content-length', 0))
        if not ('video' in content_type or content_length > 1024 * 1024):
            await status_msg.edit_text("❌ По ссылке не видео или файл слишком маленький")
            return
        ext = '.mp4'
        if 'video/quicktime' in content_type:
            ext = '.mov'
        elif 'video/x-msvideo' in content_type:
            ext = '.avi'
        elif 'video/x-matroska' in content_type:
            ext = '.mkv'
        filename = f"{TEMP_DIR}/video_{int(time.time())}{ext}"
        await status_msg.edit_text("⏬ Скачиваю видео...")
        with open(filename, 'wb') as f:
            downloaded = 0
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if downloaded % (10 * 1024 * 1024) < 8192:
                        mb = downloaded // (1024 * 1024)
                        await status_msg.edit_text(f"⏬ Скачано: {mb} MB")
        file_size = os.path.getsize(filename)
        await status_msg.edit_text(f"✅ Скачано {file_size // (1024 * 1024)} MB. Отправляю в Telegram...")
        video_file = FSInputFile(filename)
        sent_message = await message.answer_video(video_file)
        file_id = sent_message.video.file_id
        cursor.execute("INSERT INTO videos (file_id) VALUES (?)", (file_id,))
        video_id = cursor.lastrowid
        cursor.execute("INSERT INTO video_stats (video_id) VALUES (?)", (video_id,))
        conn.commit()
        cursor.execute("SELECT COUNT(*) as count FROM videos")
        total = cursor.fetchone()["count"]
        await message.answer(
            f"✅ <b>ВИДЕО УСПЕШНО ДОБАВЛЕНО!</b>\n\n"
            f"📹 <b>File ID:</b> <code>{file_id}</code>\n"
            f"📊 <b>Размер:</b> {file_size // (1024 * 1024)} MB\n"
            f"🎥 <b>Всего видео в базе:</b> {total}"
        )
    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка: {e}")
    finally:
        if filename and os.path.exists(filename):
            os.remove(filename)

@router.message(Command("dl"))
async def quick_download(message: Message, bot: Bot):
    user_id = message.from_user.id
    has_access, _, _, _ = check_admin_access(user_id)
    if not has_access:
        return
    try:
        url = message.text.split()[1]
        status_msg = await message.answer("🔄 Загружаю...")
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, stream=True, headers=headers, timeout=30)
        if response.status_code != 200:
            await status_msg.edit_text(f"❌ Ошибка {response.status_code}")
            return
        filename = f"{TEMP_DIR}/quick_{int(time.time())}.mp4"
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        await status_msg.edit_text("📤 Отправляю...")
        video_file = FSInputFile(filename)
        sent = await message.answer_video(video_file)
        file_id = sent.video.file_id
        cursor.execute("INSERT INTO videos (file_id) VALUES (?)", (file_id,))
        video_id = cursor.lastrowid
        cursor.execute("INSERT INTO video_stats (video_id) VALUES (?)", (video_id,))
        conn.commit()
        os.remove(filename)
        await message.answer(f"✅ Готово! ID: <code>{file_id}</code>")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@router.message(CommandStart())
async def start(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    username = message.from_user.username or "пользователь"
    first_name = message.from_user.first_name or "Пользователь"
    logger.info(f"🟢 START from {user_id} (@{username})")
    
    user_lang = get_user_language_db(user_id)
    set_user_language(user_id, user_lang)
    
    bonus = check_and_give_daily_bonus(user_id)
    if bonus:
        await message.answer(get_text(user_id, "bonus_received").format(bonus))
    banned, ban_until = is_banned(user_id)
    if banned:
        remaining = ban_until - datetime.now()
        minutes = remaining.seconds // 60
        seconds = remaining.seconds % 60
        await message.answer(
            f"🚫 <b>ДОСТУП ЗАБЛОКИРОВАН</b>\n\n"
            f"⏳ Осталось: {minutes} мин {seconds} сек"
        )
        return
    has_access, _, is_main, can_manage = check_admin_access(user_id)
    if has_access:
        cursor.execute("""
            INSERT OR IGNORE INTO users (user_id, username, is_verified, is_admin)
            VALUES (?, ?, 1, 1)
        """, (user_id, username))
        cursor.execute("UPDATE users SET is_verified = 1, username = ? WHERE user_id = ?", (username, user_id))
        cursor.execute("SELECT ref_code FROM users WHERE user_id = ?", (user_id,))
        admin_data = cursor.fetchone()
        if not admin_data or not admin_data["ref_code"]:
            ref_code = generate_ref_code()
            cursor.execute("UPDATE users SET ref_code = ? WHERE user_id = ?", (ref_code, user_id))
        conn.commit()
        await message.answer("👑 Админ-панель", reply_markup=get_admin_menu(is_main, can_manage))
        return
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    args = message.text.split()
    referrer_id = None
    has_ref_in_link = False
    if len(args) > 1:
        ref_code = args[1].upper()
        cursor.execute("SELECT user_id FROM users WHERE ref_code = ?", (ref_code,))
        referrer = cursor.fetchone()
        if referrer:
            referrer_id = referrer["user_id"]
            if referrer_id != user_id:
                has_ref_in_link = True
                logger.info(f"🔗 Реферальная ссылка! Код: {ref_code}, Реферер: {referrer_id}")
    if has_ref_in_link:
        logger.info(f"✅ Пользователь {user_id} перешел по реферальной ссылке")
        if user:
            if user["referrer"] is None:
                cursor.execute("UPDATE users SET referrer = ? WHERE user_id = ?", (referrer_id, user_id))
                conn.commit()
                cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (REF_BONUS, referrer_id))
                conn.commit()
                try:
                    await bot.send_message(
                        referrer_id,
                        f"🎁 <b>Новый реферал!</b>\n\n"
                        f"По вашей ссылке зарегистрировался пользователь @{username}\n"
                        f"➕ Вам начислено +{REF_BONUS} 🍬"
                    )
                except:
                    pass
            else:
                logger.info(f"🔄 Пользователь уже имеет реферера")
        else:
            logger.info(f"🆕 Создаем нового пользователя {user_id} с реферером {referrer_id}")
            new_ref_code = generate_ref_code()
            cursor.execute("""
                INSERT INTO users (user_id, username, referrer, is_verified, ref_code, subscribe_bonus_received, is_admin, language)
                VALUES (?, ?, ?, 0, ?, 0, 0, ?)
            """, (user_id, username, referrer_id, new_ref_code, user_lang))
            conn.commit()
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (REF_BONUS, referrer_id))
            conn.commit()
            try:
                await bot.send_message(
                    referrer_id,
                    f"🎁 <b>Новый реферал!</b>\n\n"
                    f"По вашей ссылке зарегистрировался новый пользователь @{username}\n"
                    f"➕ Вам начислено +{REF_BONUS} 🍬"
                )
            except:
                pass
        if not is_verified(user_id):
            if user_id in captcha_attempts:
                del captcha_attempts[user_id]
            if user_id in math_captcha_attempts:
                del math_captcha_attempts[user_id]
            image_bytes, captcha_code = generate_captcha_image()
            captcha_data[user_id] = captcha_code
            await state.update_data(captcha_code=captcha_code)
            await state.set_state(CaptchaStates.waiting_for_captcha)
            await message.answer_photo(
                photo=BufferedInputFile(file=image_bytes, filename="captcha.png"),
                caption="🔐 <b>ПОДТВЕРЖДЕНИЕ (ШАГ 1/2)</b>\n\n"
                        "Введите код с картинки:\n"
                        "⚠️ Только заглавные буквы и цифры\n"
                        "📊 Осталось попыток: 3/3"
            )
            return
        if is_verified(user_id):
            is_subscribed = await check_subscription(bot, user_id)
            if not is_subscribed:
                await state.set_state(SubscribeStates.waiting_for_subscribe)
                await message.answer(
                    get_text(user_id, "subscribe_required").format(SUBSCRIBE_BONUS),
                    reply_markup=subscribe_menu
                )
                return
            await message.answer(get_text(user_id, "welcome"), reply_markup=get_main_menu(user_id))
            return
    if not user:
        new_ref_code = generate_ref_code()
        cursor.execute("""
            INSERT INTO users (user_id, username, referrer, is_verified, ref_code, subscribe_bonus_received, is_admin, language)
            VALUES (?, ?, ?, 0, ?, 0, 0, ?)
        """, (user_id, username, referrer_id, new_ref_code, user_lang))
        conn.commit()
        if referrer_id:
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (REF_BONUS, referrer_id))
            conn.commit()
            try:
                await bot.send_message(
                    referrer_id,
                    f"🎁 <b>Новый реферал!</b>\n\n"
                    f"По вашей ссылке зарегистрировался новый пользователь @{username}\n"
                    f"➕ Вам начислено +{REF_BONUS} 🍬"
                )
            except:
                pass
    else:
        if not user["ref_code"]:
            new_ref_code = generate_ref_code()
            cursor.execute("UPDATE users SET ref_code = ? WHERE user_id = ?", (new_ref_code, user_id))
            conn.commit()
    if not has_referrer(user_id) and not referrer_id:
        await message.answer(
            f"Привет, @{username}. Добро пожаловать в главное меню!",
            reply_markup=fake_menu
        )
        return
    if not is_verified(user_id):
        if user_id in captcha_attempts:
            del captcha_attempts[user_id]
        if user_id in math_captcha_attempts:
            del math_captcha_attempts[user_id]
        image_bytes, captcha_code = generate_captcha_image()
        captcha_data[user_id] = captcha_code
        await state.update_data(captcha_code=captcha_code)
        await state.set_state(CaptchaStates.waiting_for_captcha)
        await message.answer_photo(
            photo=BufferedInputFile(file=image_bytes, filename="captcha.png"),
            caption="🔐 <b>ПОДТВЕРЖДЕНИЕ (ШАГ 1/2)</b>\n\n"
                    "Введите код с картинки:\n"
                    "⚠️ Только заглавные буквы и цифры\n"
                    "📊 Осталось попыток: 3/3"
        )
        return
    if is_verified(user_id):
        is_subscribed = await check_subscription(bot, user_id)
        if not is_subscribed:
            await state.set_state(SubscribeStates.waiting_for_subscribe)
            await message.answer(
                get_text(user_id, "subscribe_required").format(SUBSCRIBE_BONUS),
                reply_markup=subscribe_menu
            )
            return
        await message.answer(get_text(user_id, "welcome"), reply_markup=get_main_menu(user_id))

@router.message(CaptchaStates.waiting_for_captcha)
async def process_captcha(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    user_input = message.text.strip().upper()
    logger.info(f"🔍 Captcha input: {user_input}")
    banned, ban_until = is_banned(user_id)
    if banned:
        remaining = ban_until - datetime.now()
        minutes = remaining.seconds // 60
        seconds = remaining.seconds % 60
        await message.answer(
            f"🚫 <b>ДОСТУП ЗАБЛОКИРОВАН</b>\n\n"
            f"⏳ Осталось: {minutes} мин {seconds} сек"
        )
        await state.clear()
        return
    data = await state.get_data()
    correct_code = data.get('captcha_code') or captcha_data.get(user_id)
    if not correct_code:
        await message.answer("❌ Ошибка верификации. Нажми /start заново")
        await state.clear()
        return
    if user_input == correct_code:
        if user_id in captcha_data:
            del captcha_data[user_id]
        if user_id in captcha_attempts:
            del captcha_attempts[user_id]
        
        math_text, math_answer = generate_math_captcha()
        math_captcha_data[user_id] = math_answer
        await state.update_data(math_answer=math_answer)
        await state.set_state(MathCaptchaStates.waiting_for_math_captcha)
        
        await message.answer(
            f"✅ <b>Первый шаг пройден!</b>\n\n"
            f"🔢 <b>МАТЕМАТИЧЕСКАЯ ПРОВЕРКА (ШАГ 2/2)</b>\n\n"
            f"Решите пример:\n"
            f"<b>{math_text}</b>\n\n"
            f"Введите только число:\n"
            f"📊 Осталось попыток: 3/3"
        )
    else:
        attempts = captcha_attempts.get(user_id, 0) + 1
        captcha_attempts[user_id] = attempts
        if attempts >= 3:
            ban_time = datetime.now() + timedelta(minutes=10)
            banned_users[user_id] = ban_time
            if user_id in captcha_data:
                del captcha_data[user_id]
            if user_id in captcha_attempts:
                del captcha_attempts[user_id]
            await state.clear()
            await message.answer(
                f"🚫 <b>ДОСТУП ЗАБЛОКИРОВАН</b>\n\n"
                f"❌ Вы исчерпали все попытки (3/3)\n"
                f"⏳ Блокировка на 10 минут\n"
                f"🕐 Разблокировка: {ban_time.strftime('%H:%M:%S')}"
            )
            return
        image_bytes, new_code = generate_captcha_image()
        captcha_data[user_id] = new_code
        await state.update_data(captcha_code=new_code)
        remaining_attempts = 3 - attempts
        await message.answer_photo(
            photo=BufferedInputFile(file=image_bytes, filename="captcha.png"),
            caption=f"❌ <b>НЕПРАВИЛЬНЫЙ КОД!</b>\n\n"
                    f"Попробуйте еще раз:\n"
                    f"⚠️ Только заглавные буквы и цифры\n"
                    f"📊 Осталось попыток: {remaining_attempts}/3"
        )

@router.message(MathCaptchaStates.waiting_for_math_captcha)
async def process_math_captcha(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    user_input = message.text.strip()
    logger.info(f"🔢 Math captcha input: {user_input}")
    
    banned, ban_until = is_banned(user_id)
    if banned:
        remaining = ban_until - datetime.now()
        minutes = remaining.seconds // 60
        seconds = remaining.seconds % 60
        await message.answer(
            f"🚫 <b>ДОСТУП ЗАБЛОКИРОВАН</b>\n\n"
            f"⏳ Осталось: {minutes} мин {seconds} сек"
        )
        await state.clear()
        return
    
    data = await state.get_data()
    correct_answer = data.get('math_answer') or math_captcha_data.get(user_id)
    
    if correct_answer is None:
        await message.answer("❌ Ошибка верификации. Нажми /start заново")
        await state.clear()
        return
    
    try:
        user_answer = int(user_input)
    except ValueError:
        user_answer = None
    
    if user_answer == correct_answer:
        if user_id in math_captcha_data:
            del math_captcha_data[user_id]
        if user_id in math_captcha_attempts:
            del math_captcha_attempts[user_id]
        
        cursor.execute("UPDATE users SET is_verified = 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        await state.clear()
        
        await message.answer(
            f"🎉 <b>ВЕРИФИКАЦИЯ ПРОЙДЕНА!</b>\n\n"
            f"✅ Вы успешно прошли обе проверки!"
        )
        
        is_subscribed = await check_subscription(bot, user_id)
        if not is_subscribed:
            await state.set_state(SubscribeStates.waiting_for_subscribe)
            await message.answer(
                get_text(user_id, "subscribe_required").format(SUBSCRIBE_BONUS),
                reply_markup=subscribe_menu
            )
        else:
            await message.answer(
                get_text(user_id, "welcome"),
                reply_markup=get_main_menu(user_id)
            )
    else:
        attempts = math_captcha_attempts.get(user_id, 0) + 1
        math_captcha_attempts[user_id] = attempts
        
        if attempts >= 3:
            ban_time = datetime.now() + timedelta(minutes=10)
            banned_users[user_id] = ban_time
            if user_id in math_captcha_data:
                del math_captcha_data[user_id]
            if user_id in math_captcha_attempts:
                del math_captcha_attempts[user_id]
            await state.clear()
            await message.answer(
                f"🚫 <b>ДОСТУП ЗАБЛОКИРОВАН</b>\n\n"
                f"❌ Вы исчерпали все попытки (3/3)\n"
                f"⏳ Блокировка на 10 минут\n"
                f"🕐 Разблокировка: {ban_time.strftime('%H:%M:%S')}"
            )
            return
        
        math_text, math_answer = generate_math_captcha()
        math_captcha_data[user_id] = math_answer
        await state.update_data(math_answer=math_answer)
        remaining_attempts = 3 - attempts
        
        await message.answer(
            f"❌ <b>НЕПРАВИЛЬНЫЙ ОТВЕТ!</b>\n\n"
            f"Попробуйте еще раз:\n"
            f"<b>{math_text}</b>\n\n"
            f"Введите только число:\n"
            f"📊 Осталось попыток: {remaining_attempts}/3"
        )

@router.callback_query(F.data == "check_subscribe")
async def check_subscribe(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    
    print(f"🔍 check_subscribe: user {user_id} нажал кнопку")
    
    if not is_verified(user_id):
        if user_id in captcha_attempts:
            del captcha_attempts[user_id]
        if user_id in math_captcha_attempts:
            del math_captcha_attempts[user_id]
        
        image_bytes, captcha_code = generate_captcha_image()
        captcha_data[user_id] = captcha_code
        await state.update_data(captcha_code=captcha_code)
        await state.set_state(CaptchaStates.waiting_for_captcha)
        try:
            await call.message.delete()
        except:
            pass
        await call.message.answer_photo(
            photo=BufferedInputFile(file=image_bytes, filename="captcha.png"),
            caption="🔐 <b>ПОДТВЕРЖДЕНИЕ (ШАГ 1/2)</b>\n\n"
                    "Сначала пройдите верификацию.\n"
                    "Введите код с картинки:\n"
                    "⚠️ Только заглавные буквы и цифры"
        )
        await safe_answer(call, get_text(user_id, "verification_required"), show_alert=True)
        return
    
    is_subscribed = await check_subscription(bot, user_id)
    
    print(f"🔍 Результат проверки подписки: {is_subscribed}")
    
    if is_subscribed:
        if not has_received_subscribe_bonus(user_id):
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (SUBSCRIBE_BONUS, user_id))
            mark_subscribe_bonus_received(user_id)
            conn.commit()
            await safe_answer(call, get_text(user_id, "bonus_received").format(SUBSCRIBE_BONUS), show_alert=True)
        
        await safe_answer(call, "✅ Спасибо за подписку!", show_alert=True)
        await state.set_state(None)
        subscribe_message = call.message
        try:
            await subscribe_message.delete()
        except Exception as e:
            print(f"❌ Ошибка удаления сообщения: {e}")
        
        has_access, _, is_main, can_manage = check_admin_access(user_id)
        if has_access:
            await call.message.answer("👑 Админ-панель", reply_markup=get_admin_menu(is_main, can_manage))
        else:
            await call.message.answer(get_text(user_id, "welcome"), reply_markup=get_main_menu(user_id))
    else:
        await safe_answer(call, "❌ Вы не подписались на канал! Подпишитесь и нажмите кнопку снова.", show_alert=True)

@router.callback_query(F.data == "show_languages")
async def show_languages(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    await safe_answer(call)
    await call.message.answer(get_text(user_id, "choose_language"), reply_markup=language_keyboard)

@router.callback_query(F.data.startswith("lang_"))
async def change_language(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    lang = call.data.replace("lang_", "")
    
    if set_user_language_db(user_id, lang):
        set_user_language(user_id, lang)
        await safe_answer(call, get_text(user_id, "language_changed_en" if lang == "en" else "language_changed"), show_alert=True)
    else:
        await safe_answer(call, "❌ Error changing language", show_alert=True)
    
    has_access, _, is_main, can_manage = check_admin_access(user_id)
    if has_access:
        await call.message.edit_text("👑 Admin panel", reply_markup=get_admin_menu(is_main, can_manage))
    else:
        await call.message.edit_text(get_text(user_id, "welcome"), reply_markup=get_main_menu(user_id))

@router.callback_query(F.data == "battlepass_menu")
async def battlepass_menu(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    if await check_spam(user_id):
        await safe_answer(call, get_text(user_id, "spam_warning"), show_alert=True)
        return
    if not await check_access(bot, user_id, state, call=call):
        return
    
    bp = get_battlepass(user_id)
    if not bp:
        if create_battlepass(user_id):
            bp = get_battlepass(user_id)
        else:
            await call.message.answer("❌ Ошибка загрузки пропуска")
            return
    
    import json
    claimed = json.loads(bp["claimed_rewards"])
    
    next_hourly_seconds = 0
    if bp.get("last_hourly_claim"):
        last_time = datetime.fromisoformat(bp["last_hourly_claim"])
        elapsed = (datetime.now() - last_time).total_seconds()
        if elapsed < 3600:
            next_hourly_seconds = int(3600 - elapsed)
    
    text = get_battlepass_info_text(user_id, bp["level"], bp["exp"], bp["daily_exp"], bp.get("premium", 0), claimed, next_hourly_seconds)
    
    await call.message.answer(
        text,
        reply_markup=get_battlepass_menu(user_id, bp["level"], bp["exp"], bp["daily_exp"], bp.get("premium", 0), claimed, next_hourly_seconds)
    )

@router.callback_query(F.data.startswith("bp_claim_"))
async def battlepass_claim(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    level = int(call.data.replace("bp_claim_", ""))
    
    if await check_spam(user_id):
        await safe_answer(call, get_text(user_id, "spam_warning"), show_alert=True)
        return
    if not await check_access(bot, user_id, state, call=call):
        return
    
    result = claim_battlepass_reward_db(user_id, level, is_premium=False)
    
    if not result:
        result = claim_battlepass_reward_db(user_id, level, is_premium=True)
    
    if result:
        await safe_answer(call, f"✅ +{result['reward']} 🍬 за {result['level']} уровень!", show_alert=True)
        add_battlepass_exp_db(user_id, 5)
        
        bp = get_battlepass(user_id)
        import json
        claimed = json.loads(bp["claimed_rewards"])
        
        next_hourly_seconds = 0
        if bp.get("last_hourly_claim"):
            last_time = datetime.fromisoformat(bp["last_hourly_claim"])
            elapsed = (datetime.now() - last_time).total_seconds()
            if elapsed < 3600:
                next_hourly_seconds = int(3600 - elapsed)
        
        await call.message.edit_text(
            get_battlepass_info_text(user_id, bp["level"], bp["exp"], bp["daily_exp"], bp.get("premium", 0), claimed, next_hourly_seconds),
            reply_markup=get_battlepass_menu(user_id, bp["level"], bp["exp"], bp["daily_exp"], bp.get("premium", 0), claimed, next_hourly_seconds)
        )
    else:
        await safe_answer(call, "❌ Награда уже получена или уровень не достигнут!", show_alert=True)

@router.callback_query(F.data == "bp_hourly")
async def battlepass_hourly(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    
    if await check_spam(user_id):
        await safe_answer(call, get_text(user_id, "spam_warning"), show_alert=True)
        return
    if not await check_access(bot, user_id, state, call=call):
        return
    
    result = claim_hourly_exp_db(user_id)
    
    if result["status"] == "success":
        await safe_answer(call, f"✅ +{result['exp_gained']} XP!", show_alert=True)
        if result.get("leveled_up"):
            await call.message.answer(f"🎉 Поздравляем! Вы достигли {result['new_level']} уровня в боевом пропуске!")
        
        bp = get_battlepass(user_id)
        import json
        claimed = json.loads(bp["claimed_rewards"])
        
        next_hourly_seconds = 3600
        if bp.get("last_hourly_claim"):
            last_time = datetime.fromisoformat(bp["last_hourly_claim"])
            elapsed = (datetime.now() - last_time).total_seconds()
            if elapsed < 3600:
                next_hourly_seconds = int(3600 - elapsed)
        
        await call.message.edit_text(
            get_battlepass_info_text(user_id, bp["level"], bp["exp"], bp["daily_exp"], bp.get("premium", 0), claimed, next_hourly_seconds),
            reply_markup=get_battlepass_menu(user_id, bp["level"], bp["exp"], bp["daily_exp"], bp.get("premium", 0), claimed, next_hourly_seconds)
        )
    elif result["status"] == "cooldown":
        await safe_answer(call, f"⏰ Следующий бонус через {result['minutes_left']} минут!", show_alert=True)
    else:
        await safe_answer(call, "❌ Ошибка при получении бонуса", show_alert=True)

@router.callback_query(F.data == "bp_hourly_disabled")
async def battlepass_hourly_disabled(call: CallbackQuery, state: FSMContext, bot: Bot):
    await safe_answer(call, "⏰ Подождите немного перед следующим бонусом!", show_alert=True)

@router.callback_query(F.data == "bp_buy_premium")
async def battlepass_buy_premium(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    
    if await check_spam(user_id):
        await safe_answer(call, get_text(user_id, "spam_warning"), show_alert=True)
        return
    if not await check_access(bot, user_id, state, call=call):
        return
    
    bp = get_battlepass(user_id)
    if bp and bp.get("premium", 0):
        await call.message.answer("❌ У вас уже есть премиум пропуск!")
        return
    
    await call.message.answer(
        f"💎 <b>ПРЕМИУМ БОЕВОЙ ПРОПУСК</b>\n\n"
        f"Премиум пропуск даёт 130 🍬 за каждый уровень!\n"
        f"💰 Стоимость: {PREMIUM_PRICE_STARS} ⭐️ или ${PREMIUM_PRICE_USD}\n\n"
        f"Выберите способ оплаты:",
        reply_markup=get_battlepass_premium_menu(user_id)
    )

@router.callback_query(F.data == "bp_pay_stars")
async def battlepass_pay_stars(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    
    if await check_spam(user_id):
        await safe_answer(call, get_text(user_id, "spam_warning"), show_alert=True)
        return
    if not await check_access(bot, user_id, state, call=call):
        return
    
    from db import add_stars_payment_request_db
    request_id = add_stars_payment_request_db(user_id, "", 0, PREMIUM_PRICE_STARS, None)
    
    await state.update_data(pending_premium_request_id=request_id)
    
    await call.message.answer(
        f"⭐️ <b>ОПЛАТА ПРЕМИУМ ПРОПУСКА ЗВЕЗДАМИ</b>\n\n"
        f"Стоимость: {PREMIUM_PRICE_STARS} ⭐️\n\n"
        f"1. Перейдите по ссылке: {ANON_CHAT_LINK}\n"
        f"2. Нажмите на текст и отправьте его в сообщения:\n"
        f"<code>Хочу купить премиум боевой пропуск за {PREMIUM_PRICE_STARS} ⭐️\nмой id: {user_id}</code>\n"
        f"3. Оплатите ОБЫЧНЫМИ подарками\n"
        f"4. Ожидайте активации!\n\n"
        f"🔗 Ссылка: {ANON_CHAT_LINK}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⭐️ Перейти к оплате", url=ANON_CHAT_LINK)],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="bp_buy_premium")]
        ])
    )

@router.callback_query(F.data == "bp_pay_crypto")
async def battlepass_pay_crypto(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    
    if await check_spam(user_id):
        await safe_answer(call, get_text(user_id, "spam_warning"), show_alert=True)
        return
    if not await check_access(bot, user_id, state, call=call):
        return
    
    invoice = create_invoice(PREMIUM_PRICE_USD, "USDT", method="cryptobot")
    
    if not invoice or invoice.get("status") == "error":
        await call.message.answer("❌ Ошибка при создании платежа. Попробуйте позже.")
        return
    
    invoice_id = invoice["invoice_id"]
    crypto_amount = invoice.get("crypto_amount", PREMIUM_PRICE_USD)
    
    await state.update_data(pending_premium_invoice=invoice_id)
    
    await call.message.answer(
        f"💎 <b>ОПЛАТА ПРЕМИУМ ПРОПУСКА КРИПТОВАЛЮТОЙ</b>\n\n"
        f"💰 Сумма: ${PREMIUM_PRICE_USD}\n"
        f"💱 К оплате: {crypto_amount} USDT\n\n"
        f"🔗 Ссылка для оплаты:\n{invoice['pay_url']}\n\n"
        f"🔄 После оплаты нажмите \"Проверить оплату\"",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"💰 Оплатить {crypto_amount} USDT", url=invoice["pay_url"])],
            [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_premium_{invoice_id}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="bp_buy_premium")]
        ])
    )

@router.callback_query(F.data.startswith("check_premium_"))
async def check_premium_payment(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    
    if await check_spam(user_id):
        await safe_answer(call, get_text(user_id, "spam_warning"), show_alert=True)
        return
    if not await check_access(bot, user_id, state, call=call):
        return
    
    invoice_id = call.data.replace("check_premium_", "")
    
    result = check_invoice(invoice_id, method="cryptobot")
    
    if result.get("paid", False):
        if activate_premium_battlepass_payment(user_id):
            await safe_answer(call, "✅ Премиум пропуск активирован!", show_alert=True)
            await call.message.answer(
                f"🎉 <b>ПРЕМИУМ ПРОПУСК АКТИВИРОВАН!</b>\n\n"
                f"Теперь вы получаете 130 🍬 за каждый уровень!\n"
                f"Заберите свои награды в меню боевого пропуска."
            )
            
            bp = get_battlepass(user_id)
            import json
            claimed = json.loads(bp["claimed_rewards"])
            
            next_hourly_seconds = 0
            if bp.get("last_hourly_claim"):
                last_time = datetime.fromisoformat(bp["last_hourly_claim"])
                elapsed = (datetime.now() - last_time).total_seconds()
                if elapsed < 3600:
                    next_hourly_seconds = int(3600 - elapsed)
            
            await call.message.edit_text(
                get_battlepass_info_text(user_id, bp["level"], bp["exp"], bp["daily_exp"], 1, claimed, next_hourly_seconds),
                reply_markup=get_battlepass_menu(user_id, bp["level"], bp["exp"], bp["daily_exp"], 1, claimed, next_hourly_seconds)
            )
        else:
            await call.message.answer("❌ Ошибка при активации пропуска")
    else:
        await call.message.answer("⏳ Платёж ещё не оплачен")

@router.callback_query(F.data == "admin_give_battlepass")
async def admin_give_battlepass(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    if not check_admin_access(user_id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    await safe_answer(call)
    await state.set_state(AdminStates.waiting_for_user_info)
    await call.message.answer("👤 Введите ID пользователя для выдачи премиум пропуска:")

@router.message(AdminStates.waiting_for_user_info)
async def admin_give_battlepass_user(message: Message, state: FSMContext, bot: Bot):
    admin_id = message.from_user.id
    if not check_admin_access(admin_id)[0]:
        return
    
    try:
        target_user_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите корректный ID пользователя (число)")
        return
    
    cursor.execute("SELECT user_id, username FROM users WHERE user_id = ?", (target_user_id,))
    user = cursor.fetchone()
    
    if not user:
        await message.answer(f"❌ Пользователь с ID {target_user_id} не найден")
        await state.clear()
        return
    
    if activate_premium_battlepass_db(target_user_id):
        await message.answer(
            f"✅ Премиум пропуск выдан пользователю @{user['username'] or 'нет username'} (ID: {target_user_id})!\n\n"
            f"Теперь он получает 130 🍬 за каждый уровень боевого пропуска."
        )
        
        try:
            await bot.send_message(
                target_user_id,
                f"🎉 <b>Вам выдан премиум боевой пропуск!</b>\n\n"
                f"Теперь вы получаете 130 🍬 за каждый уровень!\n"
                f"Заберите свои награды в меню боевого пропуска."
            )
        except:
            pass
    else:
        await message.answer("❌ Ошибка при выдаче пропуска")
    
    await state.clear()

@router.callback_query(F.data == "shop")
async def shop(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    if await check_spam(user_id):
        await safe_answer(call, get_text(user_id, "spam_warning"), show_alert=True)
        return
    if not await check_access(bot, user_id, state, call=call):
        return
    
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    balance = user["balance"] if user else 0
    
    await call.message.answer(
        f"{get_text(user_id, 'candy_shop')}\n\n"
        f"{get_text(user_id, 'your_balance').format(balance)}\n"
        f"{get_text(user_id, 'exchange_rate_info')}\n\n"
        f"{get_text(user_id, 'choose_pack')}",
        reply_markup=get_shop_menu(balance)
    )

@router.callback_query(F.data.startswith("buy_pack_"))
async def buy_pack(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    if await check_spam(user_id):
        await safe_answer(call, get_text(user_id, "spam_warning"), show_alert=True)
        return
    if not await check_access(bot, user_id, state, call=call):
        return
    
    pack_amount = int(call.data.replace("buy_pack_", ""))
    pack_info = CANDY_PACKS.get(pack_amount)
    
    if not pack_info:
        await safe_answer(call, get_text(user_id, "pack_not_found"), show_alert=True)
        return
    
    usd_amount = pack_info["usd"]
    stars_amount = pack_info["stars"]
    
    await state.update_data(pending_pack=pack_amount, pending_usd=usd_amount, pending_stars=stars_amount)
    
    await call.message.answer(
        f"{get_text(user_id, 'selected_candies').format(pack_amount)}\n\n"
        f"{get_text(user_id, 'choose_payment')}",
        reply_markup=get_payment_methods_menu(pack_amount, usd_amount, stars_amount)
    )

@router.callback_query(F.data.startswith("pay_method_"))
async def select_payment_method(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    if await check_spam(user_id):
        await safe_answer(call, get_text(user_id, "spam_warning"), show_alert=True)
        return
    if not await check_access(bot, user_id, state, call=call):
        return
    
    parts = call.data.split("_")
    method = parts[2]
    pack_amount = int(parts[3])
    
    if method == "card":
        if pack_amount != 180:
            await call.message.answer(get_text(user_id, "pack_not_found"))
            return
        
        await call.message.answer(
            f"💳 <b>ОПЛАТА ПО КАРТЕ</b>\n\n"
            f"Сумма: 180 ₽ 💸\n"
            f"Вы получите: 180 🍬\n\n"
            f"1. Перейдите по ссылке: {ANON_CHAT_LINK}\n"
            f"2. Напишите: Хочу купить 180 🍬 за 180 ₽\n"
            f"3. Укажите ваш ID: <code>{user_id}</code>\n"
            f"4. Оплатите переводом, по карте которую вам скинут.\n"
            f"5. Ожидайте зачисления!\n\n"
            f"🔗 Ссылка: {ANON_CHAT_LINK}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Перейти к оплате", url=ANON_CHAT_LINK)],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="shop")]
            ])
        )
        return
    
    if method == "sbp":
        if not LOLZ_AVAILABLE:
            await call.message.answer("❌ Оплата через СБП временно недоступна")
            return
        usd_amount = float(parts[4])
        
        pack_info = CANDY_PACKS.get(pack_amount)
        if not pack_info:
            await safe_answer(call, get_text(user_id, "pack_not_found"), show_alert=True)
            return
        
        rub_amount = usd_amount * 95
        order_id = f"candy_{user_id}_{int(time.time())}"
        
        cursor.execute("SELECT username FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        username = user["username"] if user else "user"
        
        invoice = create_lolz_invoice(rub_amount, order_id, user_id, username)
        
        if not invoice or invoice.get("status") != "success":
            await call.message.answer("❌ Ошибка при создании платежа. Попробуйте позже.")
            return
        
        add_lolz_payment(invoice.get("invoice_id", order_id), order_id, user_id, rub_amount, pack_amount)
        
        await state.update_data(pending_sbp_order=order_id, pending_sbp_pack=pack_amount)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"🏦 Оплатить через Lolz", url=invoice["pay_url"])],
            [InlineKeyboardButton(text=get_text(user_id, "check_payment"), callback_data=f"check_sbp_{order_id}_{pack_amount}")],
            [InlineKeyboardButton(text=get_text(user_id, "back"), callback_data=f"back_to_payment_methods_{pack_amount}_{usd_amount}")]
        ])
        
        await call.message.answer(
            f"🏦 <b>ОПЛАТА ЧЕРЕЗ Lolz Market (СБП)</b>\n\n"
            f"🍬 Конфет: {pack_amount}\n"
            f"💰 Сумма: {rub_amount} RUB\n\n"
            f"🔗 Ссылка для оплаты:\n{invoice['pay_url']}\n\n"
            f"📱 {get_text(user_id, 'check_payment')}\n\n"
            f"⏳ Счет действителен 1 час",
            reply_markup=keyboard
        )
        return
    
    if method == "stars":
        stars_amount = int(parts[4])
        await call.message.answer(
            f"⭐️ <b>ОПЛАТА ЗВЕЗДАМИ</b>\n\n"
            f"Сумма: {stars_amount} ⭐️\n"
            f"Вы получите: {pack_amount} 🍬\n\n"
            f"1. Перейдите по ссылке: {ANON_CHAT_LINK}\n"
            f"2. Нажмите на текст и отправьте его в сообщения:\n"
            f"<code>Хочу купить {pack_amount} 🍬 за {stars_amount} ⭐️\nмой id: {user_id}</code>\n"
            f"3. Оплатите ОБЫЧНЫМИ подарками\n"
            f"4. Ожидайте зачисления!\n\n"
            f"🔗 Ссылка: {ANON_CHAT_LINK}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⭐️ Перейти к оплате", url=ANON_CHAT_LINK)],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"back_to_payment_methods_{pack_amount}")]
            ])
        )
        return
    
    if method in ["cryptobot", "xrocket"]:
        usd_amount = float(parts[4])
        await state.update_data(pending_method=method, pending_pack=pack_amount, pending_usd=usd_amount)
        
        await call.message.answer(
            f"💎 <b>ВЫБЕРИТЕ ВАЛЮТУ ДЛЯ ОПЛАТЫ</b>\n\n"
            f"🍬 Вы выбрали пак конфет: {pack_amount} 🍬\n\n"
            f"Выберите валюту:",
            reply_markup=get_crypto_currency_menu(pack_amount, usd_amount, method)
        )

@router.callback_query(F.data.startswith("check_sbp_"))
async def check_sbp_payment(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    if await check_spam(user_id):
        await safe_answer(call, get_text(user_id, "spam_warning"), show_alert=True)
        return
    if not await check_access(bot, user_id, state, call=call):
        return
    
    parts = call.data.split("_")
    order_id = parts[2]
    pack_amount = int(parts[3])
    
    await call.message.answer(
        f"🔄 <b>ПРОВЕРКА ОПЛАТЫ</b>\n\n"
        f"Если вы уже оплатили счет, подождите несколько минут и нажмите кнопку снова.\n\n"
        f"Если оплата не прошла:\n"
        f"1. Убедитесь, что вы перевели точную сумму\n"
        f"2. Попробуйте оплатить снова\n"
        f"3. Обратитесь в поддержку\n\n"
        f"После подтверждения оплаты конфеты будут зачислены автоматически."
    )

@router.callback_query(F.data.startswith("cryptobot_asset_"))
async def cryptobot_asset_selected(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    if await check_spam(user_id):
        await safe_answer(call, get_text(user_id, "spam_warning"), show_alert=True)
        return
    if not await check_access(bot, user_id, state, call=call):
        return
    
    parts = call.data.split("_")
    pack_amount = int(parts[2])
    usd_amount = float(parts[3])
    asset = parts[4]
    
    invoice = create_invoice(usd_amount, asset, method="cryptobot")
    
    if not invoice or invoice.get("status") == "error":
        await call.message.answer("❌ Ошибка при создании платежа. Попробуйте позже.")
        return
    
    invoice_id = invoice["invoice_id"]
    crypto_amount = invoice.get("crypto_amount", usd_amount)
    
    pending_invoices[invoice_id] = {
        "user_id": user_id,
        "pack_amount": pack_amount,
        "usd_amount": usd_amount,
        "asset": asset,
        "method": "cryptobot"
    }
    
    cursor.execute(
        "INSERT INTO payments (invoice_id, user_id, amount, paid) VALUES (?, ?, ?, 0)",
        (invoice_id, user_id, pack_amount)
    )
    conn.commit()
    
    add_battlepass_exp_db(user_id, pack_amount // 10)
    
    await call.message.answer(
        f"💳 <b>ОПЛАТА ЧЕРЕЗ CRYPTOBOT</b>\n\n"
        f"🍬 Конфет: {pack_amount}\n"
        f"💱 Валюта: {asset}\n\n"
        f"💰 К оплате: {crypto_amount} {asset}\n\n"
        f"🔗 Ссылка для оплаты:\n{invoice['pay_url']}\n\n"
        f"🔄 {get_text(user_id, 'check_payment')}",
        reply_markup=get_invoice_payment_menu(invoice['pay_url'], invoice_id, "cryptobot", pack_amount, crypto_amount, asset)
    )

@router.callback_query(F.data.startswith("xrocket_asset_"))
async def xrocket_asset_selected(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    if await check_spam(user_id):
        await safe_answer(call, get_text(user_id, "spam_warning"), show_alert=True)
        return
    if not await check_access(bot, user_id, state, call=call):
        return
    
    parts = call.data.split("_")
    pack_amount = int(parts[2])
    usd_amount = float(parts[3])
    asset = parts[4]
    
    invoice = create_invoice(usd_amount, asset, method="xrocket")
    
    if not invoice or invoice.get("status") == "error":
        await call.message.answer("❌ Ошибка при создании платежа. Попробуйте позже.")
        return
    
    invoice_id = invoice["invoice_id"]
    crypto_amount = invoice.get("crypto_amount", usd_amount)
    
    pending_invoices[invoice_id] = {
        "user_id": user_id,
        "pack_amount": pack_amount,
        "usd_amount": usd_amount,
        "asset": asset,
        "method": "xrocket"
    }
    
    cursor.execute(
        "INSERT INTO payments (invoice_id, user_id, amount, paid) VALUES (?, ?, ?, 0)",
        (invoice_id, user_id, pack_amount)
    )
    conn.commit()
    
    add_battlepass_exp_db(user_id, pack_amount // 10)
    
    await call.message.answer(
        f"💎 <b>ОПЛАТА ЧЕРЕЗ XROCKET</b>\n\n"
        f"🍬 Конфет: {pack_amount}\n"
        f"💱 Валюта: {asset}\n\n"
        f"💰 К оплате: {crypto_amount} {asset}\n\n"
        f"🔗 Ссылка для оплаты:\n{invoice['pay_url']}\n\n"
        f"🔄 {get_text(user_id, 'check_payment')}",
        reply_markup=get_invoice_payment_menu(invoice['pay_url'], invoice_id, "xrocket", pack_amount, crypto_amount, asset)
    )

@router.callback_query(F.data.startswith("check_cryptobot_"))
async def check_cryptobot_payment(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    if await check_spam(user_id):
        await safe_answer(call, get_text(user_id, "spam_warning"), show_alert=True)
        return
    if not await check_access(bot, user_id, state, call=call):
        return
    
    parts = call.data.split("_")
    invoice_id = parts[2]
    pack_amount = int(parts[3])
    
    result = check_invoice(invoice_id, method="cryptobot")
    
    if result.get("paid", False):
        cursor.execute("SELECT paid FROM payments WHERE invoice_id = ?", (invoice_id,))
        payment = cursor.fetchone()
        if payment and payment["paid"] == 1:
            await call.message.answer("✅ Этот платёж уже был обработан")
            return
        
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (pack_amount, user_id))
        cursor.execute("UPDATE payments SET paid = 1 WHERE invoice_id = ?", (invoice_id,))
        add_battlepass_exp_db(user_id, pack_amount // 10)
        
        cursor.execute("SELECT referrer FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        if user and user["referrer"]:
            ref_bonus = int(pack_amount * REF_PERCENT / 100)
            if ref_bonus > 0:
                cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (ref_bonus, user["referrer"]))
                try:
                    await bot.send_message(
                        user["referrer"],
                        f"💰 Ваш реферал купил {pack_amount} 🍬\n"
                        f"➕ Вы получили {ref_bonus} 🍬 ({REF_PERCENT}%)"
                    )
                except:
                    pass
        
        conn.commit()
        
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        new_balance = cursor.fetchone()["balance"]
        
        await call.message.answer(
            f"✅ <b>ОПЛАТА ПОДТВЕРЖДЕНА!</b>\n\n"
            f"🍬 Начислено: +{pack_amount} конфет\n"
            f"💰 Текущий баланс: {new_balance} 🍬\n\n"
            f"Спасибо за покупку! 🎉"
        )
        await call.message.delete()
    else:
        await call.message.answer("⏳ Платёж ещё не оплачен\n\nПожалуйста, оплатите счет и нажмите \"Проверить оплату\" снова.")

@router.callback_query(F.data.startswith("check_xrocket_"))
async def check_xrocket_payment(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    if await check_spam(user_id):
        await safe_answer(call, get_text(user_id, "spam_warning"), show_alert=True)
        return
    if not await check_access(bot, user_id, state, call=call):
        return
    
    parts = call.data.split("_")
    invoice_id = parts[2]
    pack_amount = int(parts[3])
    
    result = check_invoice(invoice_id, method="xrocket")
    
    if result.get("paid", False):
        cursor.execute("SELECT paid FROM payments WHERE invoice_id = ?", (invoice_id,))
        payment = cursor.fetchone()
        if payment and payment["paid"] == 1:
            await call.message.answer("✅ Этот платёж уже был обработан")
            return
        
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (pack_amount, user_id))
        cursor.execute("UPDATE payments SET paid = 1 WHERE invoice_id = ?", (invoice_id,))
        add_battlepass_exp_db(user_id, pack_amount // 10)
        
        cursor.execute("SELECT referrer FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        if user and user["referrer"]:
            ref_bonus = int(pack_amount * REF_PERCENT / 100)
            if ref_bonus > 0:
                cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (ref_bonus, user["referrer"]))
                try:
                    await bot.send_message(
                        user["referrer"],
                        f"💰 Ваш реферал купил {pack_amount} 🍬\n"
                        f"➕ Вы получили {ref_bonus} 🍬 ({REF_PERCENT}%)"
                    )
                except:
                    pass
        
        conn.commit()
        
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        new_balance = cursor.fetchone()["balance"]
        
        await call.message.answer(
            f"✅ <b>ОПЛАТА ПОДТВЕРЖДЕНА!</b>\n\n"
            f"🍬 Начислено: +{pack_amount} конфет\n"
            f"💰 Текущий баланс: {new_balance} 🍬\n\n"
            f"Спасибо за покупку! 🎉"
        )
        await call.message.delete()
    else:
        await call.message.answer("⏳ Платёж ещё не оплачен\n\nПожалуйста, оплатите счет и нажмите \"Проверить оплату\" снова.")

@router.callback_query(F.data.startswith("back_to_payment_methods_"))
async def back_to_payment_methods(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    if await check_spam(user_id):
        await safe_answer(call, get_text(user_id, "spam_warning"), show_alert=True)
        return
    if not await check_access(bot, user_id, state, call=call):
        return
    
    parts = call.data.split("_")
    
    if len(parts) >= 5:
        pack_amount = int(parts[4])
        if len(parts) >= 6:
            usd_amount = float(parts[5])
        else:
            usd_amount = CANDY_PACKS.get(pack_amount, {}).get("usd", 0)
    else:
        pack_amount = 35
        usd_amount = CANDY_PACKS.get(pack_amount, {}).get("usd", 0.30)
    
    pack_info = CANDY_PACKS.get(pack_amount)
    stars_amount = pack_info["stars"] if pack_info else 0
    
    await call.message.edit_text(
        f"{get_text(user_id, 'selected_candies').format(pack_amount)}\n\n"
        f"{get_text(user_id, 'choose_payment')}",
        reply_markup=get_payment_methods_menu(pack_amount, usd_amount, stars_amount)
    )

@router.callback_query(F.data == "subscriptions_menu")
async def subscriptions_menu_handler(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    if await check_spam(user_id):
        await safe_answer(call, get_text(user_id, "spam_warning"), show_alert=True)
        return
    if not await check_access(bot, user_id, state, call=call):
        return
    text = (
        f"{get_text(user_id, 'subscriptions')}\n\n"
        f"{SUBSCRIPTIONS['op']['name']} дает:\n{SUBSCRIPTIONS['op']['benefits']}\n\n"
        f"{SUBSCRIPTIONS['base']['name']} дает:\n{SUBSCRIPTIONS['base']['benefits']}\n\n"
        f"{SUBSCRIPTIONS['newbie']['name']} дает:\n{SUBSCRIPTIONS['newbie']['benefits']}\n\n"
        f"💰 Цены:\n"
        f"{SUBSCRIPTIONS['op']['name']}: {SUBSCRIPTIONS['op']['stars']}⭐️ / {SUBSCRIPTIONS['op']['usd']}$\n"
        f"{SUBSCRIPTIONS['base']['name']}: {SUBSCRIPTIONS['base']['stars']}⭐️ / {SUBSCRIPTIONS['base']['usd']}$\n"
        f"{SUBSCRIPTIONS['newbie']['name']}: {SUBSCRIPTIONS['newbie']['stars']}⭐️ / {SUBSCRIPTIONS['newbie']['usd']}$"
    )
    await call.message.answer(text, reply_markup=subscriptions_menu)

@router.callback_query(F.data.startswith("buy_subscription_"))
async def buy_subscription(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    sub_type = call.data.replace("buy_subscription_", "")
    if await check_spam(user_id):
        await safe_answer(call, get_text(user_id, "spam_warning"), show_alert=True)
        return
    if not await check_access(bot, user_id, state, call=call):
        return
    sub = SUBSCRIPTIONS.get(sub_type)
    if not sub:
        await safe_answer(call, get_text(user_id, "pack_not_found"), show_alert=True)
        return
    await safe_answer(call)
    await state.update_data(pending_subscription_type=sub_type)
    sorted_assets = ["USDT", "TON"] + [a for a in AVAILABLE_ASSETS if a not in ["USDT", "TON"]]
    keyboard = []
    row = []
    for i, asset in enumerate(sorted_assets):
        icon = get_asset_icon(asset)
        row.append(InlineKeyboardButton(text=f"{icon} {asset}", callback_data=f"pay_subscription_asset_{sub_type}_{asset}"))
        if (i + 1) % 2 == 0:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton(text="⭐️ Оплатить звездами", callback_data=f"pay_subscription_stars_{sub_type}")])
    keyboard.append([InlineKeyboardButton(text=get_text(user_id, "back"), callback_data="subscriptions_menu")])
    await call.message.answer(
        f"{get_text(user_id, 'buy_subscription')}\n\n"
        f"{sub['name']}\n"
        f"{get_text(user_id, 'price').format(sub['stars'], sub['usd'])}\n\n"
        f"{get_text(user_id, 'duration').format(sub['days'])}\n\n"
        f"💳 Выберите способ оплаты:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@router.callback_query(F.data.startswith("pay_subscription_asset_"))
async def pay_subscription_asset(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    parts = call.data.split("_")
    sub_type = parts[3]
    asset = parts[4]
    if not await check_access(bot, user_id, state, call=call):
        return
    sub = SUBSCRIPTIONS.get(sub_type)
    if not sub:
        await safe_answer(call, get_text(user_id, "pack_not_found"), show_alert=True)
        return
    await safe_answer(call)
    try:
        invoice = create_invoice(sub["usd"], asset, method="cryptobot")
    except Exception as e:
        logger.error(f"❌ Ошибка создания счета: {e}")
        await call.message.answer("❌ Ошибка при создании платежа")
        return
    crypto_amount = invoice.get("crypto_amount", sub["usd"])
    rate = invoice.get("rate", "")
    cursor.execute("INSERT INTO payments (invoice_id, user_id, amount, paid) VALUES (?, ?, ?, 0)", (invoice["invoice_id"], user_id, sub["usd"]))
    conn.commit()
    await state.update_data(pending_subscription=sub_type)
    rate_text = f"\n💰 К оплате: {crypto_amount} {asset}"
    if rate:
        rate_text = f"\n1 {asset} = ${rate}\n💰 К оплате: {crypto_amount} {asset}"
    icon = get_asset_icon(asset)
    await call.message.answer(
        f"💳 <b>Оплата подписки в {icon} {asset}</b>\n\n"
        f"{sub['name']}\n"
        f"💰 Сумма: ${sub['usd']}{rate_text}\n\n"
        f"🔄 После оплаты подписка активируется автоматически",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"💰 Оплатить {crypto_amount} {asset}", url=invoice["pay_url"])],
            [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_subscription_{invoice['invoice_id']}")]
        ])
    )

@router.callback_query(F.data.startswith("pay_subscription_stars_"))
async def pay_subscription_stars(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    sub_type = call.data.replace("pay_subscription_stars_", "")
    if not await check_access(bot, user_id, state, call=call):
        return
    sub = SUBSCRIPTIONS.get(sub_type)
    if not sub:
        await safe_answer(call, get_text(user_id, "pack_not_found"), show_alert=True)
        return
    
    sub_texts = {
        "op": f"💎 {sub['name']}",
        "base": f"🚀 {sub['name']}",
        "newbie": f"😊 {sub['name']}"
    }
    
    await safe_answer(call)
    await call.message.answer(
        f"⭐️ <b>ОПЛАТА ЗВЕЗДАМИ</b>\n\n"
        f"Для покупки {sub_texts.get(sub_type, sub['name'])}:\n\n"
        f"1. Перейдите по ссылке: {ANON_CHAT_LINK}\n"
        f"2. Нажмите на текст и отправьте его в сообщения:\n"
        f"<code>Хочу купить {sub_texts.get(sub_type, sub['name'])} за {sub['stars']} ⭐️\nмой id: {user_id}</code>\n"
        f"3. Оплатите ОБЫЧНЫМИ подарками\n"
        f"4. Ожидайте активации!\n\n"
        f"🔗 Ссылка: {ANON_CHAT_LINK}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⭐️ Перейти к оплате", url=ANON_CHAT_LINK)],
            [InlineKeyboardButton(text=get_text(user_id, "back"), callback_data="subscriptions_menu")]
        ])
    )

@router.callback_query(F.data.startswith("check_subscription_"))
async def check_subscription_payment(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    if not await check_access(bot, user_id, state, call=call):
        return
    invoice_id = call.data.replace("check_subscription_", "")
    cursor.execute("SELECT user_id, amount, paid FROM payments WHERE invoice_id = ?", (invoice_id,))
    row = cursor.fetchone()
    if not row:
        await call.message.answer("❌ Платёж не найден")
        return
    result = check_invoice(invoice_id, method="cryptobot")
    if result.get("paid", False):
        if row["paid"] == 1:
            await call.message.answer("✅ Этот платёж уже был обработан")
            return
        cursor.execute("UPDATE payments SET paid = 1 WHERE invoice_id = ?", (invoice_id,))
        data = await state.get_data()
        sub_type = data.get("pending_subscription", "base")
        sub = SUBSCRIPTIONS.get(sub_type, SUBSCRIPTIONS["base"])
        if add_subscription(user_id, sub_type, sub["days"]):
            await call.message.answer(
                f"✅ <b>Подписка активирована!</b>\n\n"
                f"{sub['name']}\n"
                f"📅 Действует {sub['days']} дней\n\n"
                f"🎉 Поздравляем!"
            )
        else:
            await call.message.answer("❌ Ошибка активации подписки")
        await state.update_data(pending_subscription=None)
        conn.commit()
    else:
        await call.message.answer("⏳ Платёж ещё не оплачен")

@router.callback_query(F.data == "buy_private")
async def buy_private(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    if await check_spam(user_id):
        await safe_answer(call, get_text(user_id, "spam_warning"), show_alert=True)
        return
    if not await check_access(bot, user_id, state, call=call):
        return
    await safe_answer(call)
    await call.message.answer(
        f"{get_text(user_id, 'buy_private')}\n\n"
        f"{get_text(user_id, 'private_price').format(PRIVATE_PRICE_STARS, PRIVATE_PRICE_USD)}\n\n"
        f"{get_text(user_id, 'private_benefits')}\n\n"
        f"💳 Выберите способ оплаты:",
        reply_markup=private_pay_menu
    )

@router.callback_query(F.data == "private_crypto")
async def private_crypto(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    if not await check_access(bot, user_id, state, call=call):
        return
    await safe_answer(call)
    await call.message.answer(
        f"💎 <b>ВЫБЕРИТЕ ВАЛЮТУ ДЛЯ ОПЛАТЫ ПРИВАТКИ</b>\n\n"
        f"💰 Сумма: ${PRIVATE_PRICE_USD}\n\n"
        f"Выберите валюту:",
        reply_markup=get_private_crypto_menu(AVAILABLE_ASSETS)
    )

@router.callback_query(F.data.startswith("private_asset_"))
async def private_asset_selected(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    if not await check_access(bot, user_id, state, call=call):
        return
    asset = call.data.replace("private_asset_", "")
    invoice = create_invoice(PRIVATE_PRICE_USD, asset, method="cryptobot")
    if not invoice or invoice.get("status") == "error":
        await call.message.answer("❌ Ошибка при создании платежа. Попробуйте позже.")
        return
    invoice_id = invoice["invoice_id"]
    crypto_amount = invoice.get("crypto_amount", PRIVATE_PRICE_USD)
    rate = invoice.get("rate", "")
    add_private_purchase(user_id, invoice_id, PRIVATE_PRICE_USD)
    rate_text = f"\n💰 К оплате: {crypto_amount} {asset}"
    if rate:
        rate_text = f"\n1 {asset} = ${rate}\n💰 К оплате: {crypto_amount} {asset}"
    icon = get_asset_icon(asset)
    await call.message.answer(
        f"💳 <b>Оплата приватки в {icon} {asset}</b>\n\n"
        f"💰 Сумма: ${PRIVATE_PRICE_USD}{rate_text}\n\n"
        f"🔄 После оплаты доступ откроется автоматически",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"💰 Оплатить {crypto_amount} {asset}", url=invoice["pay_url"])],
            [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_private_{invoice_id}")]
        ])
    )

@router.callback_query(F.data == "private_stars")
async def private_pay_stars(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    if not await check_access(bot, user_id, state, call=call):
        return
    await safe_answer(call)
    await call.message.answer(
        f"⭐️ <b>ОПЛАТА ЗВЕЗДАМИ</b>\n\n"
        f"Для получения доступа к приватке:\n\n"
        f"1. Перейдите по ссылке: {ANON_CHAT_LINK}\n"
        f"2. Нажмите на текст и отправьте его в сообщения:\n"
        f"<code>Хочу купить приватку за {PRIVATE_PRICE_STARS} ⭐️\nмой id: {user_id}</code>\n"
        f"3. Оплатите ОБЫЧНЫМИ подарками\n"
        f"4. Ожидайте доступа!\n\n"
        f"🔗 Ссылка: {ANON_CHAT_LINK}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⭐️ Перейти к оплате", url=ANON_CHAT_LINK)],
            [InlineKeyboardButton(text=get_text(user_id, "back"), callback_data="buy_private")]
        ])
    )

@router.callback_query(F.data.startswith("check_private_"))
async def check_private_payment(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    await safe_answer(call)
    if not await check_access(bot, user_id, state, call=call):
        return
    invoice_id = call.data.replace("check_private_", "")
    purchase = get_private_purchase(invoice_id)
    if not purchase:
        await call.message.answer("❌ Платёж не найден")
        return
    result = check_invoice(invoice_id, method="cryptobot")
    if result.get("paid", False):
        if purchase["paid"] == 1:
            await call.message.answer("✅ Доступ к приватке уже открыт!")
            return
        mark_private_paid(invoice_id)
        await call.message.answer(
            f"✅ <b>Оплата подтверждена!</b>\n\n"
            f"🔐 Доступ к приватке открыт!\n"
            f"🎉 Поздравляем!"
        )
    else:
        await call.message.answer("⏳ Платёж ещё не оплачен")

@router.callback_query(F.data == "tasks")
async def tasks_menu(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    if await check_spam(user_id):
        await safe_answer(call, get_text(user_id, "spam_warning"), show_alert=True)
        return
    if not await check_access(bot, user_id, state, call=call):
        return
    await safe_answer(call)
    await call.message.answer(
        "📋 <b>ВЫБЕРИТЕ КАТЕГОРИЮ ЗАДАНИЙ</b>\n\n"
        "Выполняйте задания и получайте КОНФЕТКИ! 🍬\n"
        "Снизу выбирай категорию, от сложности зависит лучше твоя награда, или хуже! 👇",
        reply_markup=get_categories_menu()
    )

@router.callback_query(F.data.startswith("tasks_category_"))
async def tasks_category(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    if await check_spam(user_id):
        await safe_answer(call, get_text(user_id, "spam_warning"), show_alert=True)
        return
    if not await check_access(bot, user_id, state, call=call):
        return
    
    category = call.data.replace("tasks_category_", "")
    await safe_answer(call)
    
    tasks = get_active_tasks_by_category(category)
    if not tasks:
        await call.message.answer(f"📭 В этой категории нет активных заданий")
        return
    
    user_tasks = []
    for task in tasks:
        status = get_user_task_status(user_id, task["id"])
        completed = get_user_completed_count(user_id, task["id"])
        task["completed"] = completed
        task["max_completions"] = task.get("max_completions", 1)
        task["status"] = status["status"] if status else None
        user_tasks.append(task)
    
    await call.message.answer(
        f"📋 <b>ЗАДАНИЯ</b>\n\n"
        f"Категория: {TASK_CATEGORIES.get(category, {}).get('name', category)}",
        reply_markup=get_tasks_menu_by_category(user_tasks, category)
    )

@router.callback_query(F.data.startswith("tasks_refresh_"))
async def tasks_refresh(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    if await check_spam(user_id):
        await safe_answer(call, get_text(user_id, "spam_warning"), show_alert=True)
        return
    if not await check_access(bot, user_id, state, call=call):
        return
    
    category = call.data.replace("tasks_refresh_", "")
    await safe_answer(call, "🔄 Обновляю список...")
    
    tasks = get_active_tasks_by_category(category)
    if not tasks:
        await call.message.edit_text(f"📭 В этой категории нет активных заданий")
        return
    
    user_tasks = []
    for task in tasks:
        status = get_user_task_status(user_id, task["id"])
        completed = get_user_completed_count(user_id, task["id"])
        task["completed"] = completed
        task["max_completions"] = task.get("max_completions", 1)
        task["status"] = status["status"] if status else None
        user_tasks.append(task)
    
    await call.message.edit_text(
        f"📋 <b>ЗАДАНИЯ</b>\n\n"
        f"Категория: {TASK_CATEGORIES.get(category, {}).get('name', category)}",
        reply_markup=get_tasks_menu_by_category(user_tasks, category)
    )

@router.callback_query(F.data.startswith("task_"))
async def task_detail(call: CallbackQuery, state: FSMContext, bot: Bot):
    if call.data.startswith("task_category_") or call.data.startswith("tasks_category_") or call.data.startswith("admin_task_category_"):
        return
    
    user_id = call.from_user.id
    if await check_spam(user_id):
        await safe_answer(call, get_text(user_id, "spam_warning"), show_alert=True)
        return
    if not await check_access(bot, user_id, state, call=call):
        return
    task_id = int(call.data.split("_")[1])
    task = get_task(task_id)
    if not task or not task["is_active"]:
        await safe_answer(call, "❌ Задание не найдено", show_alert=True)
        return
    status = get_user_task_status(user_id, task_id)
    task_status = status["status"] if status else None
    completed = get_user_completed_count(user_id, task_id)
    max_completions = task.get("max_completions", 1)
    
    text = (
        f"📋 <b>{task['title']}</b>\n\n"
        f"📝 {task['description']}\n\n"
        f"🎁 Награда: +{task['reward']} 🍬\n"
        f"📊 Выполнено: {completed} из {max_completions}\n\n"
        f"📸 Отправьте скриншот выполнения задания!"
    )
    
    if task_status == "pending":
        text += "\n⏳ Задание на проверке у администратора"
    elif task_status == "approved" and completed >= max_completions:
        text += "\n✅ Все выполнения завершены!"
    
    can_do = can_complete_task(user_id, task_id, max_completions)
    
    keyboard_buttons = []
    if can_do:
        keyboard_buttons.append([InlineKeyboardButton(text="📸 Отправить скриншот", callback_data=f"do_task_{task_id}")])
    keyboard_buttons.append([InlineKeyboardButton(text="⬅️ Назад к заданиям", callback_data="tasks")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    await call.message.answer(text, reply_markup=keyboard)

@router.callback_query(F.data.startswith("do_task_"))
async def do_task(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    if await check_spam(user_id):
        await safe_answer(call, get_text(user_id, "spam_warning"), show_alert=True)
        return
    if not await check_access(bot, user_id, state, call=call):
        return
    task_id = int(call.data.split("_")[2])
    task = get_task(task_id)
    if not task or not task["is_active"]:
        await safe_answer(call, "❌ Задание не найдено", show_alert=True)
        return
    
    max_completions = task.get("max_completions", 1)
    
    if not can_complete_task(user_id, task_id, max_completions):
        completed = get_user_completed_count(user_id, task_id)
        await safe_answer(call, f"❌ Вы уже выполнили это задание {completed} раз из {max_completions}", show_alert=True)
        return
    
    if max_completions == 1:
        existing_pending = get_user_task_status(user_id, task_id)
        if existing_pending and existing_pending.get("status") == "pending":
            await safe_answer(call, "⏳ У вас уже есть задание на проверке! Дождитесь результата.", show_alert=True)
            return
    
    await state.update_data(task_id=task_id)
    await state.set_state(TaskStates.waiting_for_task_photo)
    await safe_answer(call)
    await call.message.answer(
        f"📸 <b>Задание: {task['title']}</b>\n\n"
        f"{task['description']}\n\n"
        f"Отправьте скриншот выполнения задания:\n"
        f"(Выполнено: {get_user_completed_count(user_id, task_id)} из {max_completions})"
    )

@router.message(TaskStates.waiting_for_task_photo, F.photo)
async def submit_task_photo(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    photo = message.photo[-1]
    caption = message.caption or "Скриншот отправлен"
    data = await state.get_data()
    task_id = data.get("task_id")
    if not task_id:
        await state.clear()
        return
    task = get_task(task_id)
    if not task or not task["is_active"]:
        await message.answer("❌ Задание не найдено")
        await state.clear()
        return
    
    max_completions = task.get("max_completions", 1)
    
    if not can_complete_task(user_id, task_id, max_completions):
        completed = get_user_completed_count(user_id, task_id)
        await message.answer(f"❌ Вы уже выполнили это задание {completed} раз из {max_completions}. Больше нельзя!")
        await state.clear()
        return
    
    if max_completions == 1:
        existing_pending = get_user_task_status(user_id, task_id)
        if existing_pending and existing_pending.get("status") == "pending":
            await message.answer("⏳ У вас уже есть задание на проверке! Дождитесь результата.")
            await state.clear()
            return
    
    proof_text = f"Скриншот: {photo.file_id}\nОписание: {caption}"
    result = submit_task(user_id, task_id, proof_text)
    
    if result:
        completed_count = get_user_completed_count(user_id, task_id)
        await message.answer(
            f"✅ Задание отправлено на проверку!\n"
            f"📊 Выполнено: {completed_count} из {max_completions}"
        )
        
        admins = get_all_admins()
        for admin in admins:
            try:
                await bot.send_photo(
                    admin["user_id"],
                    photo=photo.file_id,
                    caption=(
                        f"📋 <b>НОВОЕ ЗАДАНИЕ НА ПРОВЕРКУ</b>\n\n"
                        f"👤 Пользователь: @{message.from_user.username or 'нет'}\n"
                        f"🆔 ID: {user_id}\n"
                        f"📝 Задание: {task['title']}\n"
                        f"🎁 Награда: +{task['reward']} 🍬\n"
                        f"📊 Макс. выполнений: {max_completions}\n"
                        f"📊 Выполнено раз: {get_user_completed_count(user_id, task_id)} из {max_completions}\n\n"
                        f"📄 Описание: {caption}"
                    ),
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [
                            InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_task_{task_id}_{user_id}"),
                            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_task_{task_id}_{user_id}")
                        ],
                        [InlineKeyboardButton(text="📝 Отправить на доработку", callback_data=f"rework_task_{task_id}_{user_id}")],
                        [InlineKeyboardButton(text="🗑 Удалить заявку", callback_data=f"admin_delete_request_{task_id}_{user_id}")]
                    ])
                )
            except Exception as e:
                print(f"Ошибка отправки админу: {e}")
        
        add_battlepass_exp_db(user_id, task["reward"] // 2)
    else:
        await message.answer("❌ Ошибка при отправке задания. Попробуйте позже.")
    
    await state.clear()

@router.message(TaskStates.waiting_for_task_photo)
async def task_photo_required(message: Message, state: FSMContext):
    await message.answer("❌ Для выполнения задания нужно отправить СКРИНШОТ (фото)!")

@router.callback_query(F.data.startswith("approve_task_"))
async def approve_task_admin(call: CallbackQuery, state: FSMContext, bot: Bot):
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    parts = call.data.split("_")
    task_id = int(parts[2])
    user_id = int(parts[3])
    task = get_task(task_id)
    if not task:
        await safe_answer(call, "❌ Задание не найдено", show_alert=True)
        return
    
    if approve_task(user_id, task_id, task["reward"]):
        completed = get_user_completed_count(user_id, task_id)
        max_completions = task.get("max_completions", 1)
        
        text = (
            f"✅ <b>Задание одобрено!</b>\n\n"
            f"🎁 Начислено на ваш баланс: +{task['reward']} 🍬\n"
            f"📊 Вы выполнили: {completed} из {max_completions}\n\n"
            f"Спасибо за выполнение, выполняйте больше заданий!"
        )
        
        await safe_answer(call, "✅ Задание одобрено!")
        try:
            await call.message.delete()
        except:
            pass
        try:
            await bot.send_message(user_id, text)
        except:
            pass
        
        add_battlepass_exp_db(user_id, task["reward"] // 2)
    else:
        await safe_answer(call, "❌ Ошибка при одобрении", show_alert=True)

@router.callback_query(F.data.startswith("reject_task_"))
async def reject_task_admin(call: CallbackQuery, state: FSMContext, bot: Bot):
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    parts = call.data.split("_")
    task_id = int(parts[2])
    user_id = int(parts[3])
    task = get_task(task_id)
    
    if reject_task(user_id, task_id):
        await safe_answer(call, "❌ Задание отклонено")
        try:
            await call.message.delete()
        except:
            pass
        try:
            await bot.send_message(
                user_id,
                f"❌ <b>Задание отклонено</b>\n\n"
                f"📋 {task['title']}\n\n"
                f"Ваше задание не прошло проверку.\n"
                f"Попробуйте выполнить его заново, следуя инструкциям."
            )
        except:
            pass
    else:
        await safe_answer(call, "❌ Ошибка при отклонении", show_alert=True)

@router.callback_query(F.data.startswith("rework_task_"))
async def rework_task_admin(call: CallbackQuery, state: FSMContext, bot: Bot):
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    parts = call.data.split("_")
    task_id = int(parts[2])
    user_id = int(parts[3])
    task = get_task(task_id)
    if not task:
        await safe_answer(call, "❌ Задание не найдено", show_alert=True)
        return
    
    await state.update_data(rework_user_id=user_id, rework_task_id=task_id, rework_task_title=task["title"])
    await state.set_state(AdminStates.waiting_for_rework_message)
    await safe_answer(call)
    await call.message.answer(
        f"✏️ <b>ОТПРАВКА НА ДОРАБОТКУ</b>\n\n"
        f"👤 Пользователь: {user_id}\n"
        f"📋 Задание: {task['title']}\n\n"
        f"Введите текст пояснения (что нужно исправить):"
    )

@router.message(AdminStates.waiting_for_rework_message)
async def send_rework_message(message: Message, state: FSMContext, bot: Bot):
    if not check_admin_access(message.from_user.id)[0]:
        return
    data = await state.get_data()
    user_id = data.get("rework_user_id")
    task_id = data.get("rework_task_id")
    task_title = data.get("rework_task_title")
    rework_text = message.text
    if not user_id or not task_id:
        await message.answer("❌ Ошибка: данные не найдены")
        await state.clear()
        return
    
    await state.update_data(rework_text=rework_text, rework_user_id=user_id, rework_task_id=task_id, rework_task_title=task_title)
    await state.set_state(AdminStates.waiting_for_rework_confirm)
    await message.answer(
        f"📝 <b>ПОДТВЕРЖДЕНИЕ ОТПРАВКИ НА ДОРАБОТКУ</b>\n\n"
        f"👤 Пользователь: {user_id}\n"
        f"📋 Задание: {task_title}\n\n"
        f"💬 Текст пояснения:\n{rework_text}\n\n"
        f"✅ Отправить пользователю?",
        reply_markup=rework_confirm_menu
    )

@router.callback_query(F.data == "confirm_rework")
async def confirm_rework(call: CallbackQuery, state: FSMContext, bot: Bot):
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    data = await state.get_data()
    user_id = data.get("rework_user_id")
    task_id = data.get("rework_task_id")
    task_title = data.get("rework_task_title")
    rework_text = data.get("rework_text")
    
    if not user_id or not task_id:
        await call.message.answer("❌ Ошибка: данные не найдены")
        await state.clear()
        return
    
    reject_task(user_id, task_id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Выполнить заново", callback_data=f"do_task_{task_id}")],
        [InlineKeyboardButton(text="❌ Отказаться от задания", callback_data=f"cancel_task_{task_id}")]
    ])
    try:
        await bot.send_message(
            user_id,
            f"📝 <b>Задание отправлено на доработку</b>\n\n"
            f"📋 <b>{task_title}</b>\n\n"
            f"💬 <b>Пояснение администратора:</b>\n{rework_text}\n\n"
            f"⚠️ Пожалуйста, исправьте задание и отправьте заново.",
            reply_markup=keyboard
        )
        await call.message.edit_text(f"✅ Сообщение отправлено пользователю {user_id}")
    except:
        pass
    await state.clear()

@router.callback_query(F.data == "cancel_rework")
async def cancel_rework(call: CallbackQuery, state: FSMContext, bot: Bot):
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    await state.clear()
    await call.message.edit_text("❌ Отправка на доработку отменена")

@router.callback_query(F.data.startswith("cancel_task_"))
async def cancel_task_by_user(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    task_id = int(call.data.split("_")[2])
    task = get_task(task_id)
    if not task:
        await safe_answer(call, "❌ Задание не найдено", show_alert=True)
        return
    
    reject_task(user_id, task_id)
    await safe_answer(call, "❌ Вы отказались от выполнения задания")
    try:
        await call.message.edit_text(
            f"❌ <b>Вы отказались от задания</b>\n\n"
            f"📋 {task['title']}\n\n"
            f"Вы можете выбрать другое задание в меню."
        )
    except:
        await call.message.answer(
            f"❌ <b>Вы отказались от задания</b>\n\n"
            f"📋 {task['title']}\n\n"
            f"Вы можете выбрать другое задание в меню."
        )

@router.callback_query(F.data == "admin_manage_requests")
async def admin_manage_requests(call: CallbackQuery, state: FSMContext):
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    await safe_answer(call)
    
    pending_tasks = get_pending_tasks()
    
    if not pending_tasks:
        await call.message.answer("📭 Нет заданий на проверке")
        return
    
    await call.message.answer(
        "🗑 <b>УПРАВЛЕНИЕ ЗАЯВКАМИ</b>\n\n"
        "Выберите заявку для управления:",
        reply_markup=get_requests_menu(pending_tasks)
    )

@router.callback_query(F.data.startswith("admin_view_request_"))
async def admin_view_request(call: CallbackQuery, state: FSMContext, bot: Bot):
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    record_id = int(call.data.replace("admin_view_request_", ""))
    record = get_task_record_by_id(record_id)
    
    if not record:
        await safe_answer(call, "❌ Заявка не найдена", show_alert=True)
        return
    
    text = (
        f"📋 <b>ДЕТАЛИ ЗАЯВКИ</b>\n\n"
        f"👤 Пользователь: @{record['username']} (ID: {record['user_id']})\n"
        f"📝 Задание: {record['title']}\n"
        f"🎁 Награда: +{record['reward']} 🍬\n"
        f"📊 Макс. выполнений: {record['max_completions']}\n"
        f"📅 Отправлено: {record['completed_at'][:19]}\n\n"
        f"📄 Доказательство:\n{record['proof']}"
    )
    
    if "Скриншот:" in record['proof']:
        file_id = record['proof'].split("Скриншот: ")[1].split("\n")[0]
        await bot.send_photo(
            call.from_user.id,
            photo=file_id,
            caption=text,
            reply_markup=get_request_action_menu(record_id, record['title'], record['username'], record['user_id'], record['task_id'], record['reward'], record['proof'])
        )
    else:
        await call.message.answer(
            text,
            reply_markup=get_request_action_menu(record_id, record['title'], record['username'], record['user_id'], record['task_id'], record['reward'], record['proof'])
        )

@router.callback_query(F.data.startswith("admin_approve_request_"))
async def admin_approve_request(call: CallbackQuery, state: FSMContext, bot: Bot):
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    parts = call.data.split("_")
    record_id = int(parts[3])
    user_id = int(parts[4])
    task_id = int(parts[5])
    reward = int(parts[6])
    
    task = get_task(task_id)
    if not task:
        await safe_answer(call, "❌ Задание не найдено", show_alert=True)
        return
    
    if approve_task(user_id, task_id, reward):
        completed = get_user_completed_count(user_id, task_id)
        max_completions = task.get("max_completions", 1)
        
        text = (
            f"✅ <b>Задание одобрено!</b>\n\n"
            f"🎁 Начислено на ваш баланс: +{reward} 🍬\n"
            f"📊 Вы выполнили: {completed} из {max_completions}\n\n"
            f"Спасибо за выполнение, выполняйте больше заданий!"
        )
        
        await safe_answer(call, "✅ Задание одобрено!")
        await call.message.delete()
        try:
            await bot.send_message(user_id, text)
        except:
            pass
    else:
        await safe_answer(call, "❌ Ошибка при одобрении", show_alert=True)

@router.callback_query(F.data.startswith("admin_reject_request_"))
async def admin_reject_request(call: CallbackQuery, state: FSMContext, bot: Bot):
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    parts = call.data.split("_")
    record_id = int(parts[3])
    user_id = int(parts[4])
    task_id = int(parts[5])
    
    task = get_task(task_id)
    if reject_task(user_id, task_id):
        await safe_answer(call, "❌ Задание отклонено")
        await call.message.delete()
        try:
            await bot.send_message(
                user_id,
                f"❌ <b>Задание отклонено</b>\n\n"
                f"📋 {task['title']}\n\n"
                f"Ваше задание не прошло проверку.\n"
                f"Попробуйте выполнить его заново, следуя инструкциям."
            )
        except:
            pass
    else:
        await safe_answer(call, "❌ Ошибка при отклонении", show_alert=True)

@router.callback_query(F.data.startswith("admin_rework_request_"))
async def admin_rework_request(call: CallbackQuery, state: FSMContext, bot: Bot):
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    parts = call.data.split("_")
    record_id = int(parts[3])
    user_id = int(parts[4])
    task_id = int(parts[5])
    
    task = get_task(task_id)
    if not task:
        await safe_answer(call, "❌ Задание не найдено", show_alert=True)
        return
    
    await state.update_data(rework_user_id=user_id, rework_task_id=task_id, rework_task_title=task["title"])
    await state.set_state(AdminStates.waiting_for_rework_message)
    await safe_answer(call)
    await call.message.answer(
        f"✏️ <b>ОТПРАВКА НА ДОРАБОТКУ</b>\n\n"
        f"👤 Пользователь: {user_id}\n"
        f"📋 Задание: {task['title']}\n\n"
        f"Введите текст пояснения (что нужно исправить):"
    )

@router.callback_query(F.data.startswith("admin_delete_request_"))
async def admin_delete_request(call: CallbackQuery, state: FSMContext, bot: Bot):
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    parts = call.data.split("_")
    record_id = int(parts[3])
    user_id = int(parts[4])
    task_id = int(parts[5])
    
    records = get_user_task_records(user_id, task_id)
    
    if not records:
        await safe_answer(call, "❌ Нет записей для удаления", show_alert=True)
        return
    
    keyboard = []
    for record in records:
        status_emoji = "⏳" if record["status"] == "pending" else "✅" if record["status"] == "approved" else "❌"
        date_str = record["completed_at"][:16] if record["completed_at"] else "без даты"
        keyboard.append([InlineKeyboardButton(
            text=f"{status_emoji} {date_str} - {record['status']}",
            callback_data=f"delete_specific_record_{record['id']}"
        )])
    keyboard.append([InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_manage_requests")])
    
    await call.message.answer(
        f"🗑 <b>Удаление заявок</b>\n\n"
        f"👤 Пользователь: {user_id}\n"
        f"📋 Задание: {get_task(task_id)['title'] if get_task(task_id) else task_id}\n\n"
        f"Выберите заявку для удаления:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await call.message.delete()

@router.callback_query(F.data.startswith("delete_specific_record_"))
async def delete_specific_record(call: CallbackQuery, state: FSMContext, bot: Bot):
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    record_id = int(call.data.replace("delete_specific_record_", ""))
    
    if delete_task_record_by_id(record_id):
        await safe_answer(call, "✅ Заявка удалена!", show_alert=True)
        await call.message.edit_text("✅ Заявка успешно удалена")
    else:
        await safe_answer(call, "❌ Ошибка при удалении", show_alert=True)

@router.callback_query(F.data == "admin_tasks")
async def admin_tasks_menu_handler(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    has_access, _, is_main, can_manage = check_admin_access(user_id)
    if not has_access:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    await safe_answer(call)
    
    await call.message.answer(
        "📋 <b>УПРАВЛЕНИЕ ЗАДАНИЯМИ</b>\n\n"
        "Выберите действие:",
        reply_markup=admin_tasks_keyboard
    )

@router.callback_query(F.data == "admin_task_categories")
async def admin_task_categories(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    if not check_admin_access(user_id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    await safe_answer(call)
    await call.message.answer(
        "📂 <b>УПРАВЛЕНИЕ КАТЕГОРИЯМИ ЗАДАНИЙ</b>\n\n"
        "Выберите категорию для просмотра и переноса заданий:",
        reply_markup=get_category_management_menu()
    )

@router.callback_query(F.data.startswith("admin_category_"))
async def admin_category_tasks(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    if not check_admin_access(user_id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    category = call.data.replace("admin_category_", "")
    await safe_answer(call)
    
    tasks = get_active_tasks_by_category(category)
    if not tasks:
        await call.message.answer(f"📭 В категории {TASK_CATEGORIES.get(category, {}).get('name', category)} нет заданий")
        return
    
    await call.message.answer(
        f"📂 <b>{TASK_CATEGORIES.get(category, {}).get('name', category)}</b>\n\n"
        f"Выберите задание для переноса в другую категорию:",
        reply_markup=get_tasks_by_category_menu(tasks, category)
    )

@router.callback_query(F.data.startswith("admin_move_task_"))
async def admin_move_task_select(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    if not check_admin_access(user_id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    parts = call.data.split("_")
    task_id = int(parts[3])
    current_category = parts[4]
    
    await safe_answer(call)
    
    task = get_task(task_id)
    if not task:
        await call.message.answer("❌ Задание не найдено")
        return
    
    await call.message.answer(
        f"📋 <b>{task['title']}</b>\n\n"
        f"Текущая категория: {TASK_CATEGORIES.get(current_category, {}).get('name', current_category)}\n\n"
        f"Выберите новую категорию для переноса:",
        reply_markup=get_move_category_menu(task_id)
    )

@router.callback_query(F.data.startswith("admin_move_to_"))
async def admin_move_task(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    if not check_admin_access(user_id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    parts = call.data.split("_")
    new_category = parts[3]
    task_id = int(parts[4])
    
    if update_task(task_id, category=new_category):
        task = get_task(task_id)
        await safe_answer(call, f"✅ Задание \"{task['title']}\" перенесено!")
        await call.message.edit_text(
            f"✅ Задание успешно перенесено!\n\n"
            f"📋 {task['title']}\n"
            f"➡️ Новая категория: {TASK_CATEGORIES.get(new_category, {}).get('name', new_category)}"
        )
    else:
        await safe_answer(call, "❌ Ошибка при переносе задания", show_alert=True)

@router.callback_query(F.data == "admin_task_add")
async def admin_task_add_start(call: CallbackQuery, state: FSMContext):
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    await safe_answer(call)
    await state.set_state(CreateTaskStates.waiting_for_title)
    await call.message.answer("📝 Введите название задания:")

@router.message(CreateTaskStates.waiting_for_title)
async def admin_task_title(message: Message, state: FSMContext):
    if not check_admin_access(message.from_user.id)[0]:
        return
    await state.update_data(title=message.text)
    await state.set_state(CreateTaskStates.waiting_for_description)
    await message.answer("📄 Введите описание задания:")

@router.message(CreateTaskStates.waiting_for_description)
async def admin_task_description(message: Message, state: FSMContext):
    if not check_admin_access(message.from_user.id)[0]:
        return
    await state.update_data(description=message.text)
    await state.set_state(CreateTaskStates.waiting_for_reward)
    await message.answer("🎁 Введите награду (в 🍬):")

@router.message(CreateTaskStates.waiting_for_reward)
async def admin_task_reward(message: Message, state: FSMContext):
    if not check_admin_access(message.from_user.id)[0]:
        return
    try:
        reward = int(message.text)
        if reward <= 0:
            await message.answer("❌ Награда должна быть больше 0")
            return
        await state.update_data(reward=reward)
        await state.set_state(CreateTaskStates.waiting_for_max_completions)
        await message.answer("📊 Введите максимальное количество выполнений (1-999):")
    except ValueError:
        await message.answer("❌ Введите число")

@router.message(CreateTaskStates.waiting_for_max_completions)
async def admin_task_max_completions(message: Message, state: FSMContext):
    if not check_admin_access(message.from_user.id)[0]:
        return
    try:
        max_completions = int(message.text.strip())
        if max_completions < 1:
            max_completions = 1
        if max_completions > 999:
            max_completions = 999
        await state.update_data(max_completions=max_completions)
        await state.set_state(CreateTaskStates.waiting_for_category)
        
        await message.answer("📂 Выберите категорию задания:", reply_markup=task_category_keyboard)
    except ValueError:
        await message.answer("❌ Введите корректное число")

@router.callback_query(F.data == "admin_task_edit")
async def admin_task_edit_start(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    if not check_admin_access(user_id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    await safe_answer(call)
    
    tasks = get_active_tasks()
    if not tasks:
        await call.message.answer("📭 Нет активных заданий для редактирования")
        return
    
    keyboard = []
    for task in tasks:
        category_name = TASK_CATEGORIES.get(task.get("category", "easy"), {}).get('name', 'ЛЕГКИЕ')
        keyboard.append([InlineKeyboardButton(
            text=f"✏️ {task['title']} ({category_name}) | +{task['reward']}🍬",
            callback_data=f"edit_task_select_{task['id']}"
        )])
    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_tasks")])
    
    await call.message.answer(
        "📋 <b>ВЫБЕРИТЕ ЗАДАНИЕ ДЛЯ РЕДАКТИРОВАНИЯ</b>\n\n"
        "Нажмите на задание, чтобы начать редактирование:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@router.callback_query(F.data.startswith("edit_task_select_"))
async def edit_task_select(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    if not check_admin_access(user_id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    task_id = int(call.data.replace("edit_task_select_", ""))
    task = get_task(task_id)
    
    if not task:
        await safe_answer(call, "❌ Задание не найдено", show_alert=True)
        return
    
    await state.update_data(edit_task_id=task_id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Редактировать название", callback_data="edit_task_title")],
        [InlineKeyboardButton(text="📄 Редактировать описание", callback_data="edit_task_description")],
        [InlineKeyboardButton(text="🎁 Редактировать награду", callback_data="edit_task_reward")],
        [InlineKeyboardButton(text="📊 Редактировать лимит выполнений", callback_data="edit_task_max_completions")],
        [InlineKeyboardButton(text="📂 Редактировать категорию", callback_data="edit_task_category")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_tasks")]
    ])
    
    category_name = TASK_CATEGORIES.get(task.get("category", "easy"), {}).get('name', 'ЛЕГКИЕ')
    
    await safe_answer(call)
    await call.message.answer(
        f"✏️ <b>РЕДАКТИРОВАНИЕ ЗАДАНИЯ</b>\n\n"
        f"🆔 ID: {task['id']}\n"
        f"📋 Название: {task['title']}\n"
        f"📝 Описание: {task['description']}\n"
        f"🎁 Награда: +{task['reward']} 🍬\n"
        f"📊 Макс. выполнений: {task['max_completions']}\n"
        f"📂 Категория: {category_name}\n\n"
        f"Выберите, что хотите изменить:",
        reply_markup=keyboard
    )

@router.callback_query(F.data == "edit_task_title")
async def edit_task_title_start(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    if not check_admin_access(user_id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    await state.set_state(AdminStates.waiting_for_edit_task_title)
    await safe_answer(call)
    await call.message.answer("📝 Введите новое название задания:")

@router.message(AdminStates.waiting_for_edit_task_title)
async def edit_task_title_save(message: Message, state: FSMContext):
    if not check_admin_access(message.from_user.id)[0]:
        return
    
    new_title = message.text.strip()
    if not new_title:
        await message.answer("❌ Название не может быть пустым")
        return
    
    data = await state.get_data()
    task_id = data.get("edit_task_id")
    
    if update_task(task_id, title=new_title):
        await message.answer(f"✅ Название задания изменено на: {new_title}")
    else:
        await message.answer("❌ Ошибка при обновлении названия")
    
    await state.clear()

@router.callback_query(F.data == "edit_task_description")
async def edit_task_description_start(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    if not check_admin_access(user_id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    await state.set_state(AdminStates.waiting_for_edit_task_description)
    await safe_answer(call)
    await call.message.answer("📄 Введите новое описание задания:")

@router.message(AdminStates.waiting_for_edit_task_description)
async def edit_task_description_save(message: Message, state: FSMContext):
    if not check_admin_access(message.from_user.id)[0]:
        return
    
    new_description = message.text.strip()
    data = await state.get_data()
    task_id = data.get("edit_task_id")
    
    if update_task(task_id, description=new_description):
        await message.answer(f"✅ Описание задания обновлено")
    else:
        await message.answer("❌ Ошибка при обновлении описания")
    
    await state.clear()

@router.callback_query(F.data == "edit_task_reward")
async def edit_task_reward_start(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    if not check_admin_access(user_id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    await state.set_state(AdminStates.waiting_for_edit_task_reward)
    await safe_answer(call)
    await call.message.answer("🎁 Введите новую награду (в 🍬):")

@router.message(AdminStates.waiting_for_edit_task_reward)
async def edit_task_reward_save(message: Message, state: FSMContext):
    if not check_admin_access(message.from_user.id)[0]:
        return
    
    try:
        new_reward = int(message.text.strip())
        if new_reward <= 0:
            await message.answer("❌ Награда должна быть больше 0")
            return
        
        data = await state.get_data()
        task_id = data.get("edit_task_id")
        
        if update_task(task_id, reward=new_reward):
            await message.answer(f"✅ Награда изменена на: +{new_reward} 🍬")
        else:
            await message.answer("❌ Ошибка при обновлении награды")
        
        await state.clear()
    except ValueError:
        await message.answer("❌ Введите число")

@router.callback_query(F.data == "edit_task_max_completions")
async def edit_task_max_completions_start(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    if not check_admin_access(user_id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    await state.set_state(AdminStates.waiting_for_edit_task_max_completions)
    await safe_answer(call)
    await call.message.answer("📊 Введите новое максимальное количество выполнений (1-999):")

@router.message(AdminStates.waiting_for_edit_task_max_completions)
async def edit_task_max_completions_save(message: Message, state: FSMContext):
    if not check_admin_access(message.from_user.id)[0]:
        return
    
    try:
        new_max = int(message.text.strip())
        if new_max < 1:
            new_max = 1
        if new_max > 999:
            new_max = 999
        
        data = await state.get_data()
        task_id = data.get("edit_task_id")
        
        if update_task(task_id, max_completions=new_max):
            await message.answer(f"✅ Лимит выполнений изменен на: {new_max}")
        else:
            await message.answer("❌ Ошибка при обновлении лимита")
        
        await state.clear()
    except ValueError:
        await message.answer("❌ Введите число")

@router.callback_query(F.data == "edit_task_category")
async def edit_task_category_start(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    if not check_admin_access(user_id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🥉 ЛЕГКИЕ ЗАДАЧИ", callback_data="edit_category_easy")],
        [InlineKeyboardButton(text="🥈 СРЕДНИЕ ЗАДАЧИ", callback_data="edit_category_medium")],
        [InlineKeyboardButton(text="🥇 ЛУЧШИЕ ЗАДАЧИ", callback_data="edit_category_hard")],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_tasks")]
    ])
    
    await safe_answer(call)
    await call.message.answer("📂 Выберите новую категорию для задания:", reply_markup=keyboard)

@router.callback_query(F.data.startswith("edit_category_"))
async def edit_task_category_save(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    if not check_admin_access(user_id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    new_category = call.data.replace("edit_category_", "")
    data = await state.get_data()
    task_id = data.get("edit_task_id")
    
    if update_task(task_id, category=new_category):
        category_name = TASK_CATEGORIES.get(new_category, {}).get('name', new_category)
        await safe_answer(call, f"✅ Категория изменена на {category_name}")
        await call.message.answer(f"✅ Категория задания изменена на: {category_name}")
    else:
        await safe_answer(call, "❌ Ошибка при изменении категории", show_alert=True)
    
    await state.clear()

@router.callback_query(F.data == "admin_task_remove")
async def admin_task_remove_start(call: CallbackQuery, state: FSMContext):
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    await safe_answer(call)
    await state.set_state(AdminTaskStates.waiting_for_task_id_to_delete)
    tasks = get_active_tasks()
    if not tasks:
        await call.message.answer("📭 Нет активных заданий")
        return
    keyboard = []
    for task in tasks:
        category_name = TASK_CATEGORIES.get(task.get("category", "easy"), {}).get('name', 'ЛЕГКИЕ')
        keyboard.append([InlineKeyboardButton(text=f"❌ {task['title']} ({category_name})", callback_data=f"delete_task_{task['id']}")])
    keyboard.append([InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_tasks")])
    await call.message.answer(
        "🗑 <b>Выберите задание для удаления:</b>\n\n"
        "Или введите ID задания:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@router.callback_query(F.data.startswith("delete_task_"))
async def admin_task_remove_by_button(call: CallbackQuery, state: FSMContext):
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    task_id = int(call.data.replace("delete_task_", ""))
    task = get_task(task_id)
    if not task:
        await safe_answer(call, "❌ Задание не найдено", show_alert=True)
        return
    if remove_task(task_id):
        await safe_answer(call, f"✅ Задание \"{task['title']}\" удалено!")
        await call.message.edit_text(f"✅ Задание ID {task_id} удалено")
    else:
        await safe_answer(call, "❌ Ошибка при удалении", show_alert=True)
    await state.clear()

@router.message(AdminTaskStates.waiting_for_task_id_to_delete)
async def admin_task_remove(message: Message, state: FSMContext):
    if not check_admin_access(message.from_user.id)[0]:
        return
    try:
        task_id = int(message.text.strip())
        task = get_task(task_id)
        if not task:
            await message.answer("❌ Задание не найдено")
            await state.clear()
            return
        if remove_task(task_id):
            await message.answer(f"✅ Задание \"{task['title']}\" удалено!")
        else:
            await message.answer("❌ Ошибка при удалении")
        await state.clear()
    except ValueError:
        await message.answer("❌ Введите ID задания (число)")

@router.callback_query(F.data == "admin_task_list")
async def admin_task_list(call: CallbackQuery):
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    await safe_answer(call)
    tasks = get_active_tasks()
    if not tasks:
        await call.message.answer("📭 Нет активных заданий")
        return
    text = "📋 <b>СПИСОК ЗАДАНИЙ</b>\n\n"
    for task in tasks:
        category_name = TASK_CATEGORIES.get(task.get("category", "easy"), {}).get('name', 'ЛЕГКИЕ')
        text += f"🆔 <b>{task['id']}</b> | {task['title']} | {category_name}\n"
        text += f"   🎁 +{task['reward']} 🍬\n"
        text += f"   📊 {task['max_completions']} раз\n"
        text += f"   📝 {task['description'][:50]}...\n\n"
    await call.message.answer(text)

@router.callback_query(F.data == "admin_task_pending")
async def admin_task_pending(call: CallbackQuery):
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    await safe_answer(call)
    pending = get_pending_tasks()
    if not pending:
        await call.message.answer("📭 Нет заданий на проверке")
        return
    text = "⏳ <b>ЗАДАНИЯ НА ПРОВЕРКЕ</b>\n\n"
    for p in pending:
        text += f"👤 @{p['username']} (ID: {p['user_id']})\n"
        text += f"📋 {p['title']} | +{p['reward']} 🍬\n"
        text += f"📄 {p['proof'][:100]}...\n"
        text += f"🆔 Задания: {p['task_id']}\n\n"
    await call.message.answer(text)

@router.callback_query(F.data.startswith("admin_task_category_"))
async def admin_task_category(call: CallbackQuery, state: FSMContext):
    print(f"🔵🔵🔵 ВЫЗВАН обработчик admin_task_category_ с data: {call.data}")
    
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    category = call.data.replace("admin_task_category_", "")
    await safe_answer(call)
    
    data = await state.get_data()
    title = data.get("title")
    description = data.get("description")
    reward = data.get("reward")
    max_completions = data.get("max_completions", 1)
    
    if not title or not description or not reward:
        await call.message.answer("❌ Ошибка: не все данные заполнены. Начните создание заново.")
        await state.clear()
        return
    
    task_id = add_task(
        title=title,
        description=description,
        reward=reward,
        category=category,
        task_type="photo",
        task_data=None,
        max_completions=max_completions
    )
    
    if task_id:
        category_name = {
            "easy": "🥉 ЛЕГКИЕ ЗАДАЧИ",
            "medium": "🥈 СРЕДНИЕ ЗАДАЧИ",
            "hard": "🥇 ЛУЧШИЕ ЗАДАЧИ"
        }.get(category, category)
        
        await call.message.answer(
            f"✅ <b>Задание создано!</b>\n\n"
            f"📋 Название: {title}\n"
            f"📝 Описание: {description}\n"
            f"🎁 Награда: +{reward} 🍬\n"
            f"📊 Макс. выполнений: {max_completions}\n"
            f"📂 Категория: {category_name}\n"
            f"🆔 ID: {task_id}"
        )
    else:
        await call.message.answer("❌ Ошибка при создании задания")
    
    await state.clear()

@router.callback_query(F.data == "support")
async def support_start(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    if await check_spam(user_id):
        await safe_answer(call, get_text(user_id, "spam_warning"), show_alert=True)
        return
    if not await check_access(bot, user_id, state, call=call):
        return
    await safe_answer(call)
    await state.set_state(SubscribeStates.waiting_for_support_message)
    await call.message.answer(
        "📝 <b>ПОДДЕРЖКА</b>\n\n"
        "Напишите ваше сообщение или отправьте скриншот.\n"
        "Администратор ответит вам в ближайшее время."
    )

@router.message(SubscribeStates.waiting_for_support_message, F.text)
async def support_message_handler(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    user_text = message.text
    if not user_text or len(user_text) < 2:
        await message.answer("❌ Сообщение слишком короткое")
        return
    cursor.execute("SELECT username FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    username = user["username"] if user and user["username"] else "нет username"
    reply_keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✏️ Ответить", callback_data=f"reply_{user_id}")]])
    try:
        await bot.send_message(
            MAIN_ADMIN_ID,
            f"📬 <b>НОВОЕ СООБЩЕНИЕ В ПОДДЕРЖКУ</b>\n\n"
            f"👤 Пользователь: @{username}\n"
            f"🆔 ID: <code>{user_id}</code>\n\n"
            f"💬 Сообщение:\n{user_text}",
            reply_markup=reply_keyboard
        )
        await message.answer("✅ <b>Сообщение отправлено!</b>\n\nАдминистратор ответит вам в ближайшее время.")
    except:
        pass
    await state.clear()

@router.message(SubscribeStates.waiting_for_support_message, F.photo)
async def support_photo_handler(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    user_text = message.caption or "Без описания"
    photo = message.photo[-1]
    file_id = photo.file_id
    cursor.execute("SELECT username FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    username = user["username"] if user and user["username"] else "нет username"
    reply_keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✏️ Ответить", callback_data=f"reply_{user_id}")]])
    try:
        await bot.send_photo(
            MAIN_ADMIN_ID,
            photo=file_id,
            caption=(
                f"📸 <b>НОВЫЙ СКРИНШОТ В ПОДДЕРЖКУ</b>\n\n"
                f"👤 Пользователь: @{username}\n"
                f"🆔 ID: <code>{user_id}</code>\n\n"
                f"💬 Описание: {user_text}"
            ),
            reply_markup=reply_keyboard
        )
        await message.answer("✅ <b>Скриншот отправлен!</b>\n\nАдминистратор ответит вам в ближайшее время.")
    except:
        pass
    await state.clear()

@router.message(AdminStates.waiting_for_support_reply)
async def support_reply_send(message: Message, state: FSMContext, bot: Bot):
    if not check_admin_access(message.from_user.id)[0]:
        return
    data = await state.get_data()
    user_id = data.get('reply_to_user')
    reply_text = message.text
    explain_user_id = data.get('explain_user_id')
    explain_task_id = data.get('explain_task_id')
    if explain_user_id and explain_task_id:
        try:
            await bot.send_message(
                chat_id=explain_user_id,
                text=f"📋 <b>ПОЯСНЕНИЕ К ЗАДАНИЮ</b>\n\n"
                     f"Ваше задание было отклонено по следующей причине:\n\n{reply_text}\n\n"
                     f"Попробуйте выполнить задание заново."
            )
            await message.answer(f"✅ Пояснение отправлено пользователю {explain_user_id}")
        except:
            pass
        await state.update_data(explain_user_id=None, explain_task_id=None)
        await state.clear()
        return
    if not user_id:
        await message.answer("❌ Ошибка: не указан получатель")
        await state.clear()
        return
    try:
        await bot.send_message(chat_id=user_id, text=f"📬 <b>ОТВЕТ ОТ ПОДДЕРЖКИ</b>\n\n{reply_text}")
        await message.answer(f"✅ Ответ отправлен пользователю {user_id}")
    except Exception as e:
        await message.answer(
            f"❌ <b>ОШИБКА ОТПРАВКИ</b>\n\n"
            f"👤 Пользователь: <code>{user_id}</code>\n"
            f"❌ Ошибка: {str(e)}\n\n"
            f"💡 Попросите пользователя написать /start"
        )
    await state.clear()

@router.callback_query(F.data.startswith("reply_"))
async def support_reply_start(call: CallbackQuery, state: FSMContext, bot: Bot):
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    user_id = int(call.data.split("_")[1])
    cursor.execute("SELECT user_id, username FROM users WHERE user_id = ?", (user_id,))
    user_exists = cursor.fetchone()
    if not user_exists:
        await call.message.answer(f"❌ Пользователь с ID {user_id} не найден")
        return
    await state.update_data(reply_to_user=user_id)
    await state.set_state(AdminStates.waiting_for_support_reply)
    await call.message.answer(
        f"✏️ <b>ОТВЕТ ПОЛЬЗОВАТЕЛЮ</b>\n\n"
        f"ID: <code>{user_id}</code>\n"
        f"Username: @{user_exists['username'] or 'нет'}\n\n"
        f"Введите текст ответа:"
    )

@router.callback_query(F.data == "videos")
async def videos(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    if await check_spam(user_id):
        await safe_answer(call, get_text(user_id, "spam_warning"), show_alert=True)
        return
    if not await check_access(bot, user_id, state, call=call):
        return
    bonus = check_and_give_daily_bonus(user_id)
    if bonus:
        await call.message.answer(get_text(user_id, "bonus_received").format(bonus))
        add_battlepass_exp_db(user_id, 10)
    
    subscription = get_user_subscription(user_id)
    has_op_subscription = subscription and subscription["subscription_type"] == "op"
    if has_op_subscription:
        pass
    else:
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        if not result:
            await safe_answer(call, "❌ Пользователь не найден", show_alert=True)
            return
        balance = result["balance"]
        if balance < VIDEO_PRICE and not check_admin_access(user_id)[0]:
            await safe_answer(call, get_text(user_id, "not_enough_balance").format(balance), show_alert=True)
            return
    count = get_video_count_for_user(user_id)
    if count == 0:
        await safe_answer(call, "🎉 Поздравляем! Вы посмотрели все видео!", show_alert=True)
        return
    videos_list = get_videos_sorted_by_rating(user_id, 1)
    if not videos_list:
        await safe_answer(call, "❌ Видео не найдены", show_alert=True)
        return
    video = videos_list[0]
    current_video_id[user_id] = video["id"]
    user_rating = get_user_video_rating(video["id"], user_id)
    rating_stats = get_video_rating(video["id"])
    like_emoji = "👍" if user_rating == 1 else "👍"
    dislike_emoji = "👎" if user_rating == -1 else "👎"
    rating_text = f"⭐️ Рейтинг: {rating_stats['rating']:.1f}% ({rating_stats['likes']}👍 / {rating_stats['dislikes']}👎)"
    video_menu_with_rating = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{like_emoji} {rating_stats['likes']}", callback_data=f"like_video_{video['id']}"),
         InlineKeyboardButton(text=f"{dislike_emoji} {rating_stats['dislikes']}", callback_data=f"dislike_video_{video['id']}")],
        [InlineKeyboardButton(text="▶️ Следующее видео", callback_data="videos")],
        [InlineKeyboardButton(text="🏠 В меню", callback_data="menu_back")]
    ])
    try:
        await call.message.answer_video(video["file_id"], caption=f"🎥 <b>Видео</b>\n\n{rating_text}", reply_markup=video_menu_with_rating)
        if not has_op_subscription and not check_admin_access(user_id)[0]:
            cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (VIDEO_PRICE, user_id))
            await safe_answer(call, f"🍬 Видео отправлено! Списана {VIDEO_PRICE} конфета", show_alert=True)
        cursor.execute("INSERT OR IGNORE INTO user_videos (user_id, video_id) VALUES (?, ?)", (user_id, video["id"]))
        conn.commit()
        
        add_battlepass_exp_db(user_id, 5)
    except Exception as e:
        logger.error(f"❌ Error sending video: {e}")
        await safe_answer(call, "❌ Ошибка отправки видео. Попробуйте позже.", show_alert=True)

@router.callback_query(F.data.startswith("like_video_"))
async def like_video(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    if await check_spam(user_id):
        await safe_answer(call, get_text(user_id, "spam_warning"), show_alert=True)
        return
    if not await check_access(bot, user_id, state, call=call):
        return
    
    video_id = int(call.data.replace("like_video_", ""))
    stats = rate_video(video_id, user_id, 1)
    
    if stats:
        like_emoji = "👍"
        dislike_emoji = "👎"
        new_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"{like_emoji} {stats['likes']}", callback_data=f"like_video_{video_id}"),
             InlineKeyboardButton(text=f"{dislike_emoji} {stats['dislikes']}", callback_data=f"dislike_video_{video_id}")],
            [InlineKeyboardButton(text="▶️ Следующее видео", callback_data="videos")],
            [InlineKeyboardButton(text="🏠 В меню", callback_data="menu_back")]
        ])
        rating_text = f"⭐️ Рейтинг: {stats['rating']:.1f}% ({stats['likes']}👍 / {stats['dislikes']}👎)"
        try:
            await call.message.edit_caption(caption=f"🎥 <b>Видео</b>\n\n{rating_text}", reply_markup=new_keyboard)
            await safe_answer(call, "✅ Ваш голос учтен!", show_alert=False)
        except Exception as e:
            logger.error(f"Error updating caption: {e}")
    else:
        await safe_answer(call, "❌ Ошибка при голосовании", show_alert=True)

@router.callback_query(F.data.startswith("dislike_video_"))
async def dislike_video(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    if await check_spam(user_id):
        await safe_answer(call, get_text(user_id, "spam_warning"), show_alert=True)
        return
    if not await check_access(bot, user_id, state, call=call):
        return
    
    video_id = int(call.data.replace("dislike_video_", ""))
    stats = rate_video(video_id, user_id, -1)
    
    if stats:
        like_emoji = "👍"
        dislike_emoji = "👎"
        new_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"{like_emoji} {stats['likes']}", callback_data=f"like_video_{video_id}"),
             InlineKeyboardButton(text=f"{dislike_emoji} {stats['dislikes']}", callback_data=f"dislike_video_{video_id}")],
            [InlineKeyboardButton(text="▶️ Следующее видео", callback_data="videos")],
            [InlineKeyboardButton(text="🏠 В меню", callback_data="menu_back")]
        ])
        rating_text = f"⭐️ Рейтинг: {stats['rating']:.1f}% ({stats['likes']}👍 / {stats['dislikes']}👎)"
        try:
            await call.message.edit_caption(caption=f"🎥 <b>Видео</b>\n\n{rating_text}", reply_markup=new_keyboard)
            await safe_answer(call, "✅ Ваш голос учтен!", show_alert=False)
        except Exception as e:
            logger.error(f"Error updating caption: {e}")
    else:
        await safe_answer(call, "❌ Ошибка при голосовании", show_alert=True)

@router.callback_query(F.data == "menu_back")
async def menu_back_handler(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    has_access, _, is_main, can_manage = check_admin_access(user_id)
    if has_access:
        await call.message.answer("👑 Админ-панель", reply_markup=get_admin_menu(is_main, can_manage))
        return
    if not await check_access(call.bot, user_id, state, call=call):
        return
    await call.message.answer(get_text(user_id, "welcome"), reply_markup=get_main_menu(user_id))

@router.callback_query(F.data == "promo")
async def promo(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    if await check_spam(user_id):
        await safe_answer(call, get_text(user_id, "spam_warning"), show_alert=True)
        return
    if not await check_access(bot, user_id, state, call=call):
        return
    await state.set_state(PromoStates.waiting_for_promo)
    await call.message.answer("🎟 Введите промокод:")

@router.message(PromoStates.waiting_for_promo)
async def process_promo_input(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    if not await check_access(bot, user_id, state, message=message):
        return
    code = message.text.strip().upper()
    cursor.execute("SELECT * FROM promocodes WHERE UPPER(code) = UPPER(?)", (code,))
    promo = cursor.fetchone()
    if not promo:
        await message.answer(f"❌ Промокод '{code}' не найден")
        await state.clear()
        return
    if promo["activations_left"] <= 0:
        await message.answer("❌ Промокод закончился")
        await state.clear()
        return
    cursor.execute("SELECT 1 FROM used_promocodes WHERE user_id = ? AND code = ?", (user_id, promo["code"]))
    if cursor.fetchone():
        await message.answer("❌ Вы уже использовали этот промокод")
        await state.clear()
        return
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (promo["reward"], user_id))
    cursor.execute("UPDATE promocodes SET activations_left = activations_left - 1 WHERE code = ?", (promo["code"],))
    cursor.execute("INSERT INTO used_promocodes (user_id, code) VALUES (?, ?)", (user_id, promo["code"]))
    conn.commit()
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    new_balance = cursor.fetchone()["balance"]
    await message.answer(
        f"✅ <b>Промокод активирован!</b>\n\n"
        f"🎁 Начислено: +{promo['reward']} 🍬\n"
        f"💰 Текущий баланс: {new_balance} 🍬"
    )
    await state.clear()

@router.callback_query(F.data == "profile")
async def profile(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    if await check_spam(user_id):
        await safe_answer(call, get_text(user_id, "spam_warning"), show_alert=True)
        return
    if not await check_access(bot, user_id, state, call=call):
        return
    cursor.execute("SELECT balance, referrer, ref_code FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        await safe_answer(call, "❌ Пользователь не найден", show_alert=True)
        return
    balance = user["balance"]
    ref_code = user["ref_code"]
    if not ref_code:
        ref_code = generate_ref_code()
        cursor.execute("UPDATE users SET ref_code = ? WHERE user_id = ?", (ref_code, user_id))
        conn.commit()
    ref_link = f"https://t.me/{BOT_USERNAME}?start={ref_code}"
    cursor.execute("SELECT COUNT(*) as count FROM users WHERE referrer = ?", (user_id,))
    ref_count = cursor.fetchone()["count"]
    subscription = get_user_subscription(user_id)
    sub_text = "❌ Нет активной подписки"
    if subscription:
        sub_type = subscription["subscription_type"]
        sub_name = SUBSCRIPTIONS.get(sub_type, {}).get("name", sub_type)
        expires = subscription["expires_at"][:10]
        sub_text = f"✅ {sub_name}\n📅 До: {expires}"
    text = (
        f"{get_text(user_id, 'profile_title')}\n\n"
        f"{get_text(user_id, 'balance_label').format(balance)}\n"
        f"{get_text(user_id, 'referrals_label').format(ref_count)}\n"
        f"{get_text(user_id, 'subscription_label').format(sub_text)}\n\n"
        f"{get_text(user_id, 'your_link')}\n"
        f"<code>{ref_link}</code>\n"
        f"<a href='{ref_link}'>( Синяя ссылка, жми )</a>\n\n"
        f"{get_text(user_id, 'ref_reward').format(REF_BONUS)}\n"
        f"{get_text(user_id, 'ref_percent').format(REF_PERCENT)}"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=get_text(user_id, "back_to_menu"), callback_data="menu")]])
    await call.message.answer(text, disable_web_page_preview=False, reply_markup=keyboard)

@router.callback_query(F.data == "bonus")
async def bonus(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    if await check_spam(user_id):
        await safe_answer(call, get_text(user_id, "spam_warning"), show_alert=True)
        return
    if not await check_access(bot, user_id, state, call=call):
        return
    now = int(time.time())
    cursor.execute("SELECT last_bonus FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    if not result:
        await safe_answer(call, "❌ Пользователь не найден", show_alert=True)
        return
    last = result["last_bonus"]
    if now - last < BONUS_COOLDOWN:
        remaining = BONUS_COOLDOWN - (now - last)
        minutes = remaining // 60
        seconds = remaining % 60
        await safe_answer(call, get_text(user_id, "bonus_cooldown").format(minutes, seconds), show_alert=True)
        return
    cursor.execute("UPDATE users SET balance = balance + ?, last_bonus = ? WHERE user_id = ?", (BONUS_AMOUNT, now, user_id))
    conn.commit()
    await safe_answer(call, get_text(user_id, "bonus_received").format(BONUS_AMOUNT), show_alert=True)
    
    add_battlepass_exp_db(user_id, 10)

@router.callback_query(F.data.startswith("fake_"))
async def fake_menu_actions(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    await safe_answer(call)
    
    if has_referrer(user_id):
        if await check_access(call.bot, user_id, state, call=call):
            await call.message.answer(get_text(user_id, "welcome"), reply_markup=get_main_menu(user_id))
        return
    
    if call.data == "fake_download":
        await safe_answer(call, "❌ Ошибка загрузки. Попробуйте позже.", show_alert=True)
    elif call.data == "fake_rate":
        rate = random.randint(45000, 52000)
        await safe_answer(call, f"💱 Курс BTC: ${rate}", show_alert=True)
    elif call.data == "fake_dice":
        dice = random.randint(1, 6)
        await safe_answer(call, f"🎲 Выпало: {dice}", show_alert=True)
    elif call.data == "fake_chat":
        await safe_answer(call)
        await state.set_state(FakeChatStates.waiting_for_anon_message)
        await call.message.answer(
            "💬 <b>АНОНИМНЫЙ ЧАТ</b>\n\n"
            "Вы подключились к анонимному чату!\n"
            "Напишите любое сообщение, и вам ответит случайный собеседник.\n\n"
            "Для выхода отправьте <b>/exit</b> или нажмите кнопку ниже.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🚪 Выйти из чата", callback_data="fake_exit_chat")]
            ])
        )
        anon_chat_sessions[user_id] = True

@router.callback_query(F.data == "fake_exit_chat")
async def fake_exit_chat(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    await safe_answer(call)
    await state.clear()
    if user_id in anon_chat_sessions:
        del anon_chat_sessions[user_id]
    await call.message.answer(
        "👋 Вы вышли из анонимного чата.\n"
        "Возвращайтесь ещё!",
        reply_markup=fake_menu
    )

@router.message(FakeChatStates.waiting_for_anon_message)
async def process_anon_message(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user_text = message.text
    
    if user_text and user_text.startswith('/exit'):
        await state.clear()
        if user_id in anon_chat_sessions:
            del anon_chat_sessions[user_id]
        await message.answer(
            "👋 Вы вышли из анонимного чата.\n"
            "Возвращайтесь ещё!",
            reply_markup=fake_menu
        )
        return
    
    if not user_text:
        await message.answer("❌ Отправьте текстовое сообщение!")
        return
    
    await message.bot.send_chat_action(chat_id=user_id, action="typing")
    await asyncio.sleep(random.uniform(1.5, 3.5))
    
    response = random.choice(ANON_CHAT_RESPONSES)
    
    await message.answer(response)
    
    await message.answer(
        "💭 <i>Продолжить общение? Напишите ещё сообщение или нажмите кнопку для выхода.</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚪 Выйти из чата", callback_data="fake_exit_chat")]
        ]),
        parse_mode="HTML"
    )
    
    anon_chat_sessions[user_id] = True

@router.message(Command("exit"))
async def exit_chat_command(message: Message, state: FSMContext):
    user_id = message.from_user.id
    current_state = await state.get_state()
    
    if current_state == FakeChatStates.waiting_for_anon_message.state:
        await state.clear()
        if user_id in anon_chat_sessions:
            del anon_chat_sessions[user_id]
        await message.answer(
            "👋 Вы вышли из анонимного чата.\n"
            "Возвращайтесь ещё!",
            reply_markup=fake_menu
        )
    else:
        await message.answer("Вы не в анонимном чате.")

@router.callback_query(F.data == "admin_panel")
async def admin_panel(call: CallbackQuery):
    user_id = call.from_user.id
    has_access, _, is_main, can_manage = check_admin_access(user_id)
    if not has_access:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    await safe_answer(call)
    await call.message.edit_text("👑 Админ-панель", reply_markup=get_admin_menu(is_main, can_manage))

@router.callback_query(F.data == "menu")
async def back_to_menu(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    has_access, _, is_main, can_manage = check_admin_access(user_id)
    if has_access:
        await call.message.edit_text("👑 Админ-панель", reply_markup=get_admin_menu(is_main, can_manage))
        return
    if not await check_access(call.bot, user_id, state, call=call):
        return
    await call.message.edit_text(get_text(user_id, "welcome"), reply_markup=get_main_menu(user_id))

@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    has_access, _, _, _ = check_admin_access(user_id)
    if not has_access:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    await safe_answer(call)
    await state.set_state(AdminStates.waiting_for_broadcast)
    await call.message.answer("📢 Введите текст для рассылки:")

@router.message(AdminStates.waiting_for_broadcast)
async def process_broadcast_text(message: Message, state: FSMContext):
    user_id = message.from_user.id
    has_access, _, _, _ = check_admin_access(user_id)
    if not has_access:
        return
    text = message.text
    await state.update_data(broadcast_text=text)
    await state.set_state(AdminStates.waiting_for_broadcast_confirm)
    await message.answer(
        f"📢 <b>Предпросмотр рассылки:</b>\n\n{text}\n\n"
        f"✅ Отправить всем пользователям?",
        reply_markup=confirm_menu
    )

@router.callback_query(F.data == "confirm_broadcast")
async def confirm_broadcast(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    has_access, _, _, _ = check_admin_access(user_id)
    if not has_access:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    await safe_answer(call)
    data = await state.get_data()
    text = data.get('broadcast_text')
    if not text:
        await call.message.answer("❌ Ошибка: текст не найден")
        await state.clear()
        return
    cursor.execute("SELECT user_id FROM users")
    users = [row["user_id"] for row in cursor.fetchall()]
    broadcast_mode.add(call.from_user.id)
    sent = 0
    failed = 0
    status_msg = await call.message.answer(f"📢 Начинаю рассылку...\nВсего пользователей: {len(users)}")
    for i, uid in enumerate(users):
        try:
            await bot.send_message(uid, text)
            sent += 1
            if i % 10 == 0:
                await status_msg.edit_text(f"📢 Рассылка...\nОтправлено: {sent}/{len(users)}")
            await asyncio.sleep(0.05)
        except:
            failed += 1
    broadcast_mode.discard(call.from_user.id)
    await status_msg.edit_text(f"📢 Рассылка завершена!\n✅ Отправлено: {sent}\n❌ Не отправлено: {failed}")
    await state.clear()
    await call.message.answer("👑 Админ-панель", reply_markup=get_admin_menu())

@router.callback_query(F.data == "cancel_broadcast")
async def cancel_broadcast(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    has_access, _, _, _ = check_admin_access(user_id)
    if not has_access:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    await safe_answer(call)
    await state.clear()
    broadcast_mode.discard(call.from_user.id)
    await call.message.answer("❌ Рассылка отменена")
    await call.message.answer("👑 Админ-панель", reply_markup=get_admin_menu())

@router.callback_query(F.data == "admin_add_promo")
async def admin_add_promo(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    has_access, _, _, _ = check_admin_access(user_id)
    if not has_access:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    await safe_answer(call)
    await state.set_state(AdminStates.waiting_for_add_promo_code)
    await call.message.answer("🎟 Введите промокод (будет автоматически преобразован в верхний регистр):")

@router.message(AdminStates.waiting_for_add_promo_code)
async def process_add_promo_code(message: Message, state: FSMContext):
    user_id = message.from_user.id
    has_access, _, _, _ = check_admin_access(user_id)
    if not has_access:
        return
    code = message.text.upper().strip()
    await state.update_data(code=code)
    await state.set_state(AdminStates.waiting_for_add_promo_reward)
    await message.answer("🎁 Введите награду за промокод (в 🍬):")

@router.message(AdminStates.waiting_for_add_promo_reward)
async def process_add_promo_reward(message: Message, state: FSMContext):
    user_id = message.from_user.id
    has_access, _, _, _ = check_admin_access(user_id)
    if not has_access:
        return
    try:
        reward = int(message.text)
        await state.update_data(reward=reward)
        await state.set_state(AdminStates.waiting_for_add_promo_uses)
        await message.answer("📊 Введите количество активаций:")
    except ValueError:
        await message.answer("❌ Введите число")

@router.message(AdminStates.waiting_for_add_promo_uses)
async def process_add_promo_uses(message: Message, state: FSMContext):
    user_id = message.from_user.id
    has_access, _, _, _ = check_admin_access(user_id)
    if not has_access:
        return
    data = await state.get_data()
    code = data.get('code')
    reward = data.get('reward')
    try:
        uses = int(message.text)
    except ValueError:
        await message.answer("❌ Введите корректное количество активаций (число)")
        return
    cursor.execute("SELECT code FROM promocodes WHERE UPPER(code) = UPPER(?)", (code,))
    existing = cursor.fetchone()
    if existing:
        await message.answer(f"❌ Промокод {code} уже существует!")
        await state.clear()
        return
    cursor.execute("INSERT INTO promocodes (code, reward, activations_left) VALUES (?, ?, ?)", (code, reward, uses))
    conn.commit()
    await message.answer(
        f"✅ <b>Промокод создан!</b>\n\n"
        f"🎟 Код: <code>{code}</code>\n"
        f"🎁 Награда: {reward} 🍬\n"
        f"📊 Активаций: {uses}"
    )
    await state.clear()
    await message.answer("👑 Админ-панель", reply_markup=get_admin_menu())

@router.callback_query(F.data == "admin_add_balance")
async def admin_add_balance(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    has_access, _, _, _ = check_admin_access(user_id)
    if not has_access:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    await safe_answer(call)
    await state.set_state(AdminStates.waiting_for_add_balance_user)
    await call.message.answer("👤 Введите ID пользователя:")

@router.message(AdminStates.waiting_for_add_balance_user)
async def process_add_balance_user(message: Message, state: FSMContext):
    user_id = message.from_user.id
    has_access, _, _, _ = check_admin_access(user_id)
    if not has_access:
        return
    try:
        target_user_id = int(message.text)
        await state.update_data(user_id=target_user_id)
        await state.set_state(AdminStates.waiting_for_add_balance_amount)
        await message.answer("💰 Введите сумму для добавления:")
    except ValueError:
        await message.answer("❌ Введите корректный ID пользователя (число)")

@router.message(AdminStates.waiting_for_add_balance_amount)
async def process_add_balance_amount(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    has_access, _, _, _ = check_admin_access(user_id)
    if not has_access:
        return
    data = await state.get_data()
    target_user_id = data.get('user_id')
    try:
        amount = int(message.text)
    except ValueError:
        await message.answer("❌ Введите корректную сумму (число)")
        return
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target_user_id))
    conn.commit()
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (target_user_id,))
    result = cursor.fetchone()
    if result:
        new_balance = result["balance"]
        await message.answer(f"✅ Баланс пользователя {target_user_id} увеличен на {amount} 🍬\nНовый баланс: {new_balance} 🍬")
        try:
            await bot.send_message(target_user_id, f"💰 Администратор начислил вам {amount} 🍬\nТекущий баланс: {new_balance} 🍬")
        except:
            pass
    else:
        await message.answer("❌ Пользователь не найден")
    await state.clear()
    await message.answer("👑 Админ-панель", reply_markup=get_admin_menu())

@router.callback_query(F.data == "admin_remove_balance")
async def admin_remove_balance(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    has_access, _, _, _ = check_admin_access(user_id)
    if not has_access:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    await safe_answer(call)
    await state.set_state(AdminStates.waiting_for_remove_balance_user)
    await call.message.answer("👤 Введите ID пользователя:")

@router.message(AdminStates.waiting_for_remove_balance_user)
async def process_remove_balance_user(message: Message, state: FSMContext):
    user_id = message.from_user.id
    has_access, _, _, _ = check_admin_access(user_id)
    if not has_access:
        return
    try:
        target_user_id = int(message.text)
        await state.update_data(user_id=target_user_id)
        await state.set_state(AdminStates.waiting_for_remove_balance_amount)
        await message.answer("💰 Введите сумму для снятия:")
    except ValueError:
        await message.answer("❌ Введите корректный ID пользователя (число)")

@router.message(AdminStates.waiting_for_remove_balance_amount)
async def process_remove_balance_amount(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    has_access, _, _, _ = check_admin_access(user_id)
    if not has_access:
        return
    data = await state.get_data()
    target_user_id = data.get('user_id')
    try:
        amount = int(message.text)
    except ValueError:
        await message.answer("❌ Введите корректную сумму (число)")
        return
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (target_user_id,))
    result = cursor.fetchone()
    if not result:
        await message.answer("❌ Пользователь не найден")
        await state.clear()
        return
    current_balance = result["balance"]
    if current_balance < amount:
        await message.answer(f"❌ У пользователя недостаточно конфет. Текущий баланс: {current_balance}")
        await state.clear()
        return
    cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, target_user_id))
    conn.commit()
    new_balance = current_balance - amount
    await message.answer(f"✅ Баланс пользователя {target_user_id} уменьшен на {amount} 🍬\nНовый баланс: {new_balance} 🍬")
    try:
        await bot.send_message(target_user_id, f"⚠️ Администратор снял {amount} 🍬 с вашего баланса\nТекущий баланс: {new_balance} 🍬")
    except:
        pass
    await state.clear()
    await message.answer("👑 Админ-панель", reply_markup=get_admin_menu())

@router.callback_query(F.data == "admin_stats")
async def admin_stats(call: CallbackQuery):
    user_id = call.from_user.id
    has_access, _, _, _ = check_admin_access(user_id)
    if not has_access:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    await safe_answer(call)
    total_users = get_total_users()
    verified_users = get_verified_users()
    users_with_balance = get_users_with_balance()
    total_balance = get_total_balance()
    max_balance = get_max_balance()
    avg_balance = get_avg_balance()
    total_videos = get_video_count()
    watched_stats = get_watched_stats()
    payments_stats = get_payments_stats()
    promo_stats = get_promo_stats()
    bonus_stats = get_bonus_stats()
    referral_stats = get_referral_stats()
    channels = get_mandatory_channels()
    cursor.execute("SELECT COUNT(*) as count FROM users WHERE subscribe_bonus_received = 1")
    bonus_received = cursor.fetchone()["count"] or 0
    admins = get_all_admins()
    admins_count = len(admins)
    text = (
        f"📊 <b>ПОЛНАЯ СТАТИСТИКА</b>\n\n"
        f"👥 <b>ПОЛЬЗОВАТЕЛИ:</b>\n"
        f"├ 👤 Всего: {total_users}\n"
        f"├ ✅ Верифицировано: {verified_users}\n"
        f"├ ❌ Не верифицировано: {total_users - verified_users}\n"
        f"├ 🔗 По рефералкам: {referral_stats['total_refs']}\n"
        f"├ 💰 С балансом: {users_with_balance}\n"
        f"├ 🍪 С нулевым балансом: {total_users - users_with_balance}\n"
        f"├ 👑 Админов: {admins_count}\n"
        f"└ 🎁 Получили бонус за подписку: {bonus_received}\n\n"
        f"💰 <b>БАЛАНСЫ:</b>\n"
        f"├ 💎 Всего конфет: {total_balance} 🍬\n"
        f"├ 📊 Средний баланс: {avg_balance:.1f} 🍬\n"
        f"└ 🏆 Макс. баланс: {max_balance} 🍬\n\n"
        f"🎥 <b>ВИДЕО:</b>\n"
        f"├ 📹 Всего видео: {total_videos}\n"
        f"├ 👀 Всего просмотров: {watched_stats['total_views']}\n"
        f"└ 🎬 Смотрели видео: {watched_stats['unique_viewers']} чел\n\n"
        f"💳 <b>ПЛАТЕЖИ:</b>\n"
        f"├ 💸 Успешных платежей: {payments_stats['successful']}\n"
        f"├ 🍬 Куплено конфет: {payments_stats['total_candies']} 🍬\n"
        f"├ 📝 Всего попыток: {payments_stats['total_attempts']}\n"
        f"└ ❌ Неуспешных: {payments_stats['total_attempts'] - payments_stats['successful']}\n\n"
        f"🎟 <b>ПРОМОКОДЫ:</b>\n"
        f"├ 📋 Всего создано: {promo_stats['total_codes']}\n"
        f"├ ✅ Активировано: {promo_stats['total_used']}\n"
        f"└ 📦 Осталось активаций: {promo_stats['total_left']}\n\n"
        f"📈 <b>АКТИВНОСТЬ:</b>\n"
        f"├ 🎁 Брали бонус: {bonus_stats['users_took_bonus']} чел\n"
        f"└ 👁 Активные юзеры: {watched_stats['unique_viewers']} чел\n\n"
        f"🔐 <b>ОБЯЗАТЕЛЬНАЯ ПОДПИСКА:</b>\n"
        f"└ 📢 Каналов в ОП: {len(channels)}"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏆 Топ рефералов", callback_data="admin_top_refs")],
        [InlineKeyboardButton(text="💰 Топ по балансу", callback_data="admin_top_balance")],
        [InlineKeyboardButton(text="🔍 Поиск платежей", callback_data="admin_search_payments")],
        [InlineKeyboardButton(text="👤 Поиск пользователей", callback_data="admin_search_users")],
        [InlineKeyboardButton(text="💎 Активные подписки", callback_data="admin_active_subscriptions")]
    ])
    await call.message.answer(text)
    await call.message.answer("📊 <b>Дополнительная статистика</b>", reply_markup=keyboard)

@router.callback_query(F.data == "admin_top_refs")
async def admin_top_refs(call: CallbackQuery):
    user_id = call.from_user.id
    has_access, _, _, _ = check_admin_access(user_id)
    if not has_access:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    await safe_answer(call)
    cursor.execute("""
        SELECT u.user_id, u.username, 
               COUNT(r.user_id) as ref_count,
               SUM(r.balance) as ref_balance
        FROM users u
        LEFT JOIN users r ON r.referrer = u.user_id
        GROUP BY u.user_id
        HAVING ref_count > 0
        ORDER BY ref_count DESC
        LIMIT 10
    """)
    top_refs = cursor.fetchall()
    text = "🏆 <b>ТОП 10 РЕФЕРАЛОВ</b>\n\n"
    if not top_refs:
        text += "📭 Нет данных"
    else:
        for i, ref in enumerate(top_refs, 1):
            username = ref["username"] or "нет username"
            ref_count = ref["ref_count"]
            ref_balance = ref["ref_balance"] or 0
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "🔹"
            text += f"{medal} <b>{i}.</b> @{username}\n"
            text += f"   👥 Рефералов: {ref_count}\n"
            text += f"   💰 Баланс рефералов: {ref_balance} 🍬\n\n"
    keyboard = [[InlineKeyboardButton(text="🔙 Назад", callback_data="admin_stats")]]
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

@router.callback_query(F.data == "admin_search_payments")
async def admin_search_payments_start(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    has_access, _, _, _ = check_admin_access(user_id)
    if not has_access:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    await safe_answer(call)
    await state.set_state(AdminStates.waiting_for_payment_search)
    await call.message.answer("🔍 <b>Поиск платежей</b>\n\nВведите ID пользователя или username для поиска:\nНапример: <code>123456789</code> или <code>@username</code>")

@router.message(AdminStates.waiting_for_payment_search)
async def admin_search_payments_result(message: Message, state: FSMContext):
    user_id = message.from_user.id
    has_access, _, _, _ = check_admin_access(user_id)
    if not has_access:
        return
    search_query = message.text.strip()
    if search_query.startswith('@'):
        username = search_query[1:]
        cursor.execute("SELECT user_id, username FROM users WHERE username = ?", (username,))
    else:
        try:
            target_id = int(search_query)
            cursor.execute("SELECT user_id, username FROM users WHERE user_id = ?", (target_id,))
        except ValueError:
            cursor.execute("SELECT user_id, username FROM users WHERE username LIKE ?", (f"%{search_query}%",))
    users = cursor.fetchall()
    if not users:
        await message.answer(f"❌ Пользователь не найден")
        await state.clear()
        return
    text = f"🔍 <b>Результаты поиска:</b>\n\n"
    for user in users[:5]:
        uid = user["user_id"]
        uname = user["username"] or "нет username"
        cursor.execute("""
            SELECT invoice_id, amount, 
                   CASE WHEN paid = 1 THEN '✅ Оплачен' ELSE '⏳ Ожидает' END as status
            FROM payments 
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 10
        """, (uid,))
        payments = cursor.fetchall()
        text += f"👤 <b>ID:</b> <code>{uid}</code> | @{uname}\n"
        if payments:
            for p in payments:
                text += f"   • {p['amount']} 🍬 | {p['status']}\n"
        else:
            text += f"   • Нет платежей\n"
        text += "\n"
    if len(users) > 5:
        text += f"... и еще {len(users) - 5} пользователей\n"
    keyboard = [[InlineKeyboardButton(text="🔙 Назад", callback_data="admin_stats")]]
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    await state.clear()

@router.callback_query(F.data == "admin_search_users")
async def admin_search_users_start(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    has_access, _, _, _ = check_admin_access(user_id)
    if not has_access:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    await safe_answer(call)
    await state.set_state(AdminStates.waiting_for_user_search)
    await call.message.answer("👤 <b>Поиск пользователей</b>\n\nВведите ID пользователя, username или часть username для поиска:")

@router.message(AdminStates.waiting_for_user_search)
async def admin_search_users_result(message: Message, state: FSMContext):
    user_id = message.from_user.id
    has_access, _, _, _ = check_admin_access(user_id)
    if not has_access:
        return
    search_query = message.text.strip()
    if search_query.startswith('@'):
        username = search_query[1:]
        cursor.execute("""
            SELECT user_id, username, balance, is_verified, 
                   referrer, last_bonus, subscribe_bonus_received, is_admin
            FROM users WHERE username = ?
        """, (username,))
    else:
        try:
            target_id = int(search_query)
            cursor.execute("""
                SELECT user_id, username, balance, is_verified, 
                       referrer, last_bonus, subscribe_bonus_received, is_admin
                FROM users WHERE user_id = ?
            """, (target_id,))
        except ValueError:
            cursor.execute("""
                SELECT user_id, username, balance, is_verified, 
                       referrer, last_bonus, subscribe_bonus_received, is_admin
                FROM users WHERE username LIKE ?
                ORDER BY user_id
                LIMIT 10
            """, (f"%{search_query}%",))
    users = cursor.fetchall()
    if not users:
        await message.answer(f"❌ Пользователи не найдены")
        await state.clear()
        return
    text = f"👤 <b>Результаты поиска:</b>\n\n"
    for user in users:
        uid = user["user_id"]
        uname = user["username"] or "нет username"
        balance = user["balance"]
        verified = "✅" if user["is_verified"] else "❌"
        admin = "👑" if user["is_admin"] else ""
        text += f"<b>ID:</b> <code>{uid}</code> {admin}\n"
        text += f"<b>Username:</b> @{uname}\n"
        text += f"<b>Баланс:</b> {balance} 🍬\n"
        text += f"<b>Верифицирован:</b> {verified}\n"
        if user["referrer"]:
            text += f"<b>Реферер:</b> <code>{user['referrer']}</code>\n"
        if user["last_bonus"] > 0:
            last_bonus = datetime.fromtimestamp(user["last_bonus"]).strftime("%Y-%m-%d %H:%M")
            text += f"<b>Последний бонус:</b> {last_bonus}\n"
        if user["subscribe_bonus_received"]:
            text += f"<b>Бонус за подписку:</b> ✅\n"
        text += "\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Подписки пользователя", callback_data=f"admin_user_subscriptions_{uid}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_stats")]
    ])
    await message.answer(text, reply_markup=keyboard)
    await state.clear()

@router.callback_query(F.data == "admin_give_subscription")
async def admin_give_subscription_start(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    has_access, _, _, _ = check_admin_access(user_id)
    if not has_access:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    await safe_answer(call)
    await state.set_state(AdminStates.waiting_for_subscription_user)
    await call.message.answer("👤 Введите ID пользователя для выдачи подписки:")

@router.message(AdminStates.waiting_for_subscription_user)
async def admin_subscription_user(message: Message, state: FSMContext):
    user_id = message.from_user.id
    has_access, _, _, _ = check_admin_access(user_id)
    if not has_access:
        return
    try:
        target_user_id = int(message.text)
        await state.update_data(target_user_id=target_user_id)
        await state.set_state(AdminStates.waiting_for_subscription_type)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 OP Статус (9 дней)", callback_data="sub_op")],
            [InlineKeyboardButton(text="🚀 Base Статус (9 дней)", callback_data="sub_base")],
            [InlineKeyboardButton(text="😊 Newbie Статус (9 дней)", callback_data="sub_newbie")],
            [InlineKeyboardButton(text="❌ Удалить подписку", callback_data="sub_remove")]
        ])
        await message.answer(f"👤 Пользователь: {target_user_id}\n\nВыберите тип подписки:", reply_markup=keyboard)
    except ValueError:
        await message.answer("❌ Введите корректный ID пользователя (число)")

@router.callback_query(F.data.startswith("sub_"))
async def admin_subscription_type(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    has_access, _, _, _ = check_admin_access(user_id)
    if not has_access:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    data = await state.get_data()
    target_user_id = data.get("target_user_id")
    if not target_user_id:
        await safe_answer(call, "❌ Ошибка: пользователь не найден", show_alert=True)
        await state.clear()
        return
    action = call.data.replace("sub_", "")
    if action == "remove":
        if remove_subscription(target_user_id):
            await call.message.answer(f"✅ Подписка пользователя {target_user_id} удалена!")
            try:
                await call.bot.send_message(
                    target_user_id,
                    f"⚠️ <b>Ваша подписка была удалена администратором!</b>\n\n"
                    f"Если у вас есть вопросы, обратитесь в поддержку."
                )
            except:
                pass
        else:
            await call.message.answer("❌ Ошибка при удалении подписки")
        await state.clear()
        return
    sub_types = {"op": "op", "base": "base", "newbie": "newbie"}
    sub_type = sub_types.get(action)
    if not sub_type:
        await safe_answer(call, "❌ Неизвестный тип подписки", show_alert=True)
        return
    sub = SUBSCRIPTIONS.get(sub_type)
    if add_subscription(target_user_id, sub_type, sub["days"]):
        await call.message.answer(
            f"✅ Подписка выдана!\n\n"
            f"👤 Пользователь: {target_user_id}\n"
            f"📋 Тип: {sub['name']}\n"
            f"📅 Дней: {sub['days']}"
        )
        try:
            await call.bot.send_message(
                target_user_id,
                f"🎉 <b>Вам выдана подписка!</b>\n\n"
                f"{sub['name']}\n"
                f"📅 Действует {sub['days']} дней\n\n"
                f"{sub['benefits']}\n\n"
                f"Поздравляем!"
            )
        except:
            pass
    else:
        await call.message.answer("❌ Ошибка при выдаче подписки")
    await state.clear()

@router.callback_query(F.data == "admin_active_subscriptions")
async def admin_active_subscriptions(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    has_access, _, _, _ = check_admin_access(user_id)
    if not has_access:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    await safe_answer(call)
    
    subscriptions = get_all_active_subscriptions()
    
    if not subscriptions:
        await call.message.answer("📭 Нет активных подписок")
        return
    
    text = "💎 <b>АКТИВНЫЕ ПОДПИСКИ</b>\n\n"
    
    for sub in subscriptions:
        uid = sub["user_id"]
        sub_type = sub["subscription_type"]
        expires = sub["expires_at"][:16]
        
        sub_name = SUBSCRIPTIONS.get(sub_type, {}).get("name", sub_type)
        
        cursor.execute("SELECT username FROM users WHERE user_id = ?", (uid,))
        user = cursor.fetchone()
        username = user["username"] if user and user["username"] else "нет username"
        
        text += f"👤 @{username} (ID: {uid})\n"
        text += f"📋 {sub_name}\n"
        text += f"📅 До: {expires}\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад в админ-панель", callback_data="admin_panel")]
    ])
    
    await call.message.answer(text, reply_markup=keyboard)

@router.callback_query(F.data.startswith("admin_user_subscriptions_"))
async def admin_user_subscriptions(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    if not check_admin_access(user_id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    target_user_id = int(call.data.replace("admin_user_subscriptions_", ""))
    
    subscriptions = get_user_subscriptions(target_user_id)
    
    if not subscriptions:
        await call.message.answer(f"📭 У пользователя {target_user_id} нет подписок")
        return
    
    cursor.execute("SELECT username FROM users WHERE user_id = ?", (target_user_id,))
    user = cursor.fetchone()
    username = user["username"] if user and user["username"] else "нет username"
    
    text = f"📋 <b>ПОДПИСКИ ПОЛЬЗОВАТЕЛЯ</b>\n\n"
    text += f"👤 @{username} (ID: {target_user_id})\n\n"
    
    for sub in subscriptions:
        sub_type = sub["subscription_type"]
        expires = sub["expires_at"][:16] if sub["expires_at"] else "бессрочно"
        created = sub["created_at"][:16]
        
        sub_name = SUBSCRIPTIONS.get(sub_type, {}).get("name", sub_type)
        is_active = "✅ АКТИВНА" if sub["expires_at"] and datetime.fromisoformat(sub["expires_at"]) > datetime.now() else "❌ ИСТЕКЛА"
        
        text += f"{'🟢' if 'АКТИВНА' in is_active else '🔴'} {sub_name}\n"
        text += f"   📅 До: {expires}\n"
        text += f"   📆 Куплена: {created}\n"
        text += f"   {is_active}\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_stats")]
    ])
    
    await call.message.answer(text, reply_markup=keyboard)

@router.callback_query(F.data == "admin_top_balance")
async def admin_top_balance(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    has_access, _, _, _ = check_admin_access(user_id)
    if not has_access:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    await safe_answer(call)
    
    top_users = get_top_balances(20)
    
    if not top_users:
        await call.message.answer("📭 Нет пользователей с балансом")
        return
    
    text = "🏆 <b>ТОП 20 ПО БАЛАНСУ</b>\n\n"
    
    keyboard = []
    for i, user in enumerate(top_users, 1):
        uid = user["user_id"]
        username = user["username"] or "нет username"
        balance = user["balance"]
        
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        text += f"{medal} @{username} — {balance} 🍬\n"
        
        keyboard.append([InlineKeyboardButton(
            text=f"👤 @{username}",
            callback_data=f"admin_user_subscriptions_{uid}"
        )])
    
    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_stats")])
    
    await call.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

@router.callback_query(F.data == "admin_op")
async def admin_op_menu(call: CallbackQuery):
    user_id = call.from_user.id
    has_access, _, _, _ = check_admin_access(user_id)
    if not has_access:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    await safe_answer(call)
    await call.message.answer("🔐 <b>Управление обязательной подпиской</b>", reply_markup=op_menu)

@router.callback_query(F.data == "op_add")
async def op_add_start(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    has_access, _, _, _ = check_admin_access(user_id)
    if not has_access:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    await safe_answer(call)
    await state.set_state(OpStates.waiting_for_channel_id)
    await call.message.answer("📢 <b>Добавление канала в ОП</b>\n\nВведите ID канала (например: -1001234567890) или @username канала:")

@router.message(OpStates.waiting_for_channel_id)
async def process_op_channel_id(message: Message, state: FSMContext):
    user_id = message.from_user.id
    has_access, _, _, _ = check_admin_access(user_id)
    if not has_access:
        return
    channel_id = message.text.strip()
    await state.update_data(channel_id=channel_id)
    await state.set_state(OpStates.waiting_for_channel_name)
    await message.answer("✏️ Введите название канала (для отображения):")

@router.message(OpStates.waiting_for_channel_name)
async def process_op_channel_name(message: Message, state: FSMContext):
    user_id = message.from_user.id
    has_access, _, _, _ = check_admin_access(user_id)
    if not has_access:
        return
    channel_name = message.text.strip()
    await state.update_data(channel_name=channel_name)
    await state.set_state(OpStates.waiting_for_channel_link)
    await message.answer("🔗 Введите ссылку на канал:")

@router.message(OpStates.waiting_for_channel_link)
async def process_op_channel_link(message: Message, state: FSMContext):
    user_id = message.from_user.id
    has_access, _, _, _ = check_admin_access(user_id)
    if not has_access:
        return
    channel_link = message.text.strip()
    data = await state.get_data()
    channel_id = data['channel_id']
    channel_name = data['channel_name']
    if add_mandatory_channel(channel_id, channel_name, channel_link):
        await message.answer(f"✅ Канал {channel_name} добавлен в ОП!")
    else:
        await message.answer("❌ Ошибка при добавлении канала")
    await state.clear()
    await message.answer("👑 Админ-панель", reply_markup=get_admin_menu())

@router.callback_query(F.data == "op_remove")
async def op_remove_menu(call: CallbackQuery):
    user_id = call.from_user.id
    has_access, _, _, _ = check_admin_access(user_id)
    if not has_access:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    await safe_answer(call)
    channels = get_mandatory_channels()
    if not channels:
        await call.message.answer("📭 Нет каналов в ОП")
        return
    keyboard = []
    for ch in channels:
        keyboard.append([InlineKeyboardButton(text=f"❌ {ch['channel_name']}", callback_data=f"op_del_{ch['channel_id']}")])
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_op")])
    await call.message.answer("🗑 <b>Выберите канал для удаления:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

@router.callback_query(F.data.startswith("op_del_"))
async def op_delete_channel(call: CallbackQuery):
    user_id = call.from_user.id
    has_access, _, _, _ = check_admin_access(user_id)
    if not has_access:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    channel_id = call.data.replace("op_del_", "")
    if remove_mandatory_channel(channel_id):
        await safe_answer(call, "✅ Канал удален из ОП!")
    else:
        await safe_answer(call, "❌ Ошибка при удалении")
        return
    channels = get_mandatory_channels()
    if not channels:
        await call.message.edit_text("📭 Нет каналов в ОП")
        return
    keyboard = []
    for ch in channels:
        keyboard.append([InlineKeyboardButton(text=f"❌ {ch['channel_name']}", callback_data=f"op_del_{ch['channel_id']}")])
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_op")])
    await call.message.edit_text("🗑 <b>Выберите канал для удаления:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

@router.callback_query(F.data == "op_list")
async def op_list(call: CallbackQuery):
    user_id = call.from_user.id
    has_access, _, _, _ = check_admin_access(user_id)
    if not has_access:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    await safe_answer(call)
    channels = get_mandatory_channels()
    if not channels:
        text = "📭 Нет каналов в обязательной подписке"
    else:
        text = "📋 <b>Каналы обязательной подписки:</b>\n\n"
        for ch in channels:
            text += f"• <b>{ch['channel_name']}</b>\n  ID: <code>{ch['channel_id']}</code>\n  {ch['channel_link']}\n\n"
    keyboard = [[InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_op")]]
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

@router.callback_query(F.data == "admin_manage")
async def admin_manage_menu_callback(call: CallbackQuery):
    user_id = call.from_user.id
    has_access, _, is_main, can_manage = check_admin_access(user_id, require_manage=True)
    if not has_access:
        await safe_answer(call, "❌ Нет прав для управления админами", show_alert=True)
        return
    await safe_answer(call)
    await call.message.edit_text("👥 <b>Управление админами</b>", reply_markup=admin_manage_menu)

@router.callback_query(F.data == "admin_list")
async def admin_list(call: CallbackQuery):
    user_id = call.from_user.id
    has_access, _, _, _ = check_admin_access(user_id)
    if not has_access:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    await safe_answer(call)
    admins = get_all_admins()
    if not admins:
        await call.message.answer("📭 Нет админов в системе")
        return
    text = "👥 <b>СПИСОК АДМИНОВ</b>\n\n"
    for admin in admins:
        username = admin['current_username'] or admin['username'] or "нет username"
        role = "👑 ГЛАВНЫЙ" if admin['is_main_admin'] else "👤 Админ"
        can_add = "✅ может добавлять" if admin['can_add_admins'] else "❌ не может добавлять"
        added = f"Добавлен: {admin['added_at'][:10]}" if admin['added_at'] else ""
        text += f"{role} | ID: <code>{admin['user_id']}</code>\n"
        text += f"└ @{username} | {can_add}\n"
        if added:
            text += f"└ {added}\n"
        text += "\n"
    keyboard = [[InlineKeyboardButton(text="🔙 Назад", callback_data="admin_manage")]]
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

@router.callback_query(F.data == "admin_add")
async def admin_add_start(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    has_access, _, is_main, can_manage = check_admin_access(user_id, require_manage=True)
    if not has_access:
        await safe_answer(call, "❌ Нет прав для добавления админов", show_alert=True)
        return
    await safe_answer(call)
    await state.set_state(AdminStates.waiting_for_add_admin_id)
    await call.message.answer("➕ <b>Добавление нового админа</b>\n\nВведите ID пользователя Telegram:")

@router.message(AdminStates.waiting_for_add_admin_id)
async def admin_add_id(message: Message, state: FSMContext):
    if not check_admin_access(message.from_user.id)[0]:
        return
    try:
        admin_id = int(message.text.strip())
        await state.update_data(admin_id=admin_id)
        await state.set_state(AdminStates.waiting_for_add_admin_username)
        await message.answer("📝 Введите username админа (можно без @):")
    except ValueError:
        await message.answer("❌ Введите корректный ID (число)")

@router.message(AdminStates.waiting_for_add_admin_username)
async def admin_add_username(message: Message, state: FSMContext):
    if not check_admin_access(message.from_user.id)[0]:
        return
    username = message.text.strip().replace('@', '')
    await state.update_data(username=username)
    await state.set_state(AdminStates.waiting_for_add_admin_permissions)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, может добавлять", callback_data="admin_perm_yes")],
        [InlineKeyboardButton(text="❌ Нет, только обычный", callback_data="admin_perm_no")]
    ])
    await message.answer("🔐 <b>Права админа</b>\n\nРазрешить этому админу добавлять других админов?", reply_markup=keyboard)

@router.callback_query(F.data.startswith("admin_perm_"))
async def admin_add_permissions(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    has_access, _, is_main, _ = check_admin_access(user_id, require_manage=True)
    if not has_access:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    can_add = call.data == "admin_perm_yes"
    data = await state.get_data()
    admin_id = data.get('admin_id')
    username = data.get('username')
    if add_admin(admin_id, username, user_id, can_add):
        await safe_answer(call, "✅ Админ добавлен!")
        await call.message.edit_text(
            f"✅ <b>Админ успешно добавлен!</b>\n\n"
            f"🆔 ID: <code>{admin_id}</code>\n"
            f"👤 Username: @{username}\n"
            f"🔐 Права: {'✅ может добавлять админов' if can_add else '❌ обычный админ'}"
        )
    else:
        await safe_answer(call, "❌ Ошибка при добавлении")
        await call.message.edit_text("❌ Ошибка при добавлении админа")
    await state.clear()
    await call.message.answer("👥 Управление админами", reply_markup=admin_manage_menu)

@router.callback_query(F.data == "admin_remove")
async def admin_remove_menu(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    has_access, _, is_main, can_manage = check_admin_access(user_id, require_manage=True)
    if not has_access:
        await safe_answer(call, "❌ Нет прав для удаления админов", show_alert=True)
        return
    await safe_answer(call)
    admins = get_all_admins()
    if not admins:
        await call.message.answer("📭 Нет админов для удаления")
        return
    keyboard = []
    for admin in admins:
        if admin['is_main_admin']:
            continue
        username = admin['current_username'] or admin['username'] or "нет username"
        keyboard.append([InlineKeyboardButton(text=f"❌ {username} (ID: {admin['user_id']})", callback_data=f"admin_del_{admin['user_id']}")])
    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_manage")])
    await call.message.answer("🗑 <b>Выберите админа для удаления:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

@router.callback_query(F.data.startswith("admin_del_"))
async def admin_delete(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    has_access, _, is_main, can_manage = check_admin_access(user_id, require_manage=True)
    if not has_access:
        await safe_answer(call, "❌ Нет прав для удаления админов", show_alert=True)
        return
    admin_id = int(call.data.replace("admin_del_", ""))
    if remove_admin(admin_id):
        await safe_answer(call, "✅ Админ удален!")
        await call.message.edit_text(f"✅ Админ с ID {admin_id} удален")
    else:
        await safe_answer(call, "❌ Ошибка при удалении")
        await call.message.edit_text("❌ Ошибка при удалении админа")
    await admin_remove_menu(call, state)

@router.message(Command("delete_200"))
async def delete_first_200_command(message: Message):
    user_id = message.from_user.id
    if not is_main_admin(user_id):
        await message.answer("❌ Только для главного админа")
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Да, удалить 200 видео", callback_data="confirm_delete_200"), InlineKeyboardButton(text="❌ Нет, отмена", callback_data="cancel_delete")]])
    await message.answer("⚠️ <b>ВНИМАНИЕ!</b>\n\nТы собираешься удалить первые 200 видео.\nЭто действие нельзя отменить!\n\nПодтверди удаление:", reply_markup=keyboard)

@router.message(Command("delete_58"))
async def delete_first_58_command(message: Message):
    user_id = message.from_user.id
    if not is_main_admin(user_id):
        await message.answer("❌ Только для главного админа")
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Да, удалить 58 видео", callback_data="confirm_delete_58"), InlineKeyboardButton(text="❌ Нет, отмена", callback_data="cancel_delete")]])
    await message.answer("⚠️ <b>ВНИМАНИЕ!</b>\n\nТы собираешься удалить первые 58 видео.\nЭто действие нельзя отменить!\n\nПодтверди удаление:", reply_markup=keyboard)

@router.callback_query(F.data == "confirm_delete_200")
async def confirm_delete_200(call: CallbackQuery):
    user_id = call.from_user.id
    if not is_main_admin(user_id):
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    await safe_answer(call)
    try:
        cursor.execute("SELECT id FROM videos ORDER BY id ASC LIMIT 200")
        videos = cursor.fetchall()
        if not videos:
            await call.message.edit_text("📭 Нет видео для удаления")
            return
        video_ids = [v["id"] for v in videos]
        placeholders = ','.join(['?'] * len(video_ids))
        cursor.execute(f"DELETE FROM user_videos WHERE video_id IN ({placeholders})", video_ids)
        deleted_views = cursor.rowcount
        cursor.execute(f"DELETE FROM videos WHERE id IN ({placeholders})", video_ids)
        deleted_videos = cursor.rowcount
        cursor.execute(f"DELETE FROM video_stats WHERE video_id IN ({placeholders})", video_ids)
        cursor.execute(f"DELETE FROM video_ratings WHERE video_id IN ({placeholders})", video_ids)
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='videos'")
        conn.commit()
        await call.message.edit_text(f"✅ <b>Удаление завершено!</b>\n\n🎥 Удалено видео: {deleted_videos}\n👀 Удалено просмотров: {deleted_views}")
    except Exception as e:
        await call.message.edit_text(f"❌ Ошибка: {e}")

@router.callback_query(F.data == "confirm_delete_58")
async def confirm_delete_58(call: CallbackQuery):
    user_id = call.from_user.id
    if not is_main_admin(user_id):
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    await safe_answer(call)
    try:
        cursor.execute("SELECT id FROM videos ORDER BY id ASC LIMIT 58")
        videos = cursor.fetchall()
        if not videos:
            await call.message.edit_text("📭 Нет видео для удаления")
            return
        video_ids = [v["id"] for v in videos]
        placeholders = ','.join(['?'] * len(video_ids))
        cursor.execute(f"DELETE FROM user_videos WHERE video_id IN ({placeholders})", video_ids)
        deleted_views = cursor.rowcount
        cursor.execute(f"DELETE FROM videos WHERE id IN ({placeholders})", video_ids)
        deleted_videos = cursor.rowcount
        cursor.execute(f"DELETE FROM video_stats WHERE video_id IN ({placeholders})", video_ids)
        cursor.execute(f"DELETE FROM video_ratings WHERE video_id IN ({placeholders})", video_ids)
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='videos'")
        conn.commit()
        await call.message.edit_text(f"✅ <b>Удаление завершено!</b>\n\n🎥 Удалено видео: {deleted_videos}\n👀 Удалено просмотров: {deleted_views}")
    except Exception as e:
        await call.message.edit_text(f"❌ Ошибка: {e}")

@router.callback_query(F.data == "cancel_delete")
async def cancel_delete(call: CallbackQuery):
    await safe_answer(call)
    await call.message.edit_text("❌ Удаление отменено")

@router.message(Command("test_captcha"))
async def test_captcha_command(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if not check_admin_access(user_id)[0]:
        await message.answer("❌ Только для админов")
        return
    image_bytes, captcha_code = generate_captcha_image()
    await message.answer_photo(photo=BufferedInputFile(file=image_bytes, filename="captcha.png"), caption=f"🔐 <b>ТЕСТ КАПЧИ</b>\n\nКод: <code>{captcha_code}</code>\nРазмер: 800x300\nБуквы: 80px")

@router.message(Command("list_promos"))
async def list_promos_command(message: Message):
    user_id = message.from_user.id
    if not check_admin_access(user_id)[0]:
        return
    cursor.execute("SELECT code, reward, activations_left FROM promocodes ORDER BY code")
    promos = cursor.fetchall()
    if not promos:
        await message.answer("📭 Промокодов нет в базе")
        return
    text = "📋 <b>Список промокодов:</b>\n\n"
    for promo in promos:
        text += f"• <code>{promo['code']}</code> | +{promo['reward']} 🍬 | {promo['activations_left']} акт.\n"
    await message.answer(text)

@router.message(Command("balance"))
async def check_balance_command(message: Message):
    user_id = message.from_user.id
    if not check_admin_access(user_id)[0]:
        return
    try:
        args = message.text.split()
        if len(args) > 1:
            target_user_id = int(args[1])
        else:
            target_user_id = message.from_user.id
    except:
        await message.answer("❌ Неверный формат. Используйте: /balance [user_id]")
        return
    cursor.execute("SELECT balance, username FROM users WHERE user_id = ?", (target_user_id,))
    user = cursor.fetchone()
    if not user:
        await message.answer("❌ Пользователь не найден")
        return
    await message.answer(f"👤 Пользователь {target_user_id} (@{user['username'] or 'нет'})\n🍬 Баланс: {user['balance']}")

@router.message(Command("set_me_admin"))
async def set_me_admin(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    
    cursor.execute("SELECT COUNT(*) as count FROM admins WHERE is_main_admin = 1")
    result = cursor.fetchone()
    
    if result["count"] == 0:
        set_main_admin(user_id, username)
        await message.answer(f"✅ Вы установлены как ГЛАВНЫЙ администратор!\nВаш ID: {user_id}")
    else:
        if is_main_admin(user_id):
            await message.answer("✅ Вы уже являетесь главным администратором!")
        else:
            add_admin(user_id, username, user_id, True)
            await message.answer(f"✅ Вы добавлены как администратор!\nВаш ID: {user_id}")

@router.message(Command("remove_admin_by_id"))
async def remove_admin_by_id(message: Message):
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        await message.answer("❌ Нет доступа! Только администраторы могут удалять админов.")
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Укажите ID админа для удаления.\nПример: `/remove_admin_by_id 123456789`", parse_mode="Markdown")
        return
    
    try:
        target_id = int(args[1])
    except ValueError:
        await message.answer("❌ ID должен быть числом!")
        return
    
    if target_id == user_id:
        await message.answer("❌ Вы не можете удалить сами себя!")
        return
    
    cursor.execute("SELECT user_id, username, is_main_admin FROM admins WHERE user_id = ?", (target_id,))
    admin = cursor.fetchone()
    
    if not admin:
        await message.answer(f"❌ Пользователь с ID {target_id} не является админом!")
        return
    
    if admin["is_main_admin"] == 1:
        cursor.execute("SELECT COUNT(*) as count FROM admins WHERE is_main_admin = 1")
        main_admins_count = cursor.fetchone()["count"]
        
        if main_admins_count == 1:
            await message.answer(
                f"⚠️ <b>ВНИМАНИЕ!</b>\n\n"
                f"Вы собираетесь удалить ЕДИНСТВЕННОГО главного администратора.\n"
                f"После этого в системе не останется главных админов.\n\n"
                f"Для подтверждения отправьте: `/confirm_remove_main {target_id}`",
                parse_mode="Markdown"
            )
            return
        else:
            cursor.execute("DELETE FROM admins WHERE user_id = ?", (target_id,))
            cursor.execute("UPDATE users SET is_admin = 0 WHERE user_id = ?", (target_id,))
            conn.commit()
            await message.answer(f"✅ Главный админ с ID {target_id} удалён!")
        return
    
    cursor.execute("DELETE FROM admins WHERE user_id = ?", (target_id,))
    cursor.execute("UPDATE users SET is_admin = 0 WHERE user_id = ?", (target_id,))
    conn.commit()
    await message.answer(f"✅ Админ с ID {target_id} удалён!")

@router.message(Command("confirm_remove_main"))
async def confirm_remove_main(message: Message):
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        await message.answer("❌ Нет доступа!")
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Укажите ID главного админа для удаления.")
        return
    
    try:
        target_id = int(args[1])
    except ValueError:
        await message.answer("❌ ID должен быть числом!")
        return
    
    cursor.execute("SELECT user_id, username FROM admins WHERE user_id = ? AND is_main_admin = 1", (target_id,))
    admin = cursor.fetchone()
    
    if not admin:
        await message.answer(f"❌ Пользователь с ID {target_id} не является главным админом!")
        return
    
    cursor.execute("DELETE FROM admins WHERE user_id = ?", (target_id,))
    cursor.execute("UPDATE users SET is_admin = 0 WHERE user_id = ?", (target_id,))
    conn.commit()
    
    if target_id == user_id:
        await message.answer(f"✅ Вы удалили себя как главного администратора!\nТеперь вы не админ.")
    else:
        await message.answer(f"✅ Главный админ с ID {target_id} удалён!")

@router.message(Command("set_main_admin"))
async def set_main_admin_command(message: Message):
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        await message.answer("❌ Нет доступа! Только администраторы могут назначать главного админа.")
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Укажите ID нового главного админа.\nПример: `/set_main_admin 993076067`", parse_mode="Markdown")
        return
    
    try:
        new_main_id = int(args[1])
    except ValueError:
        await message.answer("❌ ID должен быть числом!")
        return
    
    cursor.execute("SELECT user_id, username FROM users WHERE user_id = ?", (new_main_id,))
    user = cursor.fetchone()
    
    if not user:
        await message.answer(f"❌ Пользователь с ID {new_main_id} не найден в базе!")
        return
    
    username = user["username"] or ""
    
    cursor.execute("UPDATE admins SET is_main_admin = 0")
    
    cursor.execute("""
        INSERT OR REPLACE INTO admins (user_id, username, added_by, added_at, is_main_admin, can_add_admins)
        VALUES (?, ?, ?, datetime('now'), 1, 1)
    """, (new_main_id, username, user_id))
    
    cursor.execute("UPDATE users SET is_admin = 1 WHERE user_id = ?", (new_main_id,))
    conn.commit()
    
    await message.answer(
        f"✅ <b>Главный администратор изменён!</b>\n\n"
        f"👑 Новый главный админ: ID <code>{new_main_id}</code> (@{username if username else 'нет username'})\n"
    )
    
    try:
        await message.bot.send_message(
            new_main_id,
            f"👑 <b>Поздравляем!</b>\n\n"
            f"Вы назначены главным администратором бота!\n"
            f"Вам доступны все функции управления."
        )
    except:
        pass

# ================= НОВЫЕ КЛАССЫ СОСТОЯНИЙ =================
class MirrorStates(StatesGroup):
    waiting_for_token = State()

class CreateAutoTaskStates(StatesGroup):
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_reward = State()
    waiting_for_max_completions = State()
    waiting_for_category = State()

class AdminAutoTaskStates(StatesGroup):
    waiting_for_task_id_to_delete = State()

# ================= НОВЫЕ ХЭНДЛЕРЫ ЗЕРКАЛ =================
@router.callback_query(F.data == "mirror_menu")
async def mirror_menu(call: CallbackQuery, state: FSMContext, bot: Bot):
    uid = call.from_user.id
    if await check_spam(uid): await safe_answer(call, get_text(uid, "spam_warning"), True); return
    if not await check_access(bot, uid, state, call=call): return
    await safe_answer(call)
    await call.message.answer(get_mirror_info_text(), reply_markup=get_mirror_menu(uid))

@router.callback_query(F.data == "mirror_info")
async def mirror_info(call: CallbackQuery, state: FSMContext, bot: Bot):
    uid = call.from_user.id
    if await check_spam(uid): await safe_answer(call, get_text(uid, "spam_warning"), True); return
    if not await check_access(bot, uid, state, call=call): return
    await safe_answer(call)
    await call.message.answer(get_mirror_info_text())

@router.callback_query(F.data == "mirror_create")
async def mirror_create_start(call: CallbackQuery, state: FSMContext, bot: Bot):
    uid = call.from_user.id
    if await check_spam(uid): await safe_answer(call, get_text(uid, "spam_warning"), True); return
    if not await check_access(bot, uid, state, call=call): return
    if len(get_user_mirror_bots_db(uid)) >= MAX_MIRRORS_PER_USER:
        await safe_answer(call, get_text(uid, "mirror_limit_reached"), True)
        return
    await state.set_state(MirrorStates.waiting_for_token)
    await safe_answer(call)
    await call.message.answer(get_mirror_create_instruction())

@router.message(MirrorStates.waiting_for_token)
async def mirror_create_token(message: Message, state: FSMContext, bot: Bot):
    uid = message.from_user.id
    token = message.text.strip()
    if len(get_user_mirror_bots_db(uid)) >= MAX_MIRRORS_PER_USER:
        await message.answer(get_text(uid, "mirror_limit_reached"))
        await state.clear()
        return
    if get_mirror_bot_by_token_db(token):
        await message.answer(get_text(uid, "mirror_already_exists"))
        await state.clear()
        return
    sm = await message.answer("🔄 Проверяю токен...")
    try:
        from aiogram import Bot
        tb = Bot(token=token)
        me = await tb.get_me()
        await tb.session.close()
        success, result = add_mirror_bot_by_user(token, me.username, uid)
        if success:
            await start_mirror_bot(token, me.username)
            await sm.delete()
            await message.answer(get_text(uid, "mirror_created").format(me.username, result))
        else:
            await sm.edit_text(get_text(uid, "mirror_create_error").format(result))
    except:
        await sm.edit_text(get_text(uid, "mirror_invalid_token"))
    await state.clear()

@router.callback_query(F.data == "mirror_my_list")
async def mirror_my_list(call: CallbackQuery, state: FSMContext, bot: Bot):
    uid = call.from_user.id
    if await check_spam(uid): await safe_answer(call, get_text(uid, "spam_warning"), True); return
    if not await check_access(bot, uid, state, call=call): return
    mirrors = get_user_mirror_bots_db(uid)
    if not mirrors:
        await safe_answer(call, get_text(uid, "mirror_no_mirrors"), True)
        return
    await safe_answer(call)
    await call.message.answer("🪞 <b>ВАШИ ЗЕРКАЛА</b>", reply_markup=get_my_mirrors_keyboard(mirrors, uid))

@router.callback_query(F.data.startswith("mirror_details_"))
async def mirror_details(call: CallbackQuery, state: FSMContext, bot: Bot):
    uid = call.from_user.id
    mid = int(call.data.replace("mirror_details_", ""))
    m = get_mirror_bot_by_id(mid)
    if not m or m["added_by"] != uid:
        await safe_answer(call, get_text(uid, "mirror_not_found"), True)
        return
    status = get_text(uid, "mirror_status_active") if m["is_active"] else get_text(uid, "mirror_status_inactive")
    un = m["bot_username"] or "без юзернейма"
    ca = m["added_at"][:16] if m["added_at"] else "?"
    txt = f"🪞 <b>ДЕТАЛИ ЗЕРКАЛА</b>\n\n{status}\n🤖 @{un}\n🆔 ID: {m['id']}\n📅 Создано: {ca}\n🔗 https://t.me/{un}"
    await safe_answer(call)
    await call.message.answer(txt, reply_markup=get_mirror_details_keyboard(m, uid))

@router.callback_query(F.data.startswith("mirror_start_"))
async def mirror_start(call: CallbackQuery, state: FSMContext, bot: Bot):
    uid = call.from_user.id
    mid = int(call.data.replace("mirror_start_", ""))
    m = get_mirror_bot_by_id(mid)
    if not m or m["added_by"] != uid:
        await safe_answer(call, get_text(uid, "mirror_not_found"), True)
        return
    if toggle_mirror_bot_db(mid, True):
        await start_mirror_bot(m["bot_token"], m["bot_username"])
        await safe_answer(call, get_text(uid, "mirror_started"), True)
        await mirror_details(call, state, bot)
    else:
        await safe_answer(call, get_text(uid, "error"), True)

@router.callback_query(F.data.startswith("mirror_stop_"))
async def mirror_stop(call: CallbackQuery, state: FSMContext, bot: Bot):
    uid = call.from_user.id
    mid = int(call.data.replace("mirror_stop_", ""))
    m = get_mirror_bot_by_id(mid)
    if not m or m["added_by"] != uid:
        await safe_answer(call, get_text(uid, "mirror_not_found"), True)
        return
    if toggle_mirror_bot_db(mid, False):
        await stop_mirror_bot(m["bot_token"])
        await safe_answer(call, get_text(uid, "mirror_stopped"), True)
        await mirror_details(call, state, bot)
    else:
        await safe_answer(call, get_text(uid, "error"), True)

@router.callback_query(F.data.startswith("mirror_restart_"))
async def mirror_restart(call: CallbackQuery, state: FSMContext, bot: Bot):
    uid = call.from_user.id
    mid = int(call.data.replace("mirror_restart_", ""))
    m = get_mirror_bot_by_id(mid)
    if not m or m["added_by"] != uid:
        await safe_answer(call, get_text(uid, "mirror_not_found"), True)
        return
    await stop_mirror_bot(m["bot_token"])
    await asyncio.sleep(1)
    await start_mirror_bot(m["bot_token"], m["bot_username"])
    await safe_answer(call, get_text(uid, "mirror_restarted"), True)

@router.callback_query(F.data.startswith("mirror_delete_"))
async def mirror_delete(call: CallbackQuery, state: FSMContext, bot: Bot):
    uid = call.from_user.id
    mid = int(call.data.replace("mirror_delete_", ""))
    m = get_mirror_bot_by_id(mid)
    if not m or m["added_by"] != uid:
        await safe_answer(call, get_text(uid, "mirror_not_found"), True)
        return
    await stop_mirror_bot(m["bot_token"])
    if remove_mirror_bot_by_user(mid, uid):
        await safe_answer(call, get_text(uid, "mirror_deleted"), True)
        await call.message.delete()
    else:
        await safe_answer(call, get_text(uid, "error"), True)

# ================= АДМИН - УПРАВЛЕНИЕ ЗЕРКАЛАМИ =================
@router.callback_query(F.data == "admin_mirrors")
async def admin_mirrors_menu(call: CallbackQuery):
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", True)
        return
    mirrors = get_all_mirror_bots(include_main=True)
    txt = "🪞 <b>УПРАВЛЕНИЕ ЗЕРКАЛАМИ</b>\n\n"
    for m in mirrors:
        st = "✅" if m["is_active"] else "❌"
        mt = " 👑 ГЛАВНЫЙ" if m["is_main"] else ""
        txt += f"{st} @{m['bot_username'] or '?'}{mt}\n   ID: {m['id']}\n   Токен: {m['bot_token'][:15]}...\n"
    await call.message.answer(txt, reply_markup=get_mirrors_admin_menu())

@router.callback_query(F.data == "mirror_add")
async def admin_mirror_add(call: CallbackQuery, state: FSMContext):
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", True)
        return
    await state.set_state(AdminStates.waiting_for_mirror_token)
    await safe_answer(call)
    await call.message.answer("➕ Введите токен бота-зеркала:")

@router.message(AdminStates.waiting_for_mirror_token)
async def admin_mirror_add_token(m: Message, state: FSMContext):
    if not check_admin_access(m.from_user.id)[0]: return
    token = m.text.strip()
    try:
        from aiogram import Bot
        tb = Bot(token=token)
        me = await tb.get_me()
        await tb.session.close()
        if add_mirror_bot_db(token, me.username, m.from_user.id):
            await start_mirror_bot(token, me.username)
            await m.answer(f"✅ Зеркало @{me.username} добавлено!")
        else:
            await m.answer("❌ Ошибка")
    except:
        await m.answer("❌ Неверный токен")
    await state.clear()

@router.callback_query(F.data == "mirror_list")
async def admin_mirror_list(call: CallbackQuery):
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", True)
        return
    mirrors = get_all_mirror_bots(include_main=True)
    if not mirrors:
        await call.message.answer("📭 Нет зеркал")
        return
    txt = "🪞 <b>СПИСОК ЗЕРКАЛ</b>\n\n"
    for m in mirrors:
        st = "✅" if m["is_active"] else "❌"
        mt = " 👑" if m["is_main"] else ""
        txt += f"{st} @{m['bot_username'] or '?'}{mt}\n   ID: {m['id']}\n   Токен: <code>{m['bot_token'][:20]}...</code>\n\n"
    await call.message.answer(txt)

@router.callback_query(F.data == "mirror_delete_select")
async def admin_mirror_delete_select(call: CallbackQuery):
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", True)
        return
    mirrors = get_all_mirror_bots(include_main=False)
    if not mirrors:
        await call.message.answer("📭 Нет зеркал")
        return
    kb = []
    for m in mirrors:
        kb.append([InlineKeyboardButton(text=f"❌ @{m['bot_username'] or m['id']}", callback_data=f"mirror_del_{m['id']}")])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_mirrors")])
    await call.message.answer("🗑 Выберите зеркало:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data.startswith("mirror_del_"))
async def admin_mirror_delete(call: CallbackQuery):
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", True)
        return
    mid = int(call.data.replace("mirror_del_", ""))
    m = get_mirror_bot_by_id(mid)
    if not m:
        await safe_answer(call, "❌ Не найдено", True)
        return
    await stop_mirror_bot(m["bot_token"])
    if remove_mirror_bot_db(mid):
        await safe_answer(call, "✅ Удалено", True)
        await call.message.delete()
    else:
        await safe_answer(call, "❌ Ошибка", True)

@router.callback_query(F.data == "mirror_restart")
async def admin_mirror_restart_all(call: CallbackQuery):
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", True)
        return
    await safe_answer(call, "🔄 Перезапуск...")
    await stop_all_mirror_bots()
    await asyncio.sleep(2)
    await start_all_mirror_bots()
    await call.message.answer("✅ Все зеркала перезапущены")

# ================= АВТО-ЗАДАНИЯ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ =================
@router.callback_query(F.data == "auto_tasks")
async def auto_tasks_menu(call: CallbackQuery, state: FSMContext, bot: Bot):
    uid = call.from_user.id
    if await check_spam(uid): await safe_answer(call, get_text(uid, "spam_warning"), True); return
    if not await check_access(bot, uid, state, call=call): return
    await safe_answer(call)
    await call.message.answer("🤖 <b>АВТО-ЗАДАНИЯ</b>\n\nНаграда начисляется автоматически!", reply_markup=get_auto_categories_menu(uid))

@router.callback_query(F.data.startswith("auto_tasks_category_"))
async def auto_tasks_category(call: CallbackQuery, state: FSMContext, bot: Bot):
    uid = call.from_user.id
    if await check_spam(uid): await safe_answer(call, get_text(uid, "spam_warning"), True); return
    if not await check_access(bot, uid, state, call=call): return
    cat = call.data.replace("auto_tasks_category_", "")
    await safe_answer(call)
    tasks = get_auto_tasks_by_category(cat)
    if not tasks:
        await call.message.answer("📭 Нет заданий")
        return
    ut = []
    for t in tasks:
        s = get_user_auto_task_status(uid, t["id"])
        t["completed"] = 1 if s and s.get("status") == "completed" else 0
        t["max_completions"] = t.get("max_completions", 1)
        ut.append(t)
    await call.message.answer(f"🤖 <b>АВТО-ЗАДАНИЯ</b>\n\n{cat}", reply_markup=get_auto_tasks_menu_by_category(ut, cat, uid))

@router.callback_query(F.data.startswith("auto_task_"))
async def auto_task_detail(call: CallbackQuery, state: FSMContext, bot: Bot):
    uid = call.from_user.id
    if await check_spam(uid): await safe_answer(call, get_text(uid, "spam_warning"), True); return
    if not await check_access(bot, uid, state, call=call): return
    tid = int(call.data.split("_")[2])
    t = get_auto_task(tid)
    if not t:
        await safe_answer(call, "❌ Не найдено", True)
        return
    s = get_user_auto_task_status(uid, tid)
    comp = 1 if s and s.get("status") == "completed" else 0
    txt = f"🤖 <b>{t['title']}</b>\n\n{t['description']}\n\n🎁 +{t['reward']} 🍬\n📊 {comp}/{t['max_completions']}\n\n📸 Отправьте скриншот!"
    if comp < t['max_completions']:
        await call.message.answer(txt, reply_markup=get_auto_task_action_menu(tid, t['title'], t['reward'], uid))
    else:
        await call.message.answer(txt + "\n\n✅ Выполнено!")

@router.callback_query(F.data.startswith("do_auto_task_"))
async def do_auto_task(call: CallbackQuery, state: FSMContext, bot: Bot):
    uid = call.from_user.id
    if await check_spam(uid): await safe_answer(call, get_text(uid, "spam_warning"), True); return
    if not await check_access(bot, uid, state, call=call): return
    tid = int(call.data.split("_")[3])
    t = get_auto_task(tid)
    if not t:
        await safe_answer(call, "❌ Не найдено", True)
        return
    s = get_user_auto_task_status(uid, tid)
    comp = 1 if s and s.get("status") == "completed" else 0
    if comp >= t['max_completions']:
        await safe_answer(call, "❌ Лимит выполнений", True)
        return
    if s and s.get("status") == "pending":
        await safe_answer(call, "⏳ Уже на проверке", True)
        return
    await state.update_data(auto_task_id=tid)
    await state.set_state(TaskStates.waiting_for_task_photo)
    await safe_answer(call)
    await call.message.answer(f"🤖 <b>{t['title']}</b>\n\n{t['description']}\n\n📸 Отправьте скриншот!\n\n✅ Награда начислится автоматически!")

# ================= АДМИН - УПРАВЛЕНИЕ АВТО-ЗАДАНИЯМИ =================
@router.callback_query(F.data == "admin_auto_tasks")
async def admin_auto_tasks_menu(call: CallbackQuery):
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", True)
        return
    await safe_answer(call)
    await call.message.answer("🤖 <b>УПРАВЛЕНИЕ АВТО-ЗАДАНИЯМИ</b>", reply_markup=admin_auto_tasks_keyboard)

@router.callback_query(F.data == "admin_auto_task_add")
async def admin_auto_task_add_start(call: CallbackQuery, state: FSMContext):
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", True)
        return
    await safe_answer(call)
    await state.set_state(CreateAutoTaskStates.waiting_for_title)
    await call.message.answer("📝 Название:")

@router.message(CreateAutoTaskStates.waiting_for_title)
async def admin_auto_task_title(m: Message, state: FSMContext):
    if not check_admin_access(m.from_user.id)[0]: return
    await state.update_data(title=m.text)
    await state.set_state(CreateAutoTaskStates.waiting_for_description)
    await m.answer("📄 Описание:")

@router.message(CreateAutoTaskStates.waiting_for_description)
async def admin_auto_task_desc(m: Message, state: FSMContext):
    if not check_admin_access(m.from_user.id)[0]: return
    await state.update_data(description=m.text)
    await state.set_state(CreateAutoTaskStates.waiting_for_reward)
    await m.answer("🎁 Награда:")

@router.message(CreateAutoTaskStates.waiting_for_reward)
async def admin_auto_task_reward(m: Message, state: FSMContext):
    if not check_admin_access(m.from_user.id)[0]: return
    try:
        r = int(m.text)
        if r <= 0: await m.answer("❌ >0"); return
        await state.update_data(reward=r)
        await state.set_state(CreateAutoTaskStates.waiting_for_max_completions)
        await m.answer("📊 Макс. выполнений (1-999):")
    except: await m.answer("❌ Число")

@router.message(CreateAutoTaskStates.waiting_for_max_completions)
async def admin_auto_task_max(m: Message, state: FSMContext):
    if not check_admin_access(m.from_user.id)[0]: return
    try:
        mc = int(m.text.strip())
        if mc < 1: mc = 1
        if mc > 999: mc = 999
        await state.update_data(max_completions=mc)
        await state.set_state(CreateAutoTaskStates.waiting_for_category)
        await m.answer("📂 Категория:", reply_markup=auto_task_category_keyboard)
    except: await m.answer("❌ Число")

@router.callback_query(F.data.startswith("admin_auto_task_category_"))
async def admin_auto_task_category(call: CallbackQuery, state: FSMContext):
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", True)
        return
    cat = call.data.replace("admin_auto_task_category_", "")
    d = await state.get_data()
    tid = add_auto_task(
        title=d.get("title"), description=d.get("description"), reward=d.get("reward"),
        category=cat, max_completions=d.get("max_completions", 1), auto_verify=True
    )
    if tid: await call.message.answer(f"✅ Авто-задание {d.get('title')} создано! ID: {tid}")
    else: await call.message.answer("❌ Ошибка")
    await state.clear()

@router.callback_query(F.data == "admin_auto_task_list")
async def admin_auto_task_list(call: CallbackQuery):
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", True)
        return
    tasks = get_auto_tasks()
    if not tasks:
        await call.message.answer("📭 Нет заданий")
        return
    txt = "🤖 <b>АВТО-ЗАДАНИЯ</b>\n\n"
    for t in tasks: txt += f"🆔 {t['id']} | {t['title']} | +{t['reward']} 🍬\n"
    await call.message.answer(txt)

@router.callback_query(F.data == "admin_auto_task_remove")
async def admin_auto_task_remove_start(call: CallbackQuery, state: FSMContext):
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", True)
        return
    await state.set_state(AdminAutoTaskStates.waiting_for_task_id_to_delete)
    await call.message.answer("🗑 Введите ID авто-задания:")

@router.message(AdminAutoTaskStates.waiting_for_task_id_to_delete)
async def admin_auto_task_remove(m: Message, state: FSMContext):
    if not check_admin_access(m.from_user.id)[0]: return
    try:
        tid = int(m.text.strip())
        if remove_auto_task(tid): await m.answer(f"✅ Задание {tid} удалено")
        else: await m.answer("❌ Ошибка")
    except: await m.answer("❌ Введите число")
    await state.clear()

@router.callback_query(F.data == "admin_auto_task_pending")
async def admin_auto_task_pending(call: CallbackQuery):
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", True)
        return
    pending = get_pending_auto_tasks()
    if not pending:
        await call.message.answer("📭 Нет на проверке")
        return
    txt = "⏳ <b>АВТО-ЗАДАНИЯ НА ПРОВЕРКЕ</b>\n\n"
    for p in pending: txt += f"👤 @{p['username']} (ID:{p['user_id']})\n🤖 {p['title']} | +{p['reward']} 🍬\n📄 {p['proof'][:100]}...\n\n"
    await call.message.answer(txt)

@router.callback_query(F.data == "admin_auto_task_categories")
async def admin_auto_task_categories(call: CallbackQuery):
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", True)
        return
    await call.message.answer("📂 <b>КАТЕГОРИИ АВТО-ЗАДАНИЙ</b>", reply_markup=get_auto_category_management_menu())

@router.callback_query(F.data.startswith("admin_auto_category_"))
async def admin_auto_category_tasks(call: CallbackQuery):
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", True)
        return
    cat = call.data.replace("admin_auto_category_", "")
    tasks = get_auto_tasks_by_category(cat)
    if not tasks:
        await call.message.answer(f"📭 В категории нет заданий")
        return
    await call.message.answer(f"📂 <b>{TASK_CATEGORIES.get(cat,{}).get('name',cat)}</b>", reply_markup=get_auto_tasks_by_category_menu(tasks, cat))

@router.callback_query(F.data.startswith("admin_auto_move_task_"))
async def admin_auto_move_task_select(call: CallbackQuery):
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", True)
        return
    p = call.data.split("_")
    tid = int(p[4])
    cur_cat = p[5]
    t = get_auto_task(tid)
    if not t:
        await call.message.answer("❌ Не найдено")
        return
    await call.message.answer(f"🤖 <b>{t['title']}</b>\n\nТекущая: {TASK_CATEGORIES.get(cur_cat,{}).get('name',cur_cat)}", reply_markup=get_move_auto_category_menu(tid))

@router.callback_query(F.data.startswith("admin_auto_move_to_"))
async def admin_auto_move_task(call: CallbackQuery):
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", True)
        return
    p = call.data.split("_")
    nc = p[4]
    tid = int(p[5])
    if update_auto_task(tid, category=nc):
        await safe_answer(call, f"✅ Перенесено!")
        await call.message.edit_text(f"✅ Задание {tid} -> {TASK_CATEGORIES.get(nc,{}).get('name',nc)}")
    else:
        await safe_answer(call, "❌ Ошибка", True)

@router.callback_query(F.data == "admin_auto_manage_requests")
async def admin_auto_manage_requests(call: CallbackQuery):
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", True)
        return
    pending = get_pending_auto_tasks()
    if not pending:
        await call.message.answer("📭 Нет заявок")
        return
    await call.message.answer("🗑 <b>ЗАЯВКИ АВТО-ЗАДАНИЙ</b>", reply_markup=get_auto_requests_menu(pending))

@router.callback_query(F.data.startswith("admin_view_auto_request_"))
async def admin_view_auto_request(call: CallbackQuery, bot: Bot):
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", True)
        return
    rid = int(call.data.replace("admin_view_auto_request_", ""))
    r = get_auto_task_record_by_id(rid)
    if not r:
        await safe_answer(call, "❌ Заявка не найдена", True)
        return
    txt = f"🤖 <b>ДЕТАЛИ ЗАЯВКИ</b>\n\n👤 @{r['username']} (ID:{r['user_id']})\n📝 {r['title']}\n🎁 +{r['reward']} 🍬\n📄 {r['proof']}"
    if "Скриншот:" in r['proof']:
        fid = r['proof'].split("Скриншот: ")[1].split("\n")[0]
        await bot.send_photo(call.from_user.id, photo=fid, caption=txt, reply_markup=get_auto_request_action_menu(rid, r['title'], r['username'], r['user_id'], r['task_id'], r['reward'], r['proof']))
    else:
        await call.message.answer(txt, reply_markup=get_auto_request_action_menu(rid, r['title'], r['username'], r['user_id'], r['task_id'], r['reward'], r['proof']))

@router.callback_query(F.data.startswith("admin_approve_auto_request_"))
async def admin_approve_auto_request(call: CallbackQuery, bot: Bot):
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", True)
        return
    p = call.data.split("_")
    rid = int(p[4])
    uid = int(p[5])
    reward = int(p[7])
    if approve_auto_task(rid, reward):
        await safe_answer(call, "✅ Одобрено")
        await call.message.delete()
        try: await bot.send_message(uid, f"✅ Авто-задание одобрено! +{reward} 🍬")
        except: pass
    else:
        await safe_answer(call, "❌ Ошибка", True)

@router.callback_query(F.data.startswith("admin_reject_auto_request_"))
async def admin_reject_auto_request(call: CallbackQuery, bot: Bot):
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", True)
        return
    p = call.data.split("_")
    rid = int(p[4])
    uid = int(p[5])
    if reject_auto_task(rid):
        await safe_answer(call, "❌ Отклонено")
        await call.message.delete()
        try: await bot.send_message(uid, "❌ Авто-задание отклонено")
        except: pass
    else:
        await safe_answer(call, "❌ Ошибка", True)

@router.callback_query(F.data.startswith("admin_delete_auto_request_"))
async def admin_delete_auto_request(call: CallbackQuery):
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", True)
        return
    p = call.data.split("_")
    rid = int(p[4])
    if delete_auto_task_record_by_id(rid):
        await safe_answer(call, "✅ Удалено", True)
        await call.message.edit_text("✅ Заявка удалена")
    else:
        await safe_answer(call, "❌ Ошибка", True)

def get_main_router_for_mirror():
    """Создаёт роутер для зеркал (копирует все хэндлеры из основного роутера)"""
    from aiogram import Router
    
    mirror_router = Router()
    
    # Копируем все message handlers
    for handler in router.message.handlers:
        try:
            mirror_router.message.register(handler.callback, *handler.filters)
        except:
            pass
    
    # Копируем все callback_query handlers
    for handler in router.callback_query.handlers:
        try:
            mirror_router.callback_query.register(handler.callback, *handler.filters)
        except:
            pass
    
    return mirror_router

