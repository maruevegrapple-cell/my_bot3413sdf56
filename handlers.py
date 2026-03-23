import asyncio
import time
import random
import logging
import io
import string
import os
import requests
import traceback
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont, ImageFilter

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
    get_top_referrers, add_payment, mark_payment_paid, get_payment,
    add_promo_code, get_promo_code, use_promo_code, check_promo_used,
    update_last_bonus, add_video, mark_video_watched, get_user_watched_videos,
    get_all_tasks, get_task, add_task, delete_task,
    get_user_task_status, submit_task, approve_task, reject_task,
    get_user_completed_tasks, get_pending_submissions, get_tasks_stats,
    has_private_access, grant_private_access
)
from keyboards import (
    fake_menu, main_menu, video_menu, shop_menu, get_admin_menu, 
    confirm_menu, subscribe_menu, op_menu, admin_manage_menu,
    get_tasks_menu, get_task_action_menu, admin_tasks_menu
)
from payments import (
    create_invoice, 
    check_invoice, 
    AVAILABLE_ASSETS, 
    get_asset_icon,
    get_exchange_rates
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = Router()

# Временная директория для видео
TEMP_DIR = "temp_videos"
os.makedirs(TEMP_DIR, exist_ok=True)

# ================= НАГРАДА ЗА ПРЕДЛОЖКУ =================
SUGGESTION_REWARD = 3

# Хранилище предложенных видео
suggested_videos = {}
# Множество пользователей в режиме предложки
suggestion_mode = set()

# ================= FSM СОСТОЯНИЯ =================
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

class CaptchaStates(StatesGroup):
    waiting_for_captcha = State()

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

# ================= FSM ДЛЯ ЗАДАНИЙ =================
class TaskStates(StatesGroup):
    waiting_for_task_title = State()
    waiting_for_task_desc = State()
    waiting_for_task_reward = State()
    waiting_for_task_type = State()
    waiting_for_task_content = State()
    waiting_for_task_submit = State()

# ================= ХРАНИЛИЩЕ ДАННЫХ =================
captcha_data = {}
captcha_attempts = {}
banned_users = {}
broadcast_mode = set()
custom_pay_wait = set()
waiting_for_restore_file = False
restore_user_id = None
task_submissions = {}
task_submission_counter = 0

# ================= КОМАНДА ДЛЯ НАЗНАЧЕНИЯ ГЛАВНОГО АДМИНА =================
@router.message(Command("set_main_admin"))
async def set_main_admin_command(message: Message):
    """Устанавливает главного админа (только если его еще нет)"""
    user_id = message.from_user.id
    username = message.from_user.username or "пользователь"
    
    current_main = get_main_admin_id()
    
    if current_main:
        await message.answer(f"❌ Главный админ уже установлен: ID {current_main}")
        return
    
    result = set_main_admin(user_id, username)
    
    if result:
        await message.answer(
            f"✅ <b>Вы назначены главным админом!</b>\n\n"
            f"👑 Теперь у вас есть полный доступ ко всем функциям бота.\n"
            f"🆔 Ваш ID: <code>{user_id}</code>"
        )
        logger.info(f"👑 Главный админ установлен: {user_id} (@{username})")
    else:
        await message.answer("❌ Ошибка при назначении главного админа")

# ================= ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =================
def is_banned(user_id: int) -> tuple:
    """Проверка на бан"""
    if user_id in banned_users:
        ban_until = banned_users[user_id]
        if datetime.now() < ban_until:
            return True, ban_until
        else:
            del banned_users[user_id]
    return False, None

async def check_subscription(bot, user_id: int) -> bool:
    """Проверка подписки на канал"""
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status not in ["left", "kicked"]
    except Exception as e:
        logger.error(f"Error checking subscription: {e}")
        return False

def has_referrer(user_id: int) -> bool:
    """Проверка, пришел ли пользователь по реф ссылке"""
    cursor.execute("SELECT referrer FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    return row and row["referrer"] is not None

def is_verified(user_id: int) -> bool:
    """Проверка верификации"""
    cursor.execute("SELECT is_verified FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    return row and row["is_verified"] == 1

def generate_ref_code(length=6):
    """Генерация уникального реферального кода"""
    chars = string.ascii_uppercase + string.digits
    chars = chars.replace('O', '').replace('0', '').replace('I', '').replace('1', '')
    
    while True:
        code = ''.join(random.choices(chars, k=length))
        cursor.execute("SELECT user_id FROM users WHERE ref_code = ?", (code,))
        if not cursor.fetchone():
            return code

# ================= ФУНКЦИЯ ПРОВЕРКИ ПРАВ АДМИНА =================
def check_admin_access(user_id: int, require_main: bool = False, require_manage: bool = False) -> tuple:
    """
    Проверка прав доступа админа
    Возвращает (has_access, is_admin, is_main, can_manage)
    """
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

# ================= БЕЗОПАСНЫЕ ФУНКЦИИ ДЛЯ CALLBACK =================
async def safe_answer(call: CallbackQuery, text: str = None, show_alert: bool = False):
    """Безопасный ответ на callback query"""
    try:
        if text:
            await call.answer(text, show_alert=show_alert)
        else:
            await call.answer()
    except Exception as e:
        logger.error(f"Error in safe_answer: {e}")

# ================= ФУНКЦИЯ ДЛЯ ПРОВЕРКИ ДОСТУПА =================
async def check_access(bot, user_id: int, state: FSMContext, message: Message = None, call: CallbackQuery = None) -> bool:
    """Проверяет доступ пользователя и показывает меню подписки если нужно"""
    if check_admin_access(user_id)[0]:
        return True
    
    if not is_verified(user_id):
        if message:
            await message.answer("❌ Сначала пройдите верификацию")
        elif call:
            await safe_answer(call, "❌ Сначала пройдите верификацию", show_alert=True)
        return False
    
    is_subscribed = await check_subscription(bot, user_id)
    if not is_subscribed:
        await state.set_state(SubscribeStates.waiting_for_subscribe)
        if message:
            await message.answer(
                f"<b>🥰 Для доступа к боту нужно подписаться на канал!</b>\n\n"
                f"— ведь за подписку мы дарим каждый день по {SUBSCRIBE_BONUS} 🍬!",
                reply_markup=subscribe_menu
            )
        elif call:
            await call.message.answer(
                f"<b>🥰 Для доступа к боту нужно подписаться на канал!</b>\n\n"
                f"— ведь за подписку мы дарим каждый день по {SUBSCRIBE_BONUS} 🍬!",
                reply_markup=subscribe_menu
            )
        return False
    
    return True

# ================= ГЕНЕРАЦИЯ КАПЧИ =================
def generate_captcha_image() -> tuple:
    """Генерация изображения капчи"""
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

# ================= БЛОКИРОВКА ПЕРЕСЫЛКИ =================
@router.message(F.forward_from | F.forward_from_chat)
async def block_forward(message: Message):
    await message.delete()

# ================= ЗАГРУЗКА ВИДЕО =================
@router.message(F.video)
async def handle_video(message: Message, bot: Bot):
    user_id = message.from_user.id
    has_access, _, _, _ = check_admin_access(user_id)
    
    if has_access:
        await upload_video(message)
    else:
        await handle_suggestion_video(message, bot)

async def upload_video(message: Message):
    file_id = message.video.file_id
    file_name = message.video.file_name if message.video.file_name else "без названия"
    file_size = message.video.file_size
    duration = message.video.duration
    
    try:
        cursor.execute("SELECT id FROM videos WHERE file_id = ?", (file_id,))
        if cursor.fetchone():
            await message.answer(f"⚠️ <b>Это видео уже есть в базе!</b>\n\n📹 <b>File ID:</b> <code>{file_id}</code>")
            return
        
        cursor.execute("INSERT INTO videos (file_id) VALUES (?)", (file_id,))
        conn.commit()
        
        cursor.execute("SELECT COUNT(*) as count FROM videos")
        total_videos = cursor.fetchone()["count"]
        
        await message.answer(
            f"✅ <b>ВИДЕО ДОБАВЛЕНО!</b>\n\n"
            f"📹 {file_name}\n"
            f"🆔 <code>{file_id}</code>\n"
            f"⏱ {duration} сек\n"
            f"🎥 Всего: {total_videos}"
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

# ================= ПРЕДЛОЖКА =================
@router.callback_query(F.data == "suggestion")
async def suggestion_start(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    
    if not await check_access(call.bot, user_id, state, call=call):
        return
    
    await safe_answer(call)
    suggestion_mode.add(user_id)
    
    await call.message.answer(
        "🎬 <b>ПРЕДЛОЖКА</b>\n\n"
        "📹 Отправьте видео для добавления в бота.\n\n"
        "✅ Если одобрят: +3 🍬\n"
        "⏳ Режим активен 5 минут"
    )
    
    async def exit_suggestion_mode():
        await asyncio.sleep(300)
        suggestion_mode.discard(user_id)
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
        await message.answer("❌ Видео > 50MB")
        return
    
    short_id = file_id[-8:]
    suggested_videos[short_id] = {
        "user_id": user_id,
        "username": username,
        "file_name": file_name,
        "duration": duration,
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
    
    for admin in admins:
        try:
            await bot.send_video(
                admin["user_id"],
                video=file_id,
                caption=(
                    f"🎬 <b>НОВОЕ ПРЕДЛОЖЕНИЕ</b>\n\n"
                    f"👤 @{username}\n"
                    f"🆔 <code>{user_id}</code>\n"
                    f"📝 {file_name}\n"
                    f"💰 {balance} 🍬"
                ),
                reply_markup=admin_keyboard
            )
        except:
            pass
    
    await message.answer("✅ <b>Видео отправлено на модерацию!</b>")

@router.callback_query(F.data.startswith("app_"))
async def suggest_approve(call: CallbackQuery, bot: Bot):
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    short_id = call.data.replace("app_", "")
    video_data = suggested_videos.get(short_id)
    if not video_data:
        await safe_answer(call, "❌ Видео не найдено", show_alert=True)
        return
    
    file_id = video_data["file_id"]
    user_id = video_data["user_id"]
    
    cursor.execute("INSERT INTO videos (file_id) VALUES (?)", (file_id,))
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (SUGGESTION_REWARD, user_id))
    conn.commit()
    
    await bot.send_message(user_id, f"✅ <b>Видео одобрено!</b>\n\n🎁 +{SUGGESTION_REWARD} 🍬")
    await safe_answer(call, "✅ Одобрено")
    await call.message.delete()
    del suggested_videos[short_id]

@router.callback_query(F.data.startswith("rej_"))
async def suggest_reject(call: CallbackQuery, bot: Bot):
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    short_id = call.data.replace("rej_", "")
    video_data = suggested_videos.get(short_id)
    if not video_data:
        await safe_answer(call, "❌ Видео не найдено", show_alert=True)
        return
    
    user_id = video_data["user_id"]
    
    await bot.send_message(user_id, "❌ <b>Видео отклонено</b>\n\nПопробуйте другое видео.")
    await safe_answer(call, "❌ Отклонено")
    await call.message.delete()
    del suggested_videos[short_id]

# ================= ЗАГРУЗКА ВИДЕО ПО ССЫЛКЕ =================
@router.callback_query(F.data == "admin_upload_url")
async def admin_upload_url(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    has_access, _, _, _ = check_admin_access(user_id)
    
    if not has_access:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    await safe_answer(call)
    await state.set_state(AdminStates.waiting_for_cloud_url)
    await call.message.answer("🔗 <b>Загрузка видео по ссылке</b>\n\nОтправьте ссылку на видео.")

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
            await status_msg.edit_text(f"❌ Ошибка {response.status_code}")
            return
        
        ext = '.mp4'
        filename = f"{TEMP_DIR}/video_{int(time.time())}{ext}"
        
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        video_file = FSInputFile(filename)
        sent_message = await message.answer_video(video_file)
        
        file_id = sent_message.video.file_id
        cursor.execute("INSERT INTO videos (file_id) VALUES (?)", (file_id,))
        conn.commit()
        
        await message.answer(f"✅ <b>ВИДЕО ДОБАВЛЕНО!</b>\n\n📹 <code>{file_id}</code>")
        
    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка: {e}")
    finally:
        if filename and os.path.exists(filename):
            os.remove(filename)

# ================= БЫСТРАЯ ЗАГРУЗКА =================
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
        
        video_file = FSInputFile(filename)
        sent = await message.answer_video(video_file)
        
        file_id = sent.video.file_id
        cursor.execute("INSERT INTO videos (file_id) VALUES (?)", (file_id,))
        conn.commit()
        
        os.remove(filename)
        
        await message.answer(f"✅ Готово! ID: <code>{file_id}</code>")
        
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

# ================= СТАРТ =================
@router.message(CommandStart())
async def start(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    username = message.from_user.username or "пользователь"
    first_name = message.from_user.first_name or "Пользователь"
    
    logger.info(f"🟢 START command from user {user_id} (@{username})")
    
    banned, ban_until = is_banned(user_id)
    if banned:
        remaining = ban_until - datetime.now()
        await message.answer(f"🚫 <b>ДОСТУП ЗАБЛОКИРОВАН</b>\n\n⏳ {remaining.seconds // 60} мин")
        return
    
    has_access, _, is_main, can_manage = check_admin_access(user_id)
    
    if has_access:
        cursor.execute("""
            INSERT OR IGNORE INTO users (user_id, username, is_verified, is_admin)
            VALUES (?, ?, 1, 1)
        """, (user_id, username))
        cursor.execute("UPDATE users SET is_verified = 1, username = ? WHERE user_id = ?", (username, user_id))
        
        cursor.execute("SELECT ref_code FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if not row or not row["ref_code"]:
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
        if referrer and referrer["user_id"] != user_id:
            referrer_id = referrer["user_id"]
            has_ref_in_link = True
    
    if has_ref_in_link:
        if user:
            if user["referrer"] is None:
                cursor.execute("UPDATE users SET referrer = ? WHERE user_id = ?", (referrer_id, user_id))
                cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (REF_BONUS, referrer_id))
                conn.commit()
                try:
                    await bot.send_message(referrer_id, f"🎁 <b>Новый реферал!</b>\n\n@{username}\n➕ +{REF_BONUS} 🍬")
                except:
                    pass
        else:
            new_ref_code = generate_ref_code()
            cursor.execute("""
                INSERT INTO users (user_id, username, referrer, is_verified, ref_code, subscribe_bonus_received, is_admin)
                VALUES (?, ?, ?, 0, ?, 0, 0)
            """, (user_id, username, referrer_id, new_ref_code))
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (REF_BONUS, referrer_id))
            conn.commit()
            try:
                await bot.send_message(referrer_id, f"🎁 <b>Новый реферал!</b>\n\n@{username}\n➕ +{REF_BONUS} 🍬")
            except:
                pass
        
        if not is_verified(user_id):
            image_bytes, captcha_code = generate_captcha_image()
            captcha_data[user_id] = captcha_code
            await state.update_data(captcha_code=captcha_code)
            await state.set_state(CaptchaStates.waiting_for_captcha)
            await message.answer_photo(photo=BufferedInputFile(file=image_bytes, filename="captcha.png"), caption="🔐 <b>ПОДТВЕРЖДЕНИЕ</b>\n\nВведите код с картинки:")
            return
        
        if is_verified(user_id):
            if not await check_subscription(bot, user_id):
                await state.set_state(SubscribeStates.waiting_for_subscribe)
                await message.answer(f"<b>{first_name}🥰!</b>\n\nПодпишись на канал!\n— за подписку {SUBSCRIBE_BONUS} 🍬!", reply_markup=subscribe_menu)
                return
            await message.answer("🎥 Видео платформа", reply_markup=main_menu)
            return
    
    if not user:
        new_ref_code = generate_ref_code()
        cursor.execute("""
            INSERT INTO users (user_id, username, referrer, is_verified, ref_code, subscribe_bonus_received, is_admin)
            VALUES (?, ?, ?, 0, ?, 0, 0)
        """, (user_id, username, referrer_id, new_ref_code))
        conn.commit()
        if referrer_id:
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (REF_BONUS, referrer_id))
            conn.commit()
            try:
                await bot.send_message(referrer_id, f"🎁 <b>Новый реферал!</b>\n\n@{username}\n➕ +{REF_BONUS} 🍬")
            except:
                pass
    else:
        if not user["ref_code"]:
            ref_code = generate_ref_code()
            cursor.execute("UPDATE users SET ref_code = ? WHERE user_id = ?", (ref_code, user_id))
            conn.commit()
    
    if not has_referrer(user_id) and not referrer_id:
        await message.answer(f"Привет, @{username}!", reply_markup=fake_menu)
        return
    
    if not is_verified(user_id):
        image_bytes, captcha_code = generate_captcha_image()
        captcha_data[user_id] = captcha_code
        await state.update_data(captcha_code=captcha_code)
        await state.set_state(CaptchaStates.waiting_for_captcha)
        await message.answer_photo(photo=BufferedInputFile(file=image_bytes, filename="captcha.png"), caption="🔐 <b>ПОДТВЕРЖДЕНИЕ</b>\n\nВведите код с картинки:")
        return
    
    if is_verified(user_id):
        if not await check_subscription(bot, user_id):
            await state.set_state(SubscribeStates.waiting_for_subscribe)
            await message.answer(f"<b>{first_name}🥰!</b>\n\nПодпишись на канал!\n— за подписку {SUBSCRIBE_BONUS} 🍬!", reply_markup=subscribe_menu)
            return
        await message.answer("🎥 Видео платформа", reply_markup=main_menu)

# ================= ОБРАБОТКА КАПЧИ =================
@router.message(CaptchaStates.waiting_for_captcha)
async def process_captcha(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    user_input = message.text.strip().upper()
    
    banned, _ = is_banned(user_id)
    if banned:
        await message.answer("🚫 Доступ заблокирован")
        await state.clear()
        return
    
    data = await state.get_data()
    correct_code = data.get('captcha_code') or captcha_data.get(user_id)
    
    if not correct_code:
        await message.answer("❌ Ошибка. Нажми /start")
        await state.clear()
        return
    
    if user_input == correct_code:
        cursor.execute("UPDATE users SET is_verified = 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        if user_id in captcha_data:
            del captcha_data[user_id]
        await state.clear()
        
        if not await check_subscription(bot, user_id):
            await state.set_state(SubscribeStates.waiting_for_subscribe)
            await message.answer(f"🥰 Подпишись на канал!\n— за подписку {SUBSCRIBE_BONUS} 🍬!", reply_markup=subscribe_menu)
        else:
            await message.answer("✅ <b>Верификация пройдена!</b>", reply_markup=main_menu)
    else:
        attempts = captcha_attempts.get(user_id, 0) + 1
        captcha_attempts[user_id] = attempts
        
        if attempts >= 3:
            banned_users[user_id] = datetime.now() + timedelta(minutes=10)
            if user_id in captcha_data:
                del captcha_data[user_id]
            await state.clear()
            await message.answer("🚫 <b>ДОСТУП ЗАБЛОКИРОВАН</b>\n\n❌ 3 неудачные попытки\n⏳ Блокировка 10 минут")
            return
        
        image_bytes, new_code = generate_captcha_image()
        captcha_data[user_id] = new_code
        await state.update_data(captcha_code=new_code)
        await message.answer_photo(photo=BufferedInputFile(file=image_bytes, filename="captcha.png"), caption=f"❌ <b>НЕПРАВИЛЬНЫЙ КОД!</b>\n\nОсталось попыток: {3 - attempts}/3")

# ================= МАГАЗИН =================
@router.callback_query(F.data == "shop")
async def shop(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    if not await check_access(bot, user_id, state, call=call):
        return
    
    await call.message.answer(
        "🍬 <b>Магазин конфет</b>\n\n"
        "💰 Выберите количество конфет для покупки:\n\n"
        "⭐️ Для оплаты звездами нажми на кнопку ниже\n"
        "⭐️ 1 звезда = 3 конфеты 🍬",
        reply_markup=shop_menu
    )

# ================= КАСТОМНАЯ ОПЛАТА =================
@router.message(CustomPayStates.waiting_for_amount)
async def process_custom_pay(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    if not await check_access(bot, user_id, state, message=message):
        return
    
    try:
        amount = int(message.text.strip())
        if amount < 1 or amount > 10000:
            await message.answer("❌ От 1 до 10000 🍬")
            return
        
        usdt = round(amount * 0.003, 2)
        if usdt < 0.1:
            usdt = 0.1
        
        await state.update_data(pay_amount=amount, pay_usdt=usdt, pay_custom=True)
        
        keyboard = []
        sorted_assets = ["USDT", "TON"] + [a for a in AVAILABLE_ASSETS if a not in ["USDT", "TON"]]
        row = []
        for i, asset in enumerate(sorted_assets):
            icon = get_asset_icon(asset)
            row.append(InlineKeyboardButton(text=f"{icon} {asset}", callback_data=f"pay_asset_{asset}"))
            if (i + 1) % 2 == 0:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        
        await message.answer(
            f"💳 <b>Кастомная оплата (скидка 25%)</b>\n\n"
            f"🍬 {amount} конфет\n"
            f"💵 {usdt} USD\n\n"
            f"Выберите валюту:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
    except ValueError:
        await message.answer("❌ Введите число")

# ================= ВЫБОР ВАЛЮТЫ =================
@router.callback_query(F.data.startswith("pay_asset_"))
async def pay_with_asset(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    await safe_answer(call)
    
    if not await check_access(bot, user_id, state, call=call):
        return
    
    asset = call.data.replace("pay_asset_", "")
    data = await state.get_data()
    amount = data.get('pay_amount')
    usdt = data.get('pay_usdt')
    
    if not amount or not usdt:
        await call.message.answer("❌ Ошибка данных")
        return
    
    try:
        invoice = create_invoice(usdt, asset)
        cursor.execute("INSERT INTO payments (invoice_id, user_id, amount, paid) VALUES (?, ?, ?, 0)", (invoice["invoice_id"], user_id, amount))
        conn.commit()
        
        crypto_amount = invoice.get("crypto_amount", usdt)
        rate = invoice.get("rate", "")
        icon = get_asset_icon(asset)
        
        rate_text = f"\n💰 К оплате: {crypto_amount} {asset}"
        if rate:
            rate_text = f"\n1 {asset} = ${rate}\n💰 К оплате: {crypto_amount} {asset}"
        
        await call.message.answer(
            f"💳 <b>Оплата в {icon} {asset}</b>\n\n"
            f"🍬 {amount} конфет\n"
            f"💵 ${usdt}{rate_text}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f"💰 Оплатить {crypto_amount} {asset}", url=invoice["pay_url"])],
                [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_{invoice['invoice_id']}")]
            ])
        )
        await state.clear()
    except Exception as e:
        await call.message.answer(f"❌ Ошибка: {e}")

# ================= ОПЛАТА (ПАКЕТЫ) =================
@router.callback_query(F.data.startswith("pay_"))
async def pay(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    
    if call.data.startswith("pay_asset_"):
        return
    
    if not await check_access(bot, user_id, state, call=call):
        return
    
    prices = {
        "pay_50": (50, 0.2),
        "pay_100": (100, 0.3),
        "pay_140": (140, 0.4),
        "pay_170": (170, 0.5),
        "pay_200": (200, 0.6),
        "pay_333": (333, 1.0),
    }
    
    if call.data == "pay_custom":
        await state.set_state(CustomPayStates.waiting_for_amount)
        await call.message.answer("💰 Введите количество конфет:")
        return
    
    if call.data == "pay_private":
        await handle_private_purchase(call, state, bot)
        return
    
    if call.data not in prices:
        return
    
    amount, usdt = prices[call.data]
    await state.update_data(pay_amount=amount, pay_usdt=usdt, pay_custom=False)
    
    keyboard = []
    sorted_assets = ["USDT", "TON"] + [a for a in AVAILABLE_ASSETS if a not in ["USDT", "TON"]]
    row = []
    for i, asset in enumerate(sorted_assets):
        icon = get_asset_icon(asset)
        row.append(InlineKeyboardButton(text=f"{icon} {asset}", callback_data=f"pay_asset_{asset}"))
        if (i + 1) % 2 == 0:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    await call.message.answer(
        f"💳 <b>Выберите валюту</b>\n\n"
        f"🍬 {amount} конфет\n"
        f"💵 ${usdt}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

# ================= ПРИВАТКА =================
async def handle_private_purchase(call: CallbackQuery, state: FSMContext, bot: Bot):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐️ Оплатить 599 звездами", callback_data="pay_private_stars")],
        [InlineKeyboardButton(text="💵 Оплатить $5 (USDT/TON)", callback_data="pay_private_crypto")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="shop")]
    ])
    
    await call.message.edit_text(
        f"🔐 <b>ПОКУПКА ПРИВАТКИ</b>\n\n"
        f"💰 Стоимость: 599 ⭐️ или $5\n\n"
        f"После оплаты вы получите доступ к приватным видео.\n"
        f"Доступ выдается навсегда.\n\n"
        f"Выберите способ оплаты:",
        reply_markup=keyboard
    )

@router.callback_query(F.data == "pay_private_stars")
async def pay_private_stars(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    await safe_answer(call)
    
    if not ANON_CHAT_LINK:
        await call.message.answer("❌ Ссылка для оплаты не настроена. Обратитесь к администратору.")
        return
    
    PRIVATE_PRICE_STARS = 599
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"⭐️ Оплатить {PRIVATE_PRICE_STARS} звезд", url=ANON_CHAT_LINK)],
        [InlineKeyboardButton(text="✅ Я оплатил", callback_data="check_private_manual")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="shop")]
    ])
    
    await call.message.edit_text(
        f"🔐 <b>ПОКУПКА ПРИВАТКИ (ЗВЕЗДЫ)</b>\n\n"
        f"💰 Стоимость: {PRIVATE_PRICE_STARS} ⭐️\n\n"
        f"📌 <b>Инструкция:</b>\n"
        f"1️⃣ Нажми на кнопку ниже\n"
        f"2️⃣ Оплати {PRIVATE_PRICE_STARS} звезд\n"
        f"3️⃣ Нажми «✅ Я оплатил»\n"
        f"4️⃣ Администратор проверит и выдаст доступ\n\n"
        f"⚠️ Доступ выдается вручную",
        reply_markup=keyboard
    )

@router.callback_query(F.data == "check_private_manual")
async def check_private_manual(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    await safe_answer(call, "✅ Заявка отправлена!")
    
    admins = get_all_admins()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Выдать доступ", callback_data=f"admin_grant_private_{user_id}")],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"admin_reject_private_{user_id}")]
    ])
    
    for admin in admins:
        try:
            await bot.send_message(
                admin["user_id"],
                f"🔐 <b>ЗАЯВКА НА ПРИВАТКУ</b>\n\n"
                f"👤 @{call.from_user.username or 'нет username'}\n"
                f"🆔 <code>{user_id}</code>\n\n"
                f"Сообщил об оплате 599 звезд.\n"
                f"Проверьте и выдайте доступ:",
                reply_markup=keyboard
            )
        except:
            pass
    
    await call.message.edit_text(
        f"✅ <b>Заявка отправлена!</b>\n\n"
        f"Администратор проверит и выдаст доступ."
    )

@router.callback_query(F.data.startswith("admin_grant_private_"))
async def admin_grant_private(call: CallbackQuery, bot: Bot):
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    user_id = int(call.data.replace("admin_grant_private_", ""))
    
    if grant_private_access(user_id):
        await safe_answer(call, "✅ Доступ выдан!")
        await call.message.delete()
        try:
            await bot.send_message(user_id, "🔐 <b>Доступ к приватке активирован!</b>\n\nТеперь вам доступны приватные видео.")
        except:
            pass
    else:
        await safe_answer(call, "❌ Ошибка", show_alert=True)

@router.callback_query(F.data.startswith("admin_reject_private_"))
async def admin_reject_private(call: CallbackQuery, bot: Bot):
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    user_id = int(call.data.replace("admin_reject_private_", ""))
    
    await safe_answer(call, "❌ Отклонено")
    await call.message.delete()
    try:
        await bot.send_message(user_id, "❌ <b>Заявка отклонена</b>\n\nОбратитесь в поддержку.")
    except:
        pass

@router.callback_query(F.data == "pay_private_crypto")
async def pay_private_crypto(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    await safe_answer(call)
    
    try:
        invoice = create_invoice(5, "USDT")
        if not invoice:
            await call.message.answer("❌ Ошибка")
            return
        
        cursor.execute("INSERT INTO payments (invoice_id, user_id, amount, paid) VALUES (?, ?, ?, 0)", (invoice["invoice_id"], user_id, 5))
        conn.commit()
        
        await call.message.answer(
            f"🔐 <b>ОПЛАТА ПРИВАТКИ (КРИПТА)</b>\n\n"
            f"💰 $5\n\n"
            f"К оплате: {invoice.get('crypto_amount', 5)} USDT\n\n"
            f"Ссылка: {invoice['pay_url']}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💰 Оплатить", url=invoice["pay_url"])],
                [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_private_crypto_{invoice['invoice_id']}")]
            ])
        )
    except Exception as e:
        await call.message.answer(f"❌ Ошибка: {e}")

@router.callback_query(F.data.startswith("check_private_crypto_"))
async def check_private_crypto(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    invoice_id = call.data.replace("check_private_crypto_", "")
    await safe_answer(call)
    
    cursor.execute("SELECT user_id, amount, paid FROM payments WHERE invoice_id = ?", (invoice_id,))
    row = cursor.fetchone()
    
    if not row:
        await call.message.answer("❌ Платёж не найден")
        return
    
    result = check_invoice(invoice_id)
    
    if result.get("paid", False):
        if row["paid"] == 1:
            await call.message.answer("✅ Уже обработан")
            return
        
        cursor.execute("UPDATE payments SET paid = 1 WHERE invoice_id = ?", (invoice_id,))
        grant_private_access(user_id)
        conn.commit()
        
        await call.message.answer(f"✅ <b>Оплата подтверждена!</b>\n\n🔐 Доступ к приватке открыт!")
    else:
        await call.message.answer("⏳ Платёж ещё не оплачен")

# ================= ПРОВЕРКА ПЛАТЕЖА =================
@router.callback_query(F.data.startswith("check_"))
async def check_payment(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    
    if call.data in ["check_subscribe", "check_private_manual"] or call.data.startswith("check_private_crypto_"):
        return
    
    await safe_answer(call)
    
    if not await check_access(bot, user_id, state, call=call):
        return
    
    invoice_id = call.data.split("_", 1)[1]
    
    cursor.execute("SELECT user_id, amount, paid FROM payments WHERE invoice_id = ?", (invoice_id,))
    row = cursor.fetchone()
    
    if not row:
        await call.message.answer("❌ Платёж не найден")
        return
    
    result = check_invoice(invoice_id)
    
    if result.get("paid", False):
        if row["paid"] == 1:
            await call.message.answer("✅ Уже обработан")
            return
        
        cursor.execute("UPDATE payments SET paid = 1 WHERE invoice_id = ?", (invoice_id,))
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (row["amount"], row["user_id"]))
        
        cursor.execute("SELECT referrer FROM users WHERE user_id = ?", (row["user_id"],))
        user = cursor.fetchone()
        if user and user["referrer"]:
            ref_bonus = int(row["amount"] * REF_PERCENT / 100)
            if ref_bonus > 0:
                cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (ref_bonus, user["referrer"]))
                try:
                    await bot.send_message(user["referrer"], f"💰 Реферал купил {row['amount']} 🍬\n➕ +{ref_bonus} 🍬")
                except:
                    pass
        
        conn.commit()
        
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (row["user_id"],))
        new_balance = cursor.fetchone()["balance"]
        
        await call.message.answer(
            f"✅ <b>Оплата подтверждена!</b>\n\n"
            f"🍬 +{row['amount']} конфет\n"
            f"💰 Баланс: {new_balance} 🍬"
        )
    else:
        await call.message.answer("⏳ Платёж ещё не оплачен")

# ================= ПРОМОКОДЫ =================
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
    
    await message.answer(f"✅ <b>Промокод активирован!</b>\n\n🎁 +{promo['reward']} 🍬\n💰 Баланс: {new_balance} 🍬")
    await state.clear()

# ================= ПОДДЕРЖКА =================
@router.callback_query(F.data == "support")
async def support_start(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    if not await check_access(bot, user_id, state, call=call):
        return
    
    await safe_answer(call)
    await state.set_state(SubscribeStates.waiting_for_support_message)
    await call.message.answer("📝 <b>ПОДДЕРЖКА</b>\n\nНапишите сообщение или отправьте скриншот.\nАдминистратор ответит.")

@router.message(SubscribeStates.waiting_for_support_message, F.text)
async def support_message_handler(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    user_text = message.text
    
    if len(user_text) < 2:
        await message.answer("❌ Сообщение слишком короткое")
        return
    
    cursor.execute("SELECT username FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    username = user["username"] if user else "нет username"
    
    reply_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Ответить", callback_data=f"reply_{user_id}")]
    ])
    
    try:
        await bot.send_message(
            MAIN_ADMIN_ID,
            f"📬 <b>НОВОЕ СООБЩЕНИЕ</b>\n\n"
            f"👤 @{username}\n"
            f"🆔 <code>{user_id}</code>\n\n"
            f"💬 {user_text}",
            reply_markup=reply_keyboard
        )
        await message.answer("✅ Сообщение отправлено!")
    except:
        await message.answer("❌ Ошибка")
    
    await state.clear()

@router.message(SubscribeStates.waiting_for_support_message, F.photo)
async def support_photo_handler(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    user_text = message.caption or "Без описания"
    photo = message.photo[-1]
    
    cursor.execute("SELECT username FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    username = user["username"] if user else "нет username"
    
    reply_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Ответить", callback_data=f"reply_{user_id}")]
    ])
    
    try:
        await bot.send_photo(
            MAIN_ADMIN_ID,
            photo=photo.file_id,
            caption=f"📸 <b>СКРИНШОТ</b>\n\n👤 @{username}\n🆔 <code>{user_id}</code>\n\n💬 {user_text}",
            reply_markup=reply_keyboard
        )
        await message.answer("✅ Скриншот отправлен!")
    except:
        await message.answer("❌ Ошибка")
    
    await state.clear()

@router.message(AdminStates.waiting_for_support_reply)
async def support_reply_send(message: Message, state: FSMContext, bot: Bot):
    if not check_admin_access(message.from_user.id)[0]:
        return
    
    data = await state.get_data()
    user_id = data.get('reply_to_user')
    
    if not user_id:
        await message.answer("❌ Ошибка")
        await state.clear()
        return
    
    try:
        await bot.send_message(user_id, f"📬 <b>ОТВЕТ ОТ ПОДДЕРЖКИ</b>\n\n{message.text}")
        await message.answer(f"✅ Ответ отправлен")
    except:
        await message.answer(f"❌ Ошибка. Пользователь {user_id} не найден")
    
    await state.clear()

@router.callback_query(F.data.startswith("reply_"))
async def support_reply_start(call: CallbackQuery, state: FSMContext):
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    user_id = int(call.data.split("_")[1])
    
    cursor.execute("SELECT user_id, username FROM users WHERE user_id = ?", (user_id,))
    if not cursor.fetchone():
        await call.message.answer(f"❌ Пользователь {user_id} не найден")
        return
    
    await state.update_data(reply_to_user=user_id)
    await state.set_state(AdminStates.waiting_for_support_reply)
    await call.message.answer(f"✏️ <b>ОТВЕТ</b>\n\nID: <code>{user_id}</code>\n\nВведите текст:")

# ================= АДМИН - СТАТИСТИКА =================
@router.callback_query(F.data == "admin_stats")
async def admin_stats(call: CallbackQuery):
    user_id = call.from_user.id
    if not check_admin_access(user_id)[0]:
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
    tasks_stats = get_tasks_stats()
    
    channels = get_mandatory_channels()
    
    cursor.execute("SELECT COUNT(*) as count FROM users WHERE subscribe_bonus_received = 1")
    bonus_received = cursor.fetchone()["count"] or 0
    
    admins = get_all_admins()
    admins_count = len(admins)
    
    text = (
        f"📊 <b>СТАТИСТИКА</b>\n\n"
        f"👥 <b>ПОЛЬЗОВАТЕЛИ:</b>\n"
        f"├ Всего: {total_users}\n"
        f"├ Верифицировано: {verified_users}\n"
        f"├ С балансом: {users_with_balance}\n"
        f"├ Рефералов: {referral_stats['total_refs']}\n"
        f"├ Админов: {admins_count}\n"
        f"└ Бонус: {bonus_received}\n\n"
        f"💰 <b>БАЛАНСЫ:</b>\n"
        f"├ Всего: {total_balance} 🍬\n"
        f"├ Средний: {avg_balance:.1f}\n"
        f"└ Макс: {max_balance}\n\n"
        f"🎥 <b>ВИДЕО:</b>\n"
        f"├ Всего: {total_videos}\n"
        f"├ Просмотров: {watched_stats['total_views']}\n"
        f"└ Смотрели: {watched_stats['unique_viewers']} чел\n\n"
        f"💳 <b>ПЛАТЕЖИ:</b>\n"
        f"├ Успешных: {payments_stats['successful']}\n"
        f"├ Конфет продано: {payments_stats['total_candies']}\n"
        f"└ Попыток: {payments_stats['total_attempts']}\n\n"
        f"🎟 <b>ПРОМОКОДЫ:</b>\n"
        f"├ Создано: {promo_stats['total_codes']}\n"
        f"├ Активировано: {promo_stats['total_used']}\n"
        f"└ Осталось: {promo_stats['total_left']}\n\n"
        f"📋 <b>ЗАДАНИЯ:</b>\n"
        f"├ Всего: {tasks_stats['total']}\n"
        f"├ На проверке: {tasks_stats['pending']}\n"
        f"├ Выполнено: {tasks_stats['approved']}\n"
        f"└ Выдано наград: {tasks_stats['total_reward']} 🍬\n\n"
        f"🔐 <b>ОП:</b>\n"
        f"└ Каналов: {len(channels)}"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏆 Топ рефералов", callback_data="admin_top_refs")],
        [InlineKeyboardButton(text="🔍 Поиск платежей", callback_data="admin_search_payments")],
        [InlineKeyboardButton(text="👤 Поиск пользователей", callback_data="admin_search_users")]
    ])
    
    await call.message.answer(text)
    await call.message.answer("📊 <b>Дополнительно</b>", reply_markup=keyboard)

# ================= АДМИН - ТОП РЕФЕРОВ =================
@router.callback_query(F.data == "admin_top_refs")
async def admin_top_refs(call: CallbackQuery):
    user_id = call.from_user.id
    if not check_admin_access(user_id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    await safe_answer(call)
    
    cursor.execute("""
        SELECT u.user_id, u.username, COUNT(r.user_id) as ref_count
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
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "🔹"
            text += f"{medal} <b>{i}.</b> @{username}\n"
            text += f"   👥 Рефералов: {ref_count}\n\n"
    
    keyboard = [[InlineKeyboardButton(text="🔙 Назад", callback_data="admin_stats")]]
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

# ================= АДМИН - ПОИСК ПЛАТЕЖЕЙ =================
@router.callback_query(F.data == "admin_search_payments")
async def admin_search_payments_start(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    if not check_admin_access(user_id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    await safe_answer(call)
    await state.set_state(AdminStates.waiting_for_payment_search)
    await call.message.answer("🔍 <b>Поиск платежей</b>\n\nВведите ID пользователя или username:")

@router.message(AdminStates.waiting_for_payment_search)
async def admin_search_payments_result(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if not check_admin_access(user_id)[0]:
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

# ================= АДМИН - ПОИСК ПОЛЬЗОВАТЕЛЕЙ =================
@router.callback_query(F.data == "admin_search_users")
async def admin_search_users_start(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    if not check_admin_access(user_id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    await safe_answer(call)
    await state.set_state(AdminStates.waiting_for_user_search)
    await call.message.answer("👤 <b>Поиск пользователей</b>\n\nВведите ID, username или часть username:")

@router.message(AdminStates.waiting_for_user_search)
async def admin_search_users_result(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if not check_admin_access(user_id)[0]:
        return
    
    search_query = message.text.strip()
    
    if search_query.startswith('@'):
        username = search_query[1:]
        cursor.execute("SELECT user_id, username, balance, is_verified, referrer, last_bonus, subscribe_bonus_received, is_admin FROM users WHERE username = ?", (username,))
    else:
        try:
            target_id = int(search_query)
            cursor.execute("SELECT user_id, username, balance, is_verified, referrer, last_bonus, subscribe_bonus_received, is_admin FROM users WHERE user_id = ?", (target_id,))
        except ValueError:
            cursor.execute("SELECT user_id, username, balance, is_verified, referrer, last_bonus, subscribe_bonus_received, is_admin FROM users WHERE username LIKE ? ORDER BY user_id LIMIT 10", (f"%{search_query}%",))
    
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
        
        text += "\n"
    
    keyboard = [[InlineKeyboardButton(text="🔙 Назад", callback_data="admin_stats")]]
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    await state.clear()

# ================= ОБРАБОТКА ФЕЙК МЕНЮ =================
@router.callback_query(F.data.startswith("fake_"))
async def fake_menu_actions(call: CallbackQuery):
    user_id = call.from_user.id
    await safe_answer(call)
    
    if has_referrer(user_id):
        if await check_access(call.bot, user_id, None, call=call):
            await call.message.answer("🎥 Видео платформа", reply_markup=main_menu)
        return
    
    if call.data == "fake_download":
        await safe_answer(call, "❌ Ошибка загрузки", show_alert=True)
    elif call.data == "fake_rate":
        rate = random.randint(45000, 52000)
        await safe_answer(call, f"💱 Курс BTC: ${rate}", show_alert=True)
    elif call.data == "fake_dice":
        dice = random.randint(1, 6)
        await safe_answer(call, f"🎲 Выпало: {dice}", show_alert=True)

# ================= БОНУС =================
@router.callback_query(F.data == "bonus")
async def bonus(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    if not await check_access(bot, user_id, state, call=call):
        return
    
    now = int(time.time())
    cursor.execute("SELECT last_bonus FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    
    if not result:
        await safe_answer(call, "❌ Ошибка", show_alert=True)
        return
    
    last = result["last_bonus"]
    if now - last < BONUS_COOLDOWN:
        remaining = BONUS_COOLDOWN - (now - last)
        await safe_answer(call, f"⏳ {remaining // 60} мин {remaining % 60} сек", show_alert=True)
        return
    
    cursor.execute("UPDATE users SET balance = balance + ?, last_bonus = ? WHERE user_id = ?", (BONUS_AMOUNT, now, user_id))
    conn.commit()
    await safe_answer(call, f"🎁 +{BONUS_AMOUNT} 🍬", show_alert=True)

# ================= ВИДЕО (ПРОСМОТР) =================
@router.callback_query(F.data == "videos")
async def videos(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    
    if not await check_access(bot, user_id, state, call=call):
        return
    
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    if not result:
        await safe_answer(call, "❌ Ошибка", show_alert=True)
        return
    
    balance = result["balance"]
    has_private = has_private_access(user_id)
    
    if balance < VIDEO_PRICE and not check_admin_access(user_id)[0] and not has_private:
        await safe_answer(call, f"❌ Нужно {VIDEO_PRICE} 🍬", show_alert=True)
        return
    
    cursor.execute("SELECT COUNT(*) as count FROM videos")
    if cursor.fetchone()["count"] == 0:
        await safe_answer(call, "❌ Нет видео", show_alert=True)
        return
    
    if has_private:
        cursor.execute("""
            SELECT id, file_id, is_private FROM videos
            WHERE id NOT IN (SELECT video_id FROM user_videos WHERE user_id = ?)
            ORDER BY is_private DESC, id ASC LIMIT 1
        """, (user_id,))
    else:
        cursor.execute("""
            SELECT id, file_id, is_private FROM videos
            WHERE (is_private = 0 OR is_private IS NULL) AND id NOT IN (SELECT video_id FROM user_videos WHERE user_id = ?)
            ORDER BY id ASC LIMIT 1
        """, (user_id,))
    
    video = cursor.fetchone()
    if not video:
        await safe_answer(call, "❌ Все видео просмотрены!", show_alert=True)
        return
    
    try:
        caption = "🔐 <b>ПРИВАТНОЕ ВИДЕО</b>\n\n🎥 <b>Видео</b>" if video["is_private"] == 1 else "🎥 <b>Видео</b>"
        await call.message.answer_video(video["file_id"], caption=caption, reply_markup=video_menu)
        
        if not check_admin_access(user_id)[0] and not has_private:
            cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (VIDEO_PRICE, user_id))
            await safe_answer(call, f"🍬 -{VIDEO_PRICE}", show_alert=True)
        
        cursor.execute("INSERT OR IGNORE INTO user_videos (user_id, video_id) VALUES (?, ?)", (user_id, video["id"]))
        conn.commit()
    except Exception as e:
        logger.error(f"Video error: {e}")
        await safe_answer(call, "❌ Ошибка", show_alert=True)

# ================= ПРОМОКОДЫ =================
@router.callback_query(F.data == "promo")
async def promo(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    if not await check_access(bot, user_id, state, call=call):
        return
    
    await state.set_state(PromoStates.waiting_for_promo)
    await call.message.answer("🎟 Введите промокод:")

# ================= МЕНЮ =================
@router.callback_query(F.data == "menu")
async def back_to_menu(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    has_access, _, is_main, can_manage = check_admin_access(user_id)
    
    if has_access:
        await call.message.answer("👑 Админ-панель", reply_markup=get_admin_menu(is_main, can_manage))
        return
    
    if not await check_access(call.bot, user_id, state, call=call):
        return
    
    await call.message.answer("🎥 Видео платформа", reply_markup=main_menu)

# ================= ПРОФИЛЬ =================
@router.callback_query(F.data == "profile")
async def profile(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
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
    
    user_tasks = get_user_completed_tasks(user_id)
    completed_count = sum(1 for t in user_tasks if t.get("status") == "approved")
    has_private = has_private_access(user_id)
    
    text = (
        f"👤 <b>ПРОФИЛЬ</b>\n\n"
        f"🍬 Баланс: <code>{balance}</code>\n"
        f"👥 Рефералов: <code>{ref_count}</code>\n"
        f"📋 Выполнено: <code>{completed_count}</code>\n"
        f"🔐 Приватка: {'✅' if has_private else '❌'}\n\n"
        f"🔗 <b>Твоя ссылка:</b>\n<code>{ref_link}</code>\n\n"
        f"🎁 За друга: +{REF_BONUS} 🍬\n"
        f"💰 С покупок: {REF_PERCENT}%"
    )
    
    try:
        await call.message.edit_text(text, disable_web_page_preview=False)
    except:
        await call.message.answer(text, disable_web_page_preview=False)

# ================= ЗАДАНИЯ =================

@router.callback_query(F.data == "tasks")
async def show_tasks(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    
    if not await check_access(call.bot, user_id, state, call=call):
        return
    
    await safe_answer(call)
    
    user_tasks = get_user_completed_tasks(user_id)
    
    if not user_tasks:
        await call.message.answer("📋 <b>ЗАДАНИЯ</b>\n\nНет активных заданий")
        return
    
    text = "📋 <b>ЗАДАНИЯ</b>\n\n"
    for task in user_tasks:
        if task.get("status") == "approved":
            status = "✅ Выполнено"
        elif task.get("status") == "pending":
            status = "⏳ На проверке"
        else:
            status = "❌ Не выполнено"
        text += f"🎯 {task['title']}\n💰 +{task['reward']} 🍬 | {status}\n\n"
    
    await call.message.answer(text, reply_markup=get_tasks_menu(user_tasks))

@router.callback_query(F.data.startswith("task_"))
async def show_task_detail(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    
    if not await check_access(call.bot, user_id, state, call=call):
        return
    
    task_id = int(call.data.split("_")[1])
    task = get_task(task_id)
    if not task:
        await safe_answer(call, "❌ Задание не найдено")
        return
    
    user_status = get_user_task_status(user_id, task_id)
    if user_status and user_status["status"] == "approved":
        await safe_answer(call, "✅ Выполнено", show_alert=True)
        return
    
    text = f"🎯 <b>{task['title']}</b>\n\n📝 {task['description']}\n💰 +{task['reward']} 🍬"
    if task["content"]:
        text += f"\n\n📎 {task['content']}"
    
    if user_status and user_status["status"] == "pending":
        text += "\n\n⏳ На проверке"
        await call.message.answer(text)
    else:
        await call.message.answer(text, reply_markup=get_task_action_menu(task_id, task['title'], task['reward']))

@router.callback_query(F.data.startswith("do_task_"))
async def start_task_submission(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    
    if not await check_access(call.bot, user_id, state, call=call):
        return
    
    task_id = int(call.data.split("_")[2])
    task = get_task(task_id)
    if not task:
        await safe_answer(call, "❌ Задание не найдено")
        return
    
    user_status = get_user_task_status(user_id, task_id)
    if user_status:
        if user_status["status"] == "approved":
            await safe_answer(call, "✅ Уже выполнено", show_alert=True)
            return
        if user_status["status"] == "pending":
            await safe_answer(call, "⏳ Уже на проверке", show_alert=True)
            return
    
    await state.update_data(task_id=task_id, task_title=task['title'], task_reward=task['reward'])
    await state.set_state(TaskStates.waiting_for_task_submit)
    
    await call.message.answer(
        f"📝 <b>ВЫПОЛНЕНИЕ ЗАДАНИЯ</b>\n\n"
        f"🎯 {task['title']}\n💰 +{task['reward']} 🍬\n\n"
        f"📌 {task['content'] or 'Отправьте подтверждение'}\n\n"
        f"Отправьте:\n"
        f"• текст\n"
        f"• ссылку\n"
        f"• скриншот\n"
        f"• видео"
    )

@router.message(TaskStates.waiting_for_task_submit)
async def task_submission(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    data = await state.get_data()
    task_id = data.get("task_id")
    task_title = data.get("task_title")
    task_reward = data.get("task_reward")
    
    if not task_id:
        await state.clear()
        return
    
    if message.text:
        submission = message.text
        sub_type = "text"
    elif message.photo:
        submission = message.photo[-1].file_id
        sub_type = "photo"
    elif message.video:
        submission = message.video.file_id
        sub_type = "video"
    else:
        await message.answer("❌ Неверный формат")
        return
    
    success, msg = submit_task(user_id, task_id, submission, sub_type)
    
    if not success:
        if msg == "already_pending":
            await message.answer("⏳ Уже на проверке")
        elif msg == "already_approved":
            await message.answer("✅ Уже выполнено")
        else:
            await message.answer(f"❌ Ошибка")
        await state.clear()
        return
    
    admins = get_all_admins()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"task_approve_{user_id}_{task_id}"),
         InlineKeyboardButton(text="❌ Отклонить", callback_data=f"task_reject_{user_id}_{task_id}")]
    ])
    
    for admin in admins:
        try:
            if sub_type == "photo":
                await bot.send_photo(
                    admin["user_id"],
                    photo=submission,
                    caption=f"📋 <b>НОВОЕ ЗАДАНИЕ</b>\n\n👤 @{message.from_user.username or 'нет'}\n🆔 <code>{user_id}</code>\n🎯 {task_title}\n💰 +{task_reward} 🍬",
                    reply_markup=keyboard
                )
            elif sub_type == "video":
                await bot.send_video(
                    admin["user_id"],
                    video=submission,
                    caption=f"📋 <b>НОВОЕ ЗАДАНИЕ</b>\n\n👤 @{message.from_user.username or 'нет'}\n🆔 <code>{user_id}</code>\n🎯 {task_title}\n💰 +{task_reward} 🍬",
                    reply_markup=keyboard
                )
            else:
                await bot.send_message(
                    admin["user_id"],
                    f"📋 <b>НОВОЕ ЗАДАНИЕ</b>\n\n👤 @{message.from_user.username or 'нет'}\n🆔 <code>{user_id}</code>\n🎯 {task_title}\n💰 +{task_reward} 🍬\n\n📎 {submission}",
                    reply_markup=keyboard
                )
        except:
            pass
    
    await message.answer(f"✅ <b>Задание отправлено на проверку!</b>\n\n🎯 {task_title}\n💰 +{task_reward} 🍬")
    await state.clear()

@router.callback_query(F.data.startswith("task_approve_"))
async def task_approve(call: CallbackQuery, bot: Bot):
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    parts = call.data.split("_")
    user_id = int(parts[2])
    task_id = int(parts[3])
    
    cursor.execute("SELECT id FROM completed_tasks WHERE user_id = ? AND task_id = ? AND status = 'pending'", (user_id, task_id))
    row = cursor.fetchone()
    if not row:
        await safe_answer(call, "❌ Заявка не найдена")
        await call.message.delete()
        return
    
    success, reward = approve_task(row["id"], call.from_user.id)
    
    if success:
        await safe_answer(call, f"✅ +{reward} 🍬")
        try:
            await bot.send_message(user_id, f"✅ <b>Задание выполнено!</b>\n\n🎯 +{reward} 🍬")
        except:
            pass
        await call.message.delete()
    else:
        await safe_answer(call, "❌ Ошибка")

@router.callback_query(F.data.startswith("task_reject_"))
async def task_reject(call: CallbackQuery, bot: Bot):
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    parts = call.data.split("_")
    user_id = int(parts[2])
    task_id = int(parts[3])
    
    cursor.execute("SELECT id FROM completed_tasks WHERE user_id = ? AND task_id = ? AND status = 'pending'", (user_id, task_id))
    row = cursor.fetchone()
    if not row:
        await safe_answer(call, "❌ Заявка не найдена")
        await call.message.delete()
        return
    
    success = reject_task(row["id"], call.from_user.id)
    
    if success:
        await safe_answer(call, "❌ Отклонено")
        try:
            await bot.send_message(user_id, "❌ <b>Задание не засчитано</b>\n\nПопробуйте еще раз.")
        except:
            pass
        await call.message.delete()
    else:
        await safe_answer(call, "❌ Ошибка")

# ================= АДМИН - УПРАВЛЕНИЕ ЗАДАНИЯМИ =================

@router.callback_query(F.data == "admin_tasks")
async def admin_tasks_menu_handler(call: CallbackQuery):
    user_id = call.from_user.id
    if not check_admin_access(user_id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    await safe_answer(call)
    
    pending_count = len(get_pending_submissions())
    total_tasks = len(get_all_tasks())
    
    await call.message.answer(
        f"📋 <b>УПРАВЛЕНИЕ ЗАДАНИЯМИ</b>\n\n"
        f"📌 Всего: {total_tasks}\n"
        f"⏳ На проверке: {pending_count}\n\n"
        f"Выберите действие:",
        reply_markup=admin_tasks_menu
    )

@router.callback_query(F.data == "admin_task_add")
async def admin_task_add_start(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    if not check_admin_access(user_id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    await safe_answer(call)
    await state.set_state(TaskStates.waiting_for_task_title)
    await call.message.answer(
        "📝 <b>СОЗДАНИЕ ЗАДАНИЯ</b>\n\n"
        "1️⃣ Введите НАЗВАНИЕ:"
    )

@router.message(TaskStates.waiting_for_task_title)
async def task_add_title(message: Message, state: FSMContext):
    if not check_admin_access(message.from_user.id)[0]:
        return
    
    await state.update_data(task_title=message.text.strip())
    await state.set_state(TaskStates.waiting_for_task_desc)
    await message.answer("2️⃣ Введите ОПИСАНИЕ:")

@router.message(TaskStates.waiting_for_task_desc)
async def task_add_desc(message: Message, state: FSMContext):
    if not check_admin_access(message.from_user.id)[0]:
        return
    
    await state.update_data(task_desc=message.text.strip())
    await state.set_state(TaskStates.waiting_for_task_reward)
    await message.answer("3️⃣ Введите НАГРАДУ (🍬):")

@router.message(TaskStates.waiting_for_task_reward)
async def task_add_reward(message: Message, state: FSMContext):
    if not check_admin_access(message.from_user.id)[0]:
        return
    
    try:
        reward = int(message.text.strip())
        if reward <= 0:
            await message.answer("❌ Награда > 0")
            return
        await state.update_data(task_reward=reward)
        await state.set_state(TaskStates.waiting_for_task_type)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📝 Текст", callback_data="task_type_text")],
            [InlineKeyboardButton(text="🔗 Ссылка", callback_data="task_type_link")],
            [InlineKeyboardButton(text="📸 Фото", callback_data="task_type_photo")],
            [InlineKeyboardButton(text="🎥 Видео", callback_data="task_type_video")],
            [InlineKeyboardButton(text="❌ Без контента", callback_data="task_type_none")]
        ])
        
        await message.answer("4️⃣ Выберите ТИП подтверждения:", reply_markup=keyboard)
    except ValueError:
        await message.answer("❌ Введите число")

@router.callback_query(F.data.startswith("task_type_"))
async def task_add_type(call: CallbackQuery, state: FSMContext):
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    task_type = call.data.replace("task_type_", "")
    await state.update_data(task_type=task_type)
    await safe_answer(call)
    
    if task_type == "none":
        data = await state.get_data()
        task_id = add_task(
            title=data["task_title"],
            reward=data["task_reward"],
            description=data["task_desc"],
            task_type="text",
            content=""
        )
        if task_id:
            await call.message.edit_text(f"✅ <b>Задание создано!</b>\n\n🎯 {data['task_title']}\n💰 +{data['task_reward']} 🍬")
        else:
            await call.message.edit_text("❌ Ошибка")
        await state.clear()
        return
    
    await state.set_state(TaskStates.waiting_for_task_content)
    await call.message.edit_text(
        "5️⃣ Отправьте КОНТЕНТ:\n\n"
        "Может быть:\n"
        "• текст\n"
        "• ссылка\n"
        "• фото\n"
        "• видео"
    )

@router.message(TaskStates.waiting_for_task_content, F.text)
async def task_add_content_text(message: Message, state: FSMContext):
    if not check_admin_access(message.from_user.id)[0]:
        return
    await state.update_data(task_content=message.text.strip())
    await finish_task_creation(message, state)

@router.message(TaskStates.waiting_for_task_content, F.photo)
async def task_add_content_photo(message: Message, state: FSMContext):
    if not check_admin_access(message.from_user.id)[0]:
        return
    photo = message.photo[-1]
    await state.update_data(task_content=f"📸 Фото: {photo.file_id}")
    await finish_task_creation(message, state)

@router.message(TaskStates.waiting_for_task_content, F.video)
async def task_add_content_video(message: Message, state: FSMContext):
    if not check_admin_access(message.from_user.id)[0]:
        return
    await state.update_data(task_content=f"🎥 Видео: {message.video.file_id}")
    await finish_task_creation(message, state)

async def finish_task_creation(message: Message, state: FSMContext):
    data = await state.get_data()
    task_type = data.get("task_type", "text")
    content = data.get("task_content", "")
    
    task_id = add_task(
        title=data["task_title"],
        reward=data["task_reward"],
        description=data["task_desc"],
        task_type=task_type,
        content=content
    )
    
    if task_id:
        await message.answer(f"✅ <b>Задание создано!</b>\n\n🎯 {data['task_title']}\n💰 +{data['task_reward']} 🍬")
    else:
        await message.answer("❌ Ошибка")
    
    await state.clear()

@router.callback_query(F.data == "admin_task_list")
async def admin_task_list(call: CallbackQuery):
    user_id = call.from_user.id
    if not check_admin_access(user_id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    await safe_answer(call)
    
    tasks = get_all_tasks()
    if not tasks:
        await call.message.answer("📭 Нет заданий")
        return
    
    text = "📋 <b>СПИСОК ЗАДАНИЙ</b>\n\n"
    for task in tasks:
        text += f"🆔 <code>{task['id']}</code> | {task['title']} | +{task['reward']} 🍬\n"
    
    await call.message.answer(text)

@router.callback_query(F.data == "admin_task_remove")
async def admin_task_remove_menu(call: CallbackQuery):
    user_id = call.from_user.id
    if not check_admin_access(user_id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    await safe_answer(call)
    
    tasks = get_all_tasks()
    if not tasks:
        await call.message.answer("📭 Нет заданий")
        return
    
    keyboard = []
    for task in tasks:
        keyboard.append([InlineKeyboardButton(text=f"❌ {task['title']} (+{task['reward']})", callback_data=f"admin_task_del_{task['id']}")])
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_tasks")])
    
    await call.message.answer("🗑 <b>УДАЛЕНИЕ</b>\n\nВыберите задание:", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

@router.callback_query(F.data.startswith("admin_task_del_"))
async def admin_task_delete(call: CallbackQuery):
    user_id = call.from_user.id
    if not check_admin_access(user_id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    task_id = int(call.data.replace("admin_task_del_", ""))
    
    if delete_task(task_id):
        await safe_answer(call, "✅ Удалено")
        await call.message.edit_text("✅ Задание удалено")
    else:
        await safe_answer(call, "❌ Ошибка")

@router.callback_query(F.data == "admin_task_pending")
async def admin_task_pending(call: CallbackQuery):
    user_id = call.from_user.id
    if not check_admin_access(user_id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    await safe_answer(call)
    
    submissions = get_pending_submissions()
    if not submissions:
        await call.message.answer("📭 Нет заданий на проверке")
        return
    
    text = "⏳ <b>НА ПРОВЕРКЕ</b>\n\n"
    for sub in submissions:
        text += f"🆔 Заявка {sub['id']} | @{sub['username']} | {sub['title']} | +{sub['reward']} 🍬\n"
    
    await call.message.answer(text)

# ================= АДМИН - РАССЫЛКА =================
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
        f"📢 <b>Предпросмотр:</b>\n\n{text}\n\n"
        f"✅ Отправить?",
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
        await call.message.answer("❌ Ошибка")
        await state.clear()
        return
    
    cursor.execute("SELECT user_id FROM users")
    users = [row["user_id"] for row in cursor.fetchall()]
    
    sent = 0
    failed = 0
    
    status_msg = await call.message.answer(f"📢 Рассылка...\nВсего: {len(users)}")
    
    for i, uid in enumerate(users):
        try:
            await bot.send_message(uid, text)
            sent += 1
            if i % 10 == 0:
                await status_msg.edit_text(f"📢 Отправлено: {sent}/{len(users)}")
            await asyncio.sleep(0.05)
        except:
            failed += 1
    
    await status_msg.edit_text(f"📢 Готово!\n✅ {sent}\n❌ {failed}")
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
    await call.message.answer("❌ Отменено")
    await call.message.answer("👑 Админ-панель", reply_markup=get_admin_menu())

# ================= АДМИН - СОЗДАНИЕ ПРОМОКОДА =================
@router.callback_query(F.data == "admin_add_promo")
async def admin_add_promo(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    has_access, _, _, _ = check_admin_access(user_id)
    
    if not has_access:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    await safe_answer(call)
    await state.set_state(AdminStates.waiting_for_add_promo_code)
    await call.message.answer("🎟 Введите промокод:")

@router.message(AdminStates.waiting_for_add_promo_code)
async def process_add_promo_code(message: Message, state: FSMContext):
    user_id = message.from_user.id
    has_access, _, _, _ = check_admin_access(user_id)
    
    if not has_access:
        return
    
    code = message.text.upper().strip()
    await state.update_data(code=code)
    await state.set_state(AdminStates.waiting_for_add_promo_reward)
    await message.answer("🎁 Введите награду (🍬):")

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
        await message.answer("📊 Количество активаций:")
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
        await message.answer("❌ Введите число")
        return
    
    cursor.execute("SELECT code FROM promocodes WHERE UPPER(code) = UPPER(?)", (code,))
    if cursor.fetchone():
        await message.answer(f"❌ Промокод {code} уже существует!")
        await state.clear()
        return
    
    cursor.execute("INSERT INTO promocodes (code, reward, activations_left) VALUES (?, ?, ?)", (code, reward, uses))
    conn.commit()
    
    await message.answer(
        f"✅ <b>Промокод создан!</b>\n\n"
        f"🎟 <code>{code}</code>\n"
        f"🎁 +{reward} 🍬\n"
        f"📊 {uses} активаций"
    )
    await state.clear()
    await message.answer("👑 Админ-панель", reply_markup=get_admin_menu())

# ================= АДМИН - ДОБАВЛЕНИЕ БАЛАНСА =================
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
        target_id = int(message.text)
        await state.update_data(user_id=target_id)
        await state.set_state(AdminStates.waiting_for_add_balance_amount)
        await message.answer("💰 Введите сумму:")
    except ValueError:
        await message.answer("❌ Введите ID")

@router.message(AdminStates.waiting_for_add_balance_amount)
async def process_add_balance_amount(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    has_access, _, _, _ = check_admin_access(user_id)
    
    if not has_access:
        return
    
    data = await state.get_data()
    target_id = data.get('user_id')
    
    try:
        amount = int(message.text)
    except ValueError:
        await message.answer("❌ Введите число")
        return
    
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target_id))
    conn.commit()
    
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (target_id,))
    result = cursor.fetchone()
    
    if result:
        await message.answer(f"✅ +{amount} 🍬 пользователю {target_id}\n💰 Новый баланс: {result['balance']}")
        try:
            await bot.send_message(target_id, f"💰 Админ начислил {amount} 🍬\n💰 Баланс: {result['balance']}")
        except:
            pass
    else:
        await message.answer("❌ Пользователь не найден")
    
    await state.clear()
    await message.answer("👑 Админ-панель", reply_markup=get_admin_menu())

# ================= АДМИН - СНЯТИЕ БАЛАНСА =================
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
        target_id = int(message.text)
        await state.update_data(user_id=target_id)
        await state.set_state(AdminStates.waiting_for_remove_balance_amount)
        await message.answer("💰 Введите сумму для снятия:")
    except ValueError:
        await message.answer("❌ Введите ID")

@router.message(AdminStates.waiting_for_remove_balance_amount)
async def process_remove_balance_amount(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    has_access, _, _, _ = check_admin_access(user_id)
    
    if not has_access:
        return
    
    data = await state.get_data()
    target_id = data.get('user_id')
    
    try:
        amount = int(message.text)
    except ValueError:
        await message.answer("❌ Введите число")
        return
    
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (target_id,))
    result = cursor.fetchone()
    
    if not result:
        await message.answer("❌ Пользователь не найден")
        await state.clear()
        return
    
    if result["balance"] < amount:
        await message.answer(f"❌ Недостаточно средств. Баланс: {result['balance']}")
        await state.clear()
        return
    
    cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, target_id))
    conn.commit()
    
    new_balance = result["balance"] - amount
    await message.answer(f"✅ -{amount} 🍬 у пользователя {target_id}\n💰 Новый баланс: {new_balance}")
    
    try:
        await bot.send_message(target_id, f"⚠️ Админ снял {amount} 🍬\n💰 Баланс: {new_balance}")
    except:
        pass
    
    await state.clear()
    await message.answer("👑 Админ-панель", reply_markup=get_admin_menu())

# ================= АДМИН - УПРАВЛЕНИЕ АДМИНАМИ =================
@router.callback_query(F.data == "admin_manage")
async def admin_manage_menu_callback(call: CallbackQuery):
    user_id = call.from_user.id
    has_access, _, is_main, can_manage = check_admin_access(user_id, require_manage=True)
    
    if not has_access:
        await safe_answer(call, "❌ Нет прав", show_alert=True)
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
        await call.message.answer("📭 Нет админов")
        return
    
    text = "👥 <b>СПИСОК АДМИНОВ</b>\n\n"
    for admin in admins:
        username = admin['current_username'] or admin['username'] or "нет"
        role = "👑 ГЛАВНЫЙ" if admin['is_main_admin'] else "👤 Админ"
        can_add = "✅" if admin['can_add_admins'] else "❌"
        text += f"{role} | ID: <code>{admin['user_id']}</code>\n"
        text += f"└ @{username} | {can_add}\n\n"
    
    keyboard = [[InlineKeyboardButton(text="🔙 Назад", callback_data="admin_manage")]]
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

@router.callback_query(F.data == "admin_add")
async def admin_add_start(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    has_access, _, is_main, can_manage = check_admin_access(user_id, require_manage=True)
    
    if not has_access:
        await safe_answer(call, "❌ Нет прав", show_alert=True)
        return
    
    await safe_answer(call)
    await state.set_state(AdminStates.waiting_for_add_admin_id)
    await call.message.answer("➕ <b>Добавление админа</b>\n\nВведите ID пользователя:")

@router.message(AdminStates.waiting_for_add_admin_id)
async def admin_add_id(message: Message, state: FSMContext):
    if not check_admin_access(message.from_user.id)[0]:
        return
    
    try:
        admin_id = int(message.text.strip())
        await state.update_data(admin_id=admin_id)
        await state.set_state(AdminStates.waiting_for_add_admin_username)
        await message.answer("📝 Введите username:")
    except ValueError:
        await message.answer("❌ Введите ID")

@router.message(AdminStates.waiting_for_add_admin_username)
async def admin_add_username(message: Message, state: FSMContext):
    if not check_admin_access(message.from_user.id)[0]:
        return
    
    username = message.text.strip().replace('@', '')
    await state.update_data(username=username)
    await state.set_state(AdminStates.waiting_for_add_admin_permissions)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да", callback_data="admin_perm_yes")],
        [InlineKeyboardButton(text="❌ Нет", callback_data="admin_perm_no")]
    ])
    
    await message.answer(
        "🔐 <b>Права админа</b>\n\n"
        "Разрешить добавлять других админов?",
        reply_markup=keyboard
    )

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
            f"✅ <b>Админ добавлен!</b>\n\n"
            f"🆔 <code>{admin_id}</code>\n"
            f"👤 @{username}\n"
            f"🔐 {'✅ может добавлять' if can_add else '❌ обычный'}"
        )
    else:
        await safe_answer(call, "❌ Ошибка")
        await call.message.edit_text("❌ Ошибка")
    
    await state.clear()
    await call.message.answer("👥 Управление админами", reply_markup=admin_manage_menu)

@router.callback_query(F.data == "admin_remove")
async def admin_remove_menu(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    has_access, _, is_main, can_manage = check_admin_access(user_id, require_manage=True)
    
    if not has_access:
        await safe_answer(call, "❌ Нет прав", show_alert=True)
        return
    
    await safe_answer(call)
    
    admins = get_all_admins()
    if not admins:
        await call.message.answer("📭 Нет админов")
        return
    
    keyboard = []
    for admin in admins:
        if admin['is_main_admin']:
            continue
        username = admin['current_username'] or admin['username'] or "нет"
        keyboard.append([InlineKeyboardButton(text=f"❌ {username}", callback_data=f"admin_del_{admin['user_id']}")])
    
    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_manage")])
    
    await call.message.answer("🗑 <b>Удаление админа</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

@router.callback_query(F.data.startswith("admin_del_"))
async def admin_delete(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    has_access, _, is_main, can_manage = check_admin_access(user_id, require_manage=True)
    
    if not has_access:
        await safe_answer(call, "❌ Нет прав", show_alert=True)
        return
    
    admin_id = int(call.data.replace("admin_del_", ""))
    
    if remove_admin(admin_id):
        await safe_answer(call, "✅ Удален")
        await call.message.edit_text(f"✅ Админ {admin_id} удален")
    else:
        await safe_answer(call, "❌ Ошибка")
        await call.message.edit_text("❌ Ошибка")
    
    await admin_remove_menu(call, state)

# ================= АДМИН - УПРАВЛЕНИЕ ОП =================
@router.callback_query(F.data == "admin_op")
async def admin_op_menu(call: CallbackQuery):
    user_id = call.from_user.id
    has_access, _, _, _ = check_admin_access(user_id)
    
    if not has_access:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    await safe_answer(call)
    await call.message.answer("🔐 <b>Обязательная подписка</b>", reply_markup=op_menu)

@router.callback_query(F.data == "op_add")
async def op_add_start(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    has_access, _, _, _ = check_admin_access(user_id)
    
    if not has_access:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    await safe_answer(call)
    await state.set_state(OpStates.waiting_for_channel_id)
    await call.message.answer("📢 <b>Добавление канала</b>\n\nВведите ID канала:")

@router.message(OpStates.waiting_for_channel_id)
async def process_op_channel_id(message: Message, state: FSMContext):
    user_id = message.from_user.id
    has_access, _, _, _ = check_admin_access(user_id)
    
    if not has_access:
        return
    
    channel_id = message.text.strip()
    await state.update_data(channel_id=channel_id)
    await state.set_state(OpStates.waiting_for_channel_name)
    await message.answer("✏️ Введите название:")

@router.message(OpStates.waiting_for_channel_name)
async def process_op_channel_name(message: Message, state: FSMContext):
    user_id = message.from_user.id
    has_access, _, _, _ = check_admin_access(user_id)
    
    if not has_access:
        return
    
    channel_name = message.text.strip()
    await state.update_data(channel_name=channel_name)
    await state.set_state(OpStates.waiting_for_channel_link)
    await message.answer("🔗 Введите ссылку:")

@router.message(OpStates.waiting_for_channel_link)
async def process_op_channel_link(message: Message, state: FSMContext):
    user_id = message.from_user.id
    has_access, _, _, _ = check_admin_access(user_id)
    
    if not has_access:
        return
    
    channel_link = message.text.strip()
    data = await state.get_data()
    
    if add_mandatory_channel(data['channel_id'], data['channel_name'], channel_link):
        await message.answer(f"✅ Канал {data['channel_name']} добавлен!")
    else:
        await message.answer("❌ Ошибка")
    
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
        await call.message.answer("📭 Нет каналов")
        return
    
    keyboard = []
    for ch in channels:
        keyboard.append([InlineKeyboardButton(text=f"❌ {ch['channel_name']}", callback_data=f"op_del_{ch['channel_id']}")])
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_op")])
    
    await call.message.answer("🗑 <b>Удаление канала</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

@router.callback_query(F.data.startswith("op_del_"))
async def op_delete_channel(call: CallbackQuery):
    user_id = call.from_user.id
    has_access, _, _, _ = check_admin_access(user_id)
    
    if not has_access:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    channel_id = call.data.replace("op_del_", "")
    
    if remove_mandatory_channel(channel_id):
        await safe_answer(call, "✅ Удален")
    else:
        await safe_answer(call, "❌ Ошибка")
        return
    
    channels = get_mandatory_channels()
    if not channels:
        await call.message.edit_text("📭 Нет каналов")
        return
    
    keyboard = []
    for ch in channels:
        keyboard.append([InlineKeyboardButton(text=f"❌ {ch['channel_name']}", callback_data=f"op_del_{ch['channel_id']}")])
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_op")])
    
    await call.message.edit_text("🗑 <b>Удаление канала</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

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
        text = "📭 Нет каналов"
    else:
        text = "📋 <b>Каналы ОП:</b>\n\n"
        for ch in channels:
            text += f"• <b>{ch['channel_name']}</b>\n  ID: <code>{ch['channel_id']}</code>\n  {ch['channel_link']}\n\n"
    
    keyboard = [[InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_op")]]
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ================= АДМИН - УПРАВЛЕНИЕ =================
@router.callback_query(F.data == "admin_panel")
async def admin_panel(call: CallbackQuery):
    user_id = call.from_user.id
    has_access, _, is_main, can_manage = check_admin_access(user_id)
    
    if not has_access:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    await safe_answer(call)
    await call.message.answer("👑 Админ-панель", reply_markup=get_admin_menu(is_main, can_manage))

# ================= ПРОВЕРКА ПОДПИСКИ =================
@router.callback_query(F.data == "check_subscribe")
async def check_subscribe_callback(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    await safe_answer(call)
    
    if await check_subscription(bot, user_id):
        if not has_received_subscribe_bonus(user_id):
            cursor.execute("UPDATE users SET balance = balance + ?, subscribe_bonus_received = 1 WHERE user_id = ?", (SUBSCRIBE_BONUS, user_id))
            conn.commit()
            bonus_text = f"\n\n🎁 +{SUBSCRIBE_BONUS} 🍬"
        else:
            bonus_text = ""
        
        await state.clear()
        try:
            await call.message.delete()
        except:
            pass
        await call.message.answer(f"✅ <b>Доступ получен!</b>{bonus_text}")
        await call.message.answer("🎥 Видео платформа", reply_markup=main_menu)
    else:
        await call.message.answer("❌ Вы не подписались!")

# ================= ДОБАВЛЯЕМ КОМАНДЫ УДАЛЕНИЯ =================
@router.message(Command("delete_200"))
async def delete_first_200_command(message: Message):
    user_id = message.from_user.id
    if not is_main_admin(user_id):
        await message.answer("❌ Только главный админ")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да", callback_data="confirm_delete_200"),
         InlineKeyboardButton(text="❌ Нет", callback_data="cancel_delete")]
    ])
    
    await message.answer(
        "⚠️ <b>Удаление 200 видео</b>\n\n"
        "Это действие нельзя отменить!\n\n"
        "Подтвердите:",
        reply_markup=keyboard
    )

@router.message(Command("delete_58"))
async def delete_first_58_command(message: Message):
    user_id = message.from_user.id
    if not is_main_admin(user_id):
        await message.answer("❌ Только главный админ")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да", callback_data="confirm_delete_58"),
         InlineKeyboardButton(text="❌ Нет", callback_data="cancel_delete")]
    ])
    
    await message.answer(
        "⚠️ <b>Удаление 58 видео</b>\n\n"
        "Это действие нельзя отменить!\n\n"
        "Подтвердите:",
        reply_markup=keyboard
    )

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
            await call.message.edit_text("📭 Нет видео")
            return
        
        video_ids = [v["id"] for v in videos]
        placeholders = ','.join(['?'] * len(video_ids))
        
        cursor.execute(f"DELETE FROM user_videos WHERE video_id IN ({placeholders})", video_ids)
        deleted_views = cursor.rowcount
        cursor.execute(f"DELETE FROM videos WHERE id IN ({placeholders})", video_ids)
        deleted_videos = cursor.rowcount
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='videos'")
        conn.commit()
        
        await call.message.edit_text(f"✅ <b>Удалено!</b>\n\n🎥 {deleted_videos} видео\n👀 {deleted_views} просмотров")
        
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
            await call.message.edit_text("📭 Нет видео")
            return
        
        video_ids = [v["id"] for v in videos]
        placeholders = ','.join(['?'] * len(video_ids))
        
        cursor.execute(f"DELETE FROM user_videos WHERE video_id IN ({placeholders})", video_ids)
        deleted_views = cursor.rowcount
        cursor.execute(f"DELETE FROM videos WHERE id IN ({placeholders})", video_ids)
        deleted_videos = cursor.rowcount
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='videos'")
        conn.commit()
        
        await call.message.edit_text(f"✅ <b>Удалено!</b>\n\n🎥 {deleted_videos} видео\n👀 {deleted_views} просмотров")
        
    except Exception as e:
        await call.message.edit_text(f"❌ Ошибка: {e}")

@router.callback_query(F.data == "cancel_delete")
async def cancel_delete(call: CallbackQuery):
    await safe_answer(call)
    await call.message.edit_text("❌ Отменено")

# ================= ТЕСТОВЫЕ КОМАНДЫ =================
@router.message(Command("test_captcha"))
async def test_captcha_command(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if not check_admin_access(user_id)[0]:
        await message.answer("❌ Только для админов")
        return
    
    image_bytes, captcha_code = generate_captcha_image()
    
    await message.answer_photo(
        photo=BufferedInputFile(file=image_bytes, filename="captcha.png"),
        caption=f"🔐 <b>ТЕСТ КАПЧИ</b>\n\nКод: <code>{captcha_code}</code>"
    )

@router.message(Command("list_promos"))
async def list_promos_command(message: Message):
    user_id = message.from_user.id
    if not check_admin_access(user_id)[0]:
        return
    
    cursor.execute("SELECT code, reward, activations_left FROM promocodes ORDER BY code")
    promos = cursor.fetchall()
    
    if not promos:
        await message.answer("📭 Нет промокодов")
        return
    
    text = "📋 <b>Промокоды:</b>\n\n"
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
            target_id = int(args[1])
        else:
            target_id = message.from_user.id
    except:
        await message.answer("❌ Используйте: /balance [user_id]")
        return
    
    cursor.execute("SELECT balance, username FROM users WHERE user_id = ?", (target_id,))
    user = cursor.fetchone()
    
    if not user:
        await message.answer("❌ Пользователь не найден")
        return
    
    await message.answer(f"👤 {target_id} (@{user['username'] or 'нет'})\n🍬 Баланс: {user['balance']}")

# ================= БЭКАП БАЗЫ =================
@router.message(Command("backup_db"))
async def backup_db_command(message: Message):
    user_id = message.from_user.id
    if not is_main_admin(user_id):
        await message.answer("❌ Только главный админ")
        return
    
    await message.answer("🔄 Создаю бэкап...")
    
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        backup_data = {}
        for table in tables:
            table_name = table[0]
            cursor.execute(f"SELECT * FROM {table_name}")
            rows = cursor.fetchall()
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [col[1] for col in cursor.fetchall()]
            backup_data[table_name] = {"columns": columns, "data": [dict(row) for row in rows]}
        
        import json
        from datetime import datetime
        backup_json = json.dumps(backup_data, ensure_ascii=False, indent=2, default=str)
        
        await message.answer_document(
            document=BufferedInputFile(backup_json.encode('utf-8'), filename=f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"),
            caption=f"✅ Бэкап {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

# ================= ВОССТАНОВЛЕНИЕ БАЗЫ =================
@router.message(Command("restore"))
async def restore_db_command(message: Message):
    user_id = message.from_user.id
    if not is_main_admin(user_id):
        await message.answer("❌ Только главный админ")
        return
    
    global waiting_for_restore_file, restore_user_id
    waiting_for_restore_file = True
    restore_user_id = user_id
    
    await message.answer(
        "📤 <b>Восстановление</b>\n\n"
        "Отправьте JSON файл бэкапа.\n"
        "⚠️ База будет заменена!\n\n"
        "⏳ 120 секунд"
    )
    
    async def exit_restore_mode():
        await asyncio.sleep(120)
        global waiting_for_restore_file, restore_user_id
        waiting_for_restore_file = False
        restore_user_id = None
    
    asyncio.create_task(exit_restore_mode())

@router.message(F.document)
async def handle_restore_file(message: Message, bot: Bot):
    global waiting_for_restore_file, restore_user_id
    if not waiting_for_restore_file or message.from_user.id != restore_user_id:
        return
    
    if not message.document.file_name.endswith('.json'):
        await message.answer("❌ Нужен .json")
        waiting_for_restore_file = False
        restore_user_id = None
        return
    
    status_msg = await message.answer("🔄 Восстанавливаю...")
    
    try:
        file = await bot.get_file(message.document.file_id)
        file_bytes = await bot.download_file(file.file_path)
        
        import json
        backup_data = json.loads(file_bytes.read().decode('utf-8'))
        
        cursor.execute("BEGIN TRANSACTION")
        
        tables = ['users', 'videos', 'payments', 'promocodes', 'used_promocodes', 'user_videos', 'tasks', 'completed_tasks', 'private_access']
        for table_name in tables:
            if table_name in backup_data:
                cursor.execute(f"DELETE FROM {table_name}")
                table_info = backup_data[table_name]
                columns = table_info.get("columns", [])
                rows = table_info.get("data", [])
                if rows and columns:
                    placeholders = ','.join(['?'] * len(columns))
                    for row in rows:
                        values = [row.get(col) for col in columns]
                        try:
                            cursor.execute(f"INSERT INTO {table_name} ({','.join(columns)}) VALUES ({placeholders})", values)
                        except:
                            pass
        
        try:
            cursor.execute("DELETE FROM sqlite_sequence")
        except:
            pass
        
        conn.commit()
        
        cursor.execute("SELECT COUNT(*) as count FROM users")
        users_count = cursor.fetchone()["count"]
        cursor.execute("SELECT COUNT(*) as count FROM videos")
        videos_count = cursor.fetchone()["count"]
        
        await status_msg.edit_text(f"✅ <b>База восстановлена!</b>\n\n👥 {users_count}\n🎥 {videos_count}")
        
    except Exception as e:
        conn.rollback()
        await status_msg.edit_text(f"❌ Ошибка: {e}")
    finally:
        waiting_for_restore_file = False
        restore_user_id = None

# ================= ОСТАНОВКА ДУБЛИКАТОВ =================
@router.message(Command("stop_duplicates"))
async def stop_duplicates_command(message: Message, bot: Bot):
    user_id = message.from_user.id
    if not is_main_admin(user_id):
        await message.answer("❌ Только главный админ")
        return
    
    await message.answer("🔍 Проверяю...")
    
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await message.answer("✅ Webhook отключен")
        
        import fcntl
        lock_file_path = "/tmp/bot_single_instance.lock"
        try:
            lock_file = open(lock_file_path, 'w')
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            await message.answer("✅ Lock файл создан")
        except:
            await message.answer("⚠️ Lock уже существует")
            
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    
    await message.answer(
        "📊 <b>Решение:</b>\n\n"
        "1. Зайдите в Railway Dashboard\n"
        "2. Остановите все лишние деплои\n"
        "3. Оставьте один активный\n"
        "4. Перезапустите бота"
    )