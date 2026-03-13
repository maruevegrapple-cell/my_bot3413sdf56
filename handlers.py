import asyncio
import time
import random
import logging
import io
import string
import os
import requests
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from aiogram import Router, F
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
)

from db import (
    cursor, conn, get_mandatory_channels, add_mandatory_channel, remove_mandatory_channel,
    has_received_subscribe_bonus, mark_subscribe_bonus_received,
    is_admin, is_main_admin, can_manage_admins, get_all_admins, add_admin, remove_admin,
    set_main_admin, get_main_admin_id
)
from keyboards import (
    fake_menu, main_menu, video_menu, shop_menu, get_admin_menu, 
    confirm_menu, subscribe_menu, op_menu, admin_manage_menu
)
from payments import create_invoice, check_invoice, AVAILABLE_ASSETS, get_asset_icon

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = Router()

# Временная директория для видео
TEMP_DIR = "temp_videos"
os.makedirs(TEMP_DIR, exist_ok=True)

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

class CaptchaStates(StatesGroup):
    waiting_for_captcha = State()

class SubscribeStates(StatesGroup):
    waiting_for_subscribe = State()
    waiting_for_support_message = State()

class CustomPayStates(StatesGroup):
    waiting_for_amount = State()

class OpStates(StatesGroup):
    waiting_for_channel_id = State()
    waiting_for_channel_name = State()
    waiting_for_channel_link = State()

# ================= ХРАНИЛИЩЕ ДАННЫХ =================
captcha_data = {}
captcha_attempts = {}
banned_users = {}
broadcast_mode = set()
custom_pay_wait = set()

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
    # Проверяем, является ли пользователь главным админом
    if is_main_admin(user_id):
        return True, True, True, True
    
    # Проверяем, является ли пользователь обычным админом
    if is_admin(user_id):
        can_manage = can_manage_admins(user_id)
        # Если требуются права главного, но пользователь не главный
        if require_main:
            return False, True, False, can_manage
        # Если требуются права управления админами
        if require_manage and not can_manage:
            return False, True, False, can_manage
        # Все проверки пройдены - даем доступ
        return True, True, False, can_manage
    
    # Не админ
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
    # Админы всегда имеют доступ
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

# ================= ГЕНЕРАЦИЯ КАПЧИ (НОРМАЛЬНАЯ ВИДИМАЯ) =================
def generate_captcha_image() -> tuple:
    """Генерация изображения капчи - БОЛЬШИЕ ВИДИМЫЕ БУКВЫ"""
    length = 4
    chars = string.ascii_uppercase + string.digits
    # Убираем похожие символы
    exclude = ['O', '0', 'I', '1', 'S', '5', 'Z', '2']
    for c in exclude:
        chars = chars.replace(c, '')
    code = ''.join(random.choices(chars, k=length))
    
    # РАЗМЕР
    width, height = 800, 300
    
    # Создаем изображение с белым фоном
    image = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(image)
    
    # Заливка фона
    draw.rectangle([(0, 0), (width, height)], fill=(255, 255, 255))
    
    # Добавляем легкие серые линии для защиты
    for i in range(0, width, 50):
        draw.line([(i, 0), (i, height)], fill=(230, 230, 230), width=1)
    for i in range(0, height, 50):
        draw.line([(0, i), (width, i)], fill=(230, 230, 230), width=1)
    
    # Пытаемся загрузить жирный шрифт
    font = None
    try:
        # Пробуем разные шрифты
        font_paths = [
            "C:\\Windows\\Fonts\\Arial.ttf",
            "C:\\Windows\\Fonts\\Impact.ttf",
            "C:\\Windows\\Fonts\\arialbd.ttf",  # Arial Bold
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "arial.ttf"
        ]
        
        for path in font_paths:
            if os.path.exists(path):
                font = ImageFont.truetype(path, 80)  # Размер 80px
                print(f"✅ Загружен шрифт: {path}")
                break
    except:
        font = None
    
    if font is None:
        # Если нет шрифтов, используем встроенный но рисуем жирно
        font = ImageFont.load_default()
        print("⚠️ Используется встроенный шрифт")
    
    # Рисуем буквы жирно и крупно
    colors = [
        (0, 0, 0),        # черный
        (0, 0, 150),      # синий
        (150, 0, 0),      # красный
        (0, 150, 0),      # зеленый
    ]
    
    # Позиции для букв
    positions = [(120, 100), (270, 100), (420, 100), (570, 100)]
    
    for i, char in enumerate(code):
        x, y = positions[i]
        color = colors[i % len(colors)]
        
        if font != ImageFont.load_default():
            # Для нормального шрифта рисуем жирно с обводкой
            # Обводка
            for dx in [-2, -1, 0, 1, 2]:
                for dy in [-2, -1, 0, 1, 2]:
                    if dx != 0 or dy != 0:
                        draw.text((x + dx, y + dy), char, fill=(200, 200, 200), font=font)
            # Основная буква
            draw.text((x, y), char, fill=color, font=font)
        else:
            # Для встроенного шрифта рисуем несколько раз
            for dx in range(-3, 4):
                for dy in range(-3, 4):
                    draw.text((x + dx, y + dy), char, fill=color, font=font)
    
    # Добавляем немного шума точками
    for _ in range(100):
        x = random.randint(0, width)
        y = random.randint(0, height)
        draw.point((x, y), fill=(100, 100, 100))
    
    # Сохраняем
    bio = io.BytesIO()
    image.save(bio, 'PNG', quality=95)
    bio.seek(0)
    
    print(f"✅ Капча сгенерирована: {code}")
    return bio.getvalue(), code

# ================= БЛОКИРОВКА ПЕРЕСЫЛКИ =================
@router.message(F.forward_from | F.forward_from_chat)
async def block_forward(message: Message):
    await message.delete()

# ================= ЗАГРУЗКА ВИДЕО (ДЛЯ ВСЕХ АДМИНОВ) =================
@router.message(F.video)
async def upload_video(message: Message):
    user_id = message.from_user.id
    
    logger.info(f"📹 ВИДЕО ПОЛУЧЕНО от пользователя {user_id}")
    
    has_access, is_admin_user, is_main, _ = check_admin_access(user_id)
    
    if not has_access:
        logger.info(f"📹 Видео от обычного пользователя {user_id} проигнорировано")
        return
    
    logger.info(f"📹 Админ {user_id} загружает видео")
    
    file_id = message.video.file_id
    file_name = message.video.file_name if message.video.file_name else "без названия"
    file_size = message.video.file_size
    duration = message.video.duration
    
    logger.info(f"📹 Детали видео - ID: {file_id}, Name: {file_name}, Size: {file_size}, Duration: {duration}")
    
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
        
        await message.answer(
            f"✅ <b>ВИДЕО УСПЕШНО ДОБАВЛЕНО!</b>\n\n"
            f"📹 <b>Название:</b> {file_name}\n"
            f"🆔 <b>File ID:</b> <code>{file_id}</code>\n"
            f"🔢 <b>Номер в базе:</b> {video_id}\n"
            f"⏱ <b>Длительность:</b> {duration} сек\n"
            f"📊 <b>Размер:</b> {file_size // 1024} KB\n"
            f"🎥 <b>Всего видео в базе:</b> {total_videos}"
        )
        logger.info(f"✅ Видео {video_id} добавлено в базу: {file_id}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при добавлении видео: {e}")
        await message.answer(f"❌ Ошибка при добавлении видео: {e}")

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
    await call.message.answer(
        "🔗 <b>Загрузка видео по ссылке</b>\n\n"
        "Отправьте ссылку на видео.\n\n"
        "Поддерживаются:\n"
        "• Прямые ссылки на .mp4\n"
        "• Google Drive\n"
        "• Dropbox\n"
        "• Любые другие ссылки"
    )

@router.message(AdminStates.waiting_for_cloud_url)
async def process_video_url(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    has_access, _, _, _ = check_admin_access(user_id)
    
    if not has_access:
        return
    
    url = message.text.strip()
    await state.clear()
    
    status_msg = await message.answer("🔄 Обрабатываю ссылку...")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
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
        conn.commit()
        
        os.remove(filename)
        
        cursor.execute("SELECT COUNT(*) as count FROM videos")
        total = cursor.fetchone()["count"]
        
        await message.answer(
            f"✅ <b>ВИДЕО УСПЕШНО ДОБАВЛЕНО!</b>\n\n"
            f"📹 <b>File ID:</b> <code>{file_id}</code>\n"
            f"📊 <b>Размер:</b> {file_size // (1024 * 1024)} MB\n"
            f"🎥 <b>Всего видео в базе:</b> {total}\n\n"
            f"💡 Теперь можно смотреть!"
        )
        
    except requests.exceptions.Timeout:
        await status_msg.edit_text("❌ Таймаут при скачивании. Ссылка недоступна.")
    except requests.exceptions.ConnectionError:
        await status_msg.edit_text("❌ Ошибка соединения. Проверьте ссылку.")
    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка: {e}")
        if os.path.exists(filename):
            os.remove(filename)

# ================= БЫСТРАЯ ЗАГРУЗКА ПО КОМАНДЕ =================
@router.message(Command("dl"))
async def quick_download(message: Message):
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
        conn.commit()
        
        os.remove(filename)
        
        await message.answer(f"✅ Готово! ID: <code>{file_id}</code>")
        
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

# ================= СТАРТ =================
@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username or "пользователь"
    first_name = message.from_user.first_name or "Пользователь"
    
    logger.info(f"🟢 START command from user {user_id} (@{username})")
    
    # Проверка на бан
    banned, ban_until = is_banned(user_id)
    if banned:
        remaining = ban_until - datetime.now()
        minutes = remaining.seconds // 60
        seconds = remaining.seconds % 60
        await message.answer(
            f"🚫 <b>ДОСТУП ЗАБЛОКИРОВАН</b>\n\n"
            f"Причина: слишком много неверных попыток ввода капчи\n"
            f"⏳ Осталось: {minutes} мин {seconds} сек"
        )
        return
    
    # Проверка на админа
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
    
    # Получаем информацию о пользователе
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    
    # Проверка на реферальный код
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
                logger.info(f"🔗 Реферальная ссылка обнаружена! Код: {ref_code}, Реферер: {referrer_id}")
    
    # ========== ВАЖНО: ЕСЛИ В ССЫЛКЕ ЕСТЬ РЕФ КОД ==========
    if has_ref_in_link:
        logger.info(f"✅ Пользователь {user_id} перешел по реферальной ссылке")
        
        # Проверяем, существует ли пользователь
        if user:
            # Пользователь уже есть - НЕ НАЧИСЛЯЕМ БОНУС (не новый)
            logger.info(f"🔄 Пользователь {user_id} уже существует. Бонус рефереру НЕ начислен.")
        else:
            # Создаем НОВОГО пользователя с реферером
            logger.info(f"🆕 Создаем НОВОГО пользователя {user_id} с реферером {referrer_id}")
            new_ref_code = generate_ref_code()
            cursor.execute("""
                INSERT INTO users (user_id, username, referrer, is_verified, ref_code, subscribe_bonus_received, is_admin)
                VALUES (?, ?, ?, 0, ?, 0, 0)
            """, (user_id, username, referrer_id, new_ref_code))
            conn.commit()
            
            # Начисляем бонус рефереру (ТОЛЬКО ЗА НОВОГО)
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", 
                          (REF_BONUS, referrer_id))
            conn.commit()
            
            try:
                await message.bot.send_message(
                    referrer_id,
                    f"🎁 <b>Новый реферал!</b>\n\n"
                    f"По вашей ссылке зарегистрировался новый пользователь @{username}\n"
                    f"➕ Вам начислено +{REF_BONUS} 🍬",
                    parse_mode="HTML"
                )
            except:
                pass
        
        # ВЕРИФИКАЦИЯ - если пользователь не верифицирован
        if not is_verified(user_id):
            logger.info(f"🔐 Пользователь {user_id} не верифицирован, отправляем капчу")
            if user_id in captcha_attempts:
                del captcha_attempts[user_id]
            
            image_bytes, captcha_code = generate_captcha_image()
            captcha_data[user_id] = captcha_code
            await state.update_data(captcha_code=captcha_code)
            await state.set_state(CaptchaStates.waiting_for_captcha)
            
            await message.answer_photo(
                photo=BufferedInputFile(file=image_bytes, filename="captcha.png"),
                caption="🔐 <b>ПОДТВЕРЖДЕНИЕ</b>\n\n"
                        "Введите код с картинки:\n"
                        "⚠️ Только заглавные буквы и цифры\n"
                        "📊 Осталось попыток: 3/3"
            )
            return
        
        # Если верифицирован - проверяем подписку
        if is_verified(user_id):
            logger.info(f"✅ Пользователь {user_id} верифицирован, проверяем подписку")
            is_subscribed = await check_subscription(message.bot, user_id)
            if not is_subscribed:
                await state.set_state(SubscribeStates.waiting_for_subscribe)
                await message.answer(
                    f"<b>{first_name}🥰!</b>\n\n"
                    f"Для доступа к боту, вам нужно подписаться на наш канал!\n"
                    f"— ведь за подписку мы дарим каждый день по {SUBSCRIBE_BONUS} 🍬!",
                    reply_markup=subscribe_menu
                )
                return
            
            logger.info(f"🎉 Пользователь {user_id} получает доступ к основному меню!")
            await message.answer("🎥 Видео платформа", reply_markup=main_menu)
            return
    
    # ========== ЕСЛИ В ССЫЛКЕ НЕТ РЕФ КОДА ==========
    
    # Создание нового пользователя, если его нет
    if not user:
        new_ref_code = generate_ref_code()
        
        cursor.execute("""
            INSERT INTO users (user_id, username, referrer, is_verified, ref_code, subscribe_bonus_received, is_admin)
            VALUES (?, ?, ?, 0, ?, 0, 0)
        """, (user_id, username, referrer_id, new_ref_code))
        conn.commit()
        
        # Если есть реферер и пользователь новый - начисляем бонус
        if referrer_id:
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", 
                          (REF_BONUS, referrer_id))
            conn.commit()
            
            try:
                await message.bot.send_message(
                    referrer_id,
                    f"🎁 <b>Новый реферал!</b>\n\n"
                    f"По вашей ссылке зарегистрировался новый пользователь @{username}\n"
                    f"➕ Вам начислено +{REF_BONUS} 🍬",
                    parse_mode="HTML"
                )
            except:
                pass
    else:
        if not user["ref_code"]:
            new_ref_code = generate_ref_code()
            cursor.execute("UPDATE users SET ref_code = ? WHERE user_id = ?", 
                          (new_ref_code, user_id))
            conn.commit()
    
    # Если у пользователя нет реферера (и не получил сейчас) - показываем фейк меню
    if not has_referrer(user_id) and not referrer_id:
        await message.answer(
            f"Привет, @{username}. Добро пожаловать в главное меню!",
            reply_markup=fake_menu
        )
        return
    
    # Если есть реферальная ссылка (была раньше или сейчас), но не верифицирован - капча
    if not is_verified(user_id):
        if user_id in captcha_attempts:
            del captcha_attempts[user_id]
        
        image_bytes, captcha_code = generate_captcha_image()
        captcha_data[user_id] = captcha_code
        await state.update_data(captcha_code=captcha_code)
        await state.set_state(CaptchaStates.waiting_for_captcha)
        
        await message.answer_photo(
            photo=BufferedInputFile(file=image_bytes, filename="captcha.png"),
            caption="🔐 <b>ПОДТВЕРЖДЕНИЕ</b>\n\n"
                    "Введите код с картинки:\n"
                    "⚠️ Только заглавные буквы и цифры\n"
                    "📊 Осталось попыток: 3/3"
        )
        return
    
    # Если верифицирован - проверяем подписку
    if is_verified(user_id):
        is_subscribed = await check_subscription(message.bot, user_id)
        if not is_subscribed:
            await state.set_state(SubscribeStates.waiting_for_subscribe)
            await message.answer(
                f"<b>{first_name}🥰!</b>\n\n"
                f"Для доступа к боту, вам нужно подписаться на наш канал!\n"
                f"— ведь за подписку мы дарим каждый день по {SUBSCRIBE_BONUS} 🍬!",
                reply_markup=subscribe_menu
            )
            return
        
        await message.answer("🎥 Видео платформа", reply_markup=main_menu)

# ================= ОБРАБОТКА КАПЧИ =================
@router.message(CaptchaStates.waiting_for_captcha)
async def process_captcha(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user_input = message.text.strip().upper()
    
    logger.info(f"🔍 Captcha input from user {user_id}: {user_input}")
    
    banned, ban_until = is_banned(user_id)
    if banned:
        remaining = ban_until - datetime.now()
        minutes = remaining.seconds // 60
        seconds = remaining.seconds % 60
        await message.answer(
            f"🚫 <b>ДОСТУП ЗАБЛОКИРОВАН</b>\n\n"
            f"Причина: слишком много неверных попыток ввода капчи\n"
            f"⏳ Осталось: {minutes} мин {seconds} сек"
        )
        await state.clear()
        return
    
    data = await state.get_data()
    correct_code = data.get('captcha_code') or captcha_data.get(user_id)
    
    logger.info(f"✅ Correct captcha code: {correct_code}")
    
    if not correct_code:
        await message.answer("❌ Ошибка верификации. Нажми /start заново")
        await state.clear()
        return
    
    if user_input == correct_code:
        cursor.execute("UPDATE users SET is_verified = 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        
        if user_id in captcha_data:
            del captcha_data[user_id]
        if user_id in captcha_attempts:
            del captcha_attempts[user_id]
        await state.clear()
        
        first_name = message.from_user.first_name or "Пользователь"
        is_subscribed = await check_subscription(message.bot, user_id)
        
        if not is_subscribed:
            await state.set_state(SubscribeStates.waiting_for_subscribe)
            await message.answer(
                f"<b>{first_name}🥰!</b>\n\n"
                f"Для доступа к боту, вам нужно подписаться на наш канал!\n"
                f"— ведь за подписку мы дарим каждый день по {SUBSCRIBE_BONUS} 🍬!",
                reply_markup=subscribe_menu
            )
        else:
            await message.answer(
                f"✅ <b>Верификация пройдена!</b>\n\nДобро пожаловать!",
                reply_markup=main_menu
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

# ================= КАСТОМНАЯ ОПЛАТА =================
@router.message(CustomPayStates.waiting_for_amount)
async def process_custom_pay(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if not await check_access(message.bot, user_id, state, message=message):
        return
    
    logger.info(f"💰 Custom pay input from user {user_id}: {message.text}")
    
    try:
        amount = int(message.text.strip())
        if amount < 1:
            await message.answer("❌ Минимальное количество: 1 🍬")
            return
        if amount > 10000:
            await message.answer("❌ Максимальное количество: 10000 🍬")
            return
        
        usdt = round(amount * 0.003, 2)
        
        if usdt < 0.1:
            usdt = 0.1
        
        # Сохраняем данные для выбора валюты
        await state.update_data(pay_amount=amount, pay_usdt=usdt, pay_custom=True)
        
        # Показываем меню выбора валюты ГОРИЗОНТАЛЬНОЕ
        keyboard = []
        row = []
        for i, asset in enumerate(AVAILABLE_ASSETS):
            icon = get_asset_icon(asset)
            row.append(InlineKeyboardButton(text=f"{icon} {asset}", callback_data=f"pay_asset_{asset}"))
            if (i + 1) % 3 == 0:  # По 3 в ряд
                keyboard.append(row)
                row = []
        if row:  # Остаток
            keyboard.append(row)
        
        await message.answer(
            f"💳 <b>Выберите валюту для оплаты</b>\n\n"
            f"🍬 Конфет: {amount}\n"
            f"💵 Сумма: {usdt} USD\n\n"
            f"Курс будет сконвертирован автоматически:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        
    except ValueError:
        await message.answer("❌ Введите корректное число")
        return

# ================= ОПЛАТА С ВЫБОРОМ КРИПТЫ =================
@router.callback_query(F.data.startswith("pay_"))
async def pay(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    
    print(f"💰 pay called with data: {call.data}")  # ОТЛАДКА
    
    if not await check_access(call.bot, user_id, state, call=call):
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
        await call.message.answer("💰 Введите желаемое количество конфет (число):")
        return
    
    if call.data not in prices:
        print(f"❌ Unknown pay data: {call.data}")
        return
    
    amount, usdt = prices[call.data]
    print(f"✅ Selected: {amount} candies for ${usdt}")
    
    # Сохраняем сумму в state для выбора валюты
    await state.update_data(pay_amount=amount, pay_usdt=usdt, pay_custom=False)
    
    # Показываем меню выбора валюты ГОРИЗОНТАЛЬНОЕ
    keyboard = []
    row = []
    for i, asset in enumerate(AVAILABLE_ASSETS):
        icon = get_asset_icon(asset)
        row.append(InlineKeyboardButton(text=f"{icon} {asset}", callback_data=f"pay_asset_{asset}"))
        if (i + 1) % 3 == 0:  # По 3 в ряд
            keyboard.append(row)
            row = []
    if row:  # Остаток
        keyboard.append(row)
    
    await call.message.answer(
        f"💳 <b>Выберите валюту для оплаты</b>\n\n"
        f"🍬 Конфет: {amount}\n"
        f"💵 Сумма: {usdt} USD\n\n"
        f"Курс будет сконвертирован автоматически:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@router.callback_query(F.data.startswith("pay_asset_"))
async def pay_with_asset(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    
    print(f"💰 pay_with_asset called with data: {call.data}")  # ОТЛАДКА
    
    if not await check_access(call.bot, user_id, state, call=call):
        return
    
    asset = call.data.replace("pay_asset_", "")
    print(f"✅ Selected asset: {asset}")
    
    data = await state.get_data()
    amount = data.get('pay_amount')
    usdt = data.get('pay_usdt')
    
    if not amount or not usdt:
        await safe_answer(call, "❌ Ошибка: данные платежа не найдены", show_alert=True)
        return
    
    # Получаем курсы для отображения
    from payments import get_exchange_rates
    rates = get_exchange_rates()
    rate_text = ""
    crypto_amount = usdt
    
    if rates and asset in rates:
        rate = rates[asset]
        crypto_amount = round(usdt / rate, 8)
        rate_text = f"\n1 {asset} = {rate} USD\n💰 К оплате: {crypto_amount} {asset}"
    
    invoice = create_invoice(usdt, asset)
    
    cursor.execute(
        "INSERT INTO payments (invoice_id, user_id, amount) VALUES (?, ?, ?)",
        (invoice["invoice_id"], user_id, amount)
    )
    conn.commit()
    
    icon = get_asset_icon(asset)
    
    await call.message.answer(
        f"💳 <b>Оплата в {icon} {asset}</b>\n\n"
        f"🍬 Конфет: {amount}\n"
        f"💵 Сумма: {usdt} USD{rate_text}\n\n"
        f"🔄 Курс обновлен в реальном времени",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"💰 Оплатить {crypto_amount} {asset}", url=invoice["pay_url"])],
            [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_{invoice['invoice_id']}")]
        ])
    )
    
    await state.clear()

# ================= ПРОВЕРКА ПОДПИСКИ (ИСПРАВЛЕНО) =================
@router.callback_query(F.data == "check_subscribe")
async def check_subscribe_callback(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    
    await safe_answer(call)
    
    # Проверяем подписку на канал
    is_subscribed = await check_subscription(call.bot, user_id)
    
    if is_subscribed:
        # Проверяем, получал ли уже бонус
        try:
            bonus_received = has_received_subscribe_bonus(user_id)
        except:
            bonus_received = False
        
        if not bonus_received:
            cursor.execute("""
                UPDATE users 
                SET balance = balance + ?, subscribe_bonus_received = 1 
                WHERE user_id = ?
            """, (SUBSCRIBE_BONUS, user_id))
            conn.commit()
            
            bonus_text = f"\n\n🎁 Вам начислено +{SUBSCRIBE_BONUS} 🍬 за подписку!"
        else:
            bonus_text = ""
        
        await state.clear()
        
        try:
            await call.message.delete()
        except:
            pass
        
        # Сначала отправляем сообщение о доступе
        await call.message.answer(f"✅ <b>Доступ получен!</b>{bonus_text}")
        
        # Потом отправляем основное меню
        await call.message.answer("🎥 Видео платформа", reply_markup=main_menu)
    else:
        try:
            await call.message.answer("❌ Вы еще не подписались на канал!")
        except:
            pass

# ================= ПРОВЕРКА ПЛАТЕЖА (ИСПРАВЛЕНО) =================
@router.callback_query(F.data.startswith("check_"))
async def check_payment(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    
    # ВАЖНО: пропускаем check_subscribe
    if call.data == "check_subscribe":
        return
    
    if not await check_access(call.bot, user_id, state, call=call):
        return
    
    invoice_id = call.data.split("_", 1)[1]
    
    cursor.execute("SELECT user_id, amount FROM payments WHERE invoice_id = ?", (invoice_id,))
    row = cursor.fetchone()
    
    if not row:
        await safe_answer(call, "❌ Платёж не найден", show_alert=True)
        return
    
    from payments import check_invoice
    result = check_invoice(invoice_id)
    
    if result.get("paid", False):
        # ТОЛЬКО ЗДЕСЬ НАЧИСЛЯЕМ КОНФЕТЫ - ПОСЛЕ РЕАЛЬНОЙ ОПЛАТЫ
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (row["amount"], row["user_id"]))
        
        # Начисляем бонус рефереру
        cursor.execute("SELECT referrer FROM users WHERE user_id = ?", (row["user_id"],))
        user = cursor.fetchone()
        if user and user["referrer"]:
            ref_bonus = int(row["amount"] * REF_PERCENT / 100)
            if ref_bonus > 0:
                cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", 
                             (ref_bonus, user["referrer"]))
                try:
                    await call.bot.send_message(
                        user["referrer"],
                        f"💰 Ваш реферал купил {row['amount']} 🍬\n"
                        f"➕ Вы получили {ref_bonus} 🍬 ({REF_PERCENT}%)"
                    )
                except:
                    pass
        
        # Удаляем запись о платеже
        cursor.execute("DELETE FROM payments WHERE invoice_id = ?", (invoice_id,))
        conn.commit()
        
        # Получаем новый баланс
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (row["user_id"],))
        new_balance = cursor.fetchone()["balance"]
        
        await safe_answer(call, f"✅ Оплата прошла! +{row['amount']} 🍬\n💰 Баланс: {new_balance} 🍬", show_alert=True)
        
        # Отправляем сообщение о успешной оплате
        await call.message.answer(
            f"✅ <b>Оплата успешно подтверждена!</b>\n\n"
            f"🍬 Начислено: +{row['amount']} конфет\n"
            f"💰 Текущий баланс: {new_balance} 🍬"
        )
    else:
        await safe_answer(call, "⏳ Платёж ещё не оплачен", show_alert=True)

# ================= ПРОМОКОДЫ =================
@router.message(PromoStates.waiting_for_promo)
async def process_promo_input(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if not await check_access(message.bot, user_id, state, message=message):
        return
    
    code = message.text.strip().upper()
    
    logger.info(f"🎟️ Promo input from user {user_id}: {code}")
    
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
    
    cursor.execute("SELECT 1 FROM used_promocodes WHERE user_id = ? AND code = ?", 
                   (user_id, promo["code"]))
    if cursor.fetchone():
        await message.answer("❌ Вы уже использовали этот промокод")
        await state.clear()
        return
    
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", 
                   (promo["reward"], user_id))
    cursor.execute("UPDATE promocodes SET activations_left = activations_left - 1 WHERE code = ?", 
                   (promo["code"],))
    cursor.execute("INSERT INTO used_promocodes (user_id, code) VALUES (?, ?)", 
                   (user_id, promo["code"]))
    conn.commit()
    
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    new_balance = cursor.fetchone()["balance"]
    
    await message.answer(
        f"✅ <b>Промокод активирован!</b>\n\n"
        f"🎁 Начислено: +{promo['reward']} 🍬\n"
        f"💰 Текущий баланс: {new_balance} 🍬"
    )
    await state.clear()

# ================= ПОДДЕРЖКА - ОТВЕТ =================
@router.message(AdminStates.waiting_for_support_reply)
async def support_reply_send(message: Message, state: FSMContext):
    if not check_admin_access(message.from_user.id)[0]:
        return
    
    logger.info(f"📬 Support reply from admin: {message.text[:50]}...")
    
    data = await state.get_data()
    user_id = data.get('reply_to_user')
    reply_text = message.text
    
    if not user_id:
        await message.answer("❌ Ошибка: не указан получатель")
        await state.clear()
        return
    
    try:
        await message.bot.send_message(
            chat_id=user_id,
            text=f"📬 <b>ОТВЕТ ОТ ПОДДЕРЖКИ</b>\n\n{reply_text}"
        )
        
        await message.answer(f"✅ Ответ отправлен пользователю {user_id}")
    except Exception as e:
        await message.answer(
            f"❌ <b>ОШИБКА ОТПРАВКИ</b>\n\n"
            f"👤 Пользователь: <code>{user_id}</code>\n"
            f"❌ Ошибка: {str(e)}\n\n"
            f"💡 Попросите пользователя написать /start"
        )
    
    await state.clear()

# ================= ПОДДЕРЖКА - НОВОЕ СООБЩЕНИЕ =================
@router.callback_query(F.data == "support")
async def support_start(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    
    if not await check_access(call.bot, user_id, state, call=call):
        return
    
    await safe_answer(call)
    
    await state.set_state(SubscribeStates.waiting_for_support_message)
    
    await call.message.answer(
        "📝 <b>ПОДДЕРЖКА</b>\n\n"
        "Напишите ваше сообщение. Администратор ответит вам в ближайшее время.\n\n"
        "💡 Вы можете продолжать пользоваться ботом, ваше сообщение будет доставлено."
    )

@router.message(SubscribeStates.waiting_for_support_message)
async def support_message_handler(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user_text = message.text
    
    if not user_text or len(user_text) < 2:
        await message.answer("❌ Сообщение слишком короткое")
        return
    
    cursor.execute("SELECT username FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    username = user["username"] if user and user["username"] else "нет username"
    
    reply_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Ответить", callback_data=f"reply_{user_id}")]
    ])
    
    try:
        await message.bot.send_message(
            MAIN_ADMIN_ID,
            f"📬 <b>НОВОЕ СООБЩЕНИЕ В ПОДДЕРЖКУ</b>\n\n"
            f"👤 Пользователь: @{username}\n"
            f"🆔 ID: <code>{user_id}</code>\n\n"
            f"💬 Сообщение:\n{user_text}",
            reply_markup=reply_keyboard
        )
        
        await message.answer(
            "✅ <b>Сообщение отправлено!</b>\n\n"
            "Администратор ответит вам в ближайшее время."
        )
        
    except Exception as e:
        logger.error(f"Failed to forward support message: {e}")
        await message.answer("❌ Ошибка при отправке сообщения. Попробуйте позже.")
    
    await state.clear()

@router.callback_query(F.data.startswith("reply_"))
async def support_reply_start(call: CallbackQuery, state: FSMContext):
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    user_id = int(call.data.split("_")[1])
    
    cursor.execute("SELECT user_id, username FROM users WHERE user_id = ?", (user_id,))
    user_exists = cursor.fetchone()
    
    if not user_exists:
        await call.message.answer(f"❌ Пользователь с ID {user_id} не найден в базе")
        return
    
    await state.update_data(reply_to_user=user_id)
    await state.set_state(AdminStates.waiting_for_support_reply)
    
    await call.message.answer(
        f"✏️ <b>ОТВЕТ ПОЛЬЗОВАТЕЛЮ</b>\n\n"
        f"ID: <code>{user_id}</code>\n"
        f"Username: @{user_exists['username'] or 'нет'}\n\n"
        f"Введите текст ответа:"
    )

# ================= АДМИН - РАССЫЛКА =================
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

# ================= АДМИН - ДОБАВЛЕНИЕ БАЛАНСА =================
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
async def process_add_balance_amount(message: Message, state: FSMContext):
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
            await message.bot.send_message(
                target_user_id,
                f"💰 Администратор начислил вам {amount} 🍬\nТекущий баланс: {new_balance} 🍬"
            )
        except:
            pass
    else:
        await message.answer("❌ Пользователь не найден")
    
    await state.clear()
    await message.answer("👑 Админ-панель", reply_markup=get_admin_menu())

# ================= АДМИН - СНЯТИЕ БАЛАНСА =================
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
async def process_remove_balance_amount(message: Message, state: FSMContext):
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
        await message.bot.send_message(
            target_user_id,
            f"⚠️ Администратор снял {amount} 🍬 с вашего баланса\nТекущий баланс: {new_balance} 🍬"
        )
    except:
        pass
    
    await state.clear()
    await message.answer("👑 Админ-панель", reply_markup=get_admin_menu())

# ================= АДМИН - СОЗДАНИЕ ПРОМОКОДА =================
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
    
    cursor.execute(
        "INSERT INTO promocodes (code, reward, activations_left) VALUES (?, ?, ?)",
        (code, reward, uses)
    )
    conn.commit()
    
    await message.answer(
        f"✅ <b>Промокод создан!</b>\n\n"
        f"🎟 Код: <code>{code}</code>\n"
        f"🎁 Награда: {reward} 🍬\n"
        f"📊 Активаций: {uses}"
    )
    await state.clear()
    await message.answer("👑 Админ-панель", reply_markup=get_admin_menu())

# ================= ОП (обязательная подписка) =================
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
        await safe_answer(call, "❌ Ошибка загрузки. Попробуйте позже.", show_alert=True)
    elif call.data == "fake_rate":
        rate = random.randint(45000, 52000)
        await safe_answer(call, f"💱 Курс BTC: ${rate}", show_alert=True)
    elif call.data == "fake_dice":
        dice = random.randint(1, 6)
        await safe_answer(call, f"🎲 Выпало: {dice}", show_alert=True)

# ================= БОНУС =================
@router.callback_query(F.data == "bonus")
async def bonus(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    
    if not await check_access(call.bot, user_id, state, call=call):
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
        await safe_answer(call, f"⏳ Подожди {minutes} мин {seconds} сек", show_alert=True)
        return
    
    cursor.execute(
        "UPDATE users SET balance = balance + ?, last_bonus = ? WHERE user_id = ?",
        (BONUS_AMOUNT, now, user_id)
    )
    conn.commit()
    
    await safe_answer(call, f"🎁 +{BONUS_AMOUNT} 🍬", show_alert=True)

# ================= ВИДЕО (ПРОСМОТР) =================
@router.callback_query(F.data == "videos")
async def videos(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    
    logger.info(f"🎥 Videos request from user {user_id}")
    
    if not await check_access(call.bot, user_id, state, call=call):
        return
    
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    if not result:
        await safe_answer(call, "❌ Пользователь не найден", show_alert=True)
        return
    
    balance = result["balance"]
    
    if balance < VIDEO_PRICE and not check_admin_access(user_id)[0]:
        await safe_answer(call, f"❌ Недостаточно конфет. Нужно: {VIDEO_PRICE} 🍬", show_alert=True)
        return
    
    cursor.execute("SELECT COUNT(*) as count FROM videos")
    count = cursor.fetchone()["count"]
    
    if count == 0:
        await safe_answer(call, "❌ Видео еще не загружены", show_alert=True)
        return
    
    cursor.execute("""
        SELECT id, file_id FROM videos
        WHERE id NOT IN (
            SELECT video_id FROM user_videos WHERE user_id = ?
        )
        ORDER BY id ASC
        LIMIT 1
    """, (user_id,))
    video = cursor.fetchone()
    
    if not video:
        await safe_answer(call, "❌ Ты посмотрел все видео!", show_alert=True)
        return
    
    try:
        logger.info(f"📤 Sending video {video['id']} to user {user_id}")
        await call.message.answer_video(
            video["file_id"],
            caption=f"🎥 <b>Видео</b>",
            reply_markup=video_menu
        )
        
        if not check_admin_access(user_id)[0]:
            cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (VIDEO_PRICE, user_id))
            await safe_answer(call, f"🍬 Списана {VIDEO_PRICE} конфета", show_alert=True)
        
        cursor.execute("INSERT OR IGNORE INTO user_videos (user_id, video_id) VALUES (?, ?)", (user_id, video["id"]))
        conn.commit()
        logger.info(f"✅ Video {video['id']} sent successfully to user {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Error sending video: {e}")
        await safe_answer(call, "❌ Ошибка отправки видео", show_alert=True)

# ================= ПРОМОКОДЫ =================
@router.callback_query(F.data == "promo")
async def promo(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    
    if not await check_access(call.bot, user_id, state, call=call):
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
async def profile(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    
    if not await check_access(call.bot, user_id, state, call=call):
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
    
    text = (
        f"👤 <b>ПРОФИЛЬ</b>\n\n"
        f"🍬 Баланс: <code>{balance}</code> конфет\n"
        f"👥 Рефералов: <code>{ref_count}</code>\n\n"
        f"🔗 <b>Твоя ссылка:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        f"🎁 За друга: +{REF_BONUS} 🍬\n"
        f"💰 С покупок рефералов: {REF_PERCENT}%"
    )
    
    try:
        await call.message.answer(text)
    except:
        pass

# ================= МАГАЗИН =================
@router.callback_query(F.data == "shop")
async def shop(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    
    if not await check_access(call.bot, user_id, state, call=call):
        return
    
    await call.message.answer(
        "🍬 <b>Магазин конфет</b>\n\n"
        "💰 Выберите количество конфет для покупки:\n\n"
        "⭐️ Для оплаты звездами нажми на кнопку ниже",
        reply_markup=shop_menu
    )

# ================= АДМИН КОМАНДЫ =================
@router.callback_query(F.data == "admin_stats")
async def admin_stats(call: CallbackQuery):
    user_id = call.from_user.id
    
    has_access, _, _, _ = check_admin_access(user_id)
    
    if not has_access:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    await safe_answer(call)
    
    # РЕАЛЬНАЯ СТАТИСТИКА ИЗ БД
    cursor.execute("SELECT COUNT(*) as count FROM users")
    total_users = cursor.fetchone()["count"]
    
    cursor.execute("SELECT COUNT(*) as count FROM users WHERE is_verified = 1")
    verified_users = cursor.fetchone()["count"]
    
    cursor.execute("SELECT COUNT(*) as count FROM users WHERE is_verified = 0")
    unverified_users = cursor.fetchone()["count"]
    
    cursor.execute("SELECT COUNT(*) as count FROM users WHERE referrer IS NOT NULL")
    ref_users = cursor.fetchone()["count"]
    
    cursor.execute("SELECT COUNT(*) as count FROM users WHERE referrer IS NULL")
    non_ref_users = cursor.fetchone()["count"]
    
    cursor.execute("SELECT SUM(balance) as total FROM users")
    total_balance = cursor.fetchone()["total"] or 0
    
    cursor.execute("SELECT AVG(balance) as avg FROM users")
    avg_balance = cursor.fetchone()["avg"] or 0
    
    cursor.execute("SELECT MAX(balance) as max FROM users")
    max_balance = cursor.fetchone()["max"] or 0
    
    cursor.execute("SELECT COUNT(*) as count FROM users WHERE balance > 0")
    users_with_balance = cursor.fetchone()["count"]
    
    cursor.execute("SELECT COUNT(*) as count FROM users WHERE balance = 0")
    users_zero_balance = cursor.fetchone()["count"]
    
    cursor.execute("SELECT COUNT(*) as count FROM videos")
    total_videos = cursor.fetchone()["count"]
    
    cursor.execute("SELECT COUNT(DISTINCT user_id) as count FROM user_videos")
    users_watched = cursor.fetchone()["count"]
    
    cursor.execute("SELECT COUNT(*) as count FROM user_videos")
    total_views = cursor.fetchone()["count"]
    
    cursor.execute("SELECT COUNT(*) as count FROM payments")
    total_payments = cursor.fetchone()["count"]
    
    cursor.execute("SELECT SUM(amount) as total FROM payments")
    total_paid_candies = cursor.fetchone()["total"] or 0
    
    cursor.execute("SELECT COUNT(*) as count FROM promocodes")
    total_promos = cursor.fetchone()["count"]
    
    cursor.execute("SELECT SUM(activations_left) as total FROM promocodes")
    total_activations_left = cursor.fetchone()["total"] or 0
    
    cursor.execute("SELECT COUNT(*) as count FROM used_promocodes")
    used_promos = cursor.fetchone()["count"]
    
    cursor.execute("SELECT COUNT(*) as count FROM users WHERE last_bonus > 0")
    users_took_bonus = cursor.fetchone()["count"]
    
    cursor.execute("SELECT COUNT(DISTINCT user_id) as count FROM user_videos")
    active_users = cursor.fetchone()["count"]
    
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
        f"├ ❌ Не верифицировано: {unverified_users}\n"
        f"├ 🔗 По рефералкам: {ref_users}\n"
        f"├ 🚫 Без рефералки: {non_ref_users}\n"
        f"├ 💰 С балансом: {users_with_balance}\n"
        f"├ 🍪 С нулевым балансом: {users_zero_balance}\n"
        f"├ 👑 Админов: {admins_count}\n"
        f"└ 🎁 Получили бонус за подписку: {bonus_received}\n\n"
        
        f"💰 <b>БАЛАНСЫ:</b>\n"
        f"├ 💎 Всего конфет: {total_balance} 🍬\n"
        f"├ 📊 Средний баланс: {avg_balance:.1f} 🍬\n"
        f"└ 🏆 Макс. баланс: {max_balance} 🍬\n\n"
        
        f"🎥 <b>ВИДЕО:</b>\n"
        f"├ 📹 Всего видео: {total_videos}\n"
        f"├ 👀 Всего просмотров: {total_views}\n"
        f"└ 🎬 Смотрели видео: {users_watched} чел\n\n"
        
        f"💳 <b>ПЛАТЕЖИ:</b>\n"
        f"├ 💸 Всего платежей: {total_payments}\n"
        f"└ 🍬 Куплено конфет: {total_paid_candies} 🍬\n\n"
        
        f"🎟 <b>ПРОМОКОДЫ:</b>\n"
        f"├ 📋 Всего создано: {total_promos}\n"
        f"├ ✅ Активировано: {used_promos}\n"
        f"└ 📦 Осталось активаций: {total_activations_left}\n\n"
        
        f"📈 <b>АКТИВНОСТЬ:</b>\n"
        f"├ 🎁 Брали бонус: {users_took_bonus} чел\n"
        f"└ 👁 Активные юзеры: {active_users} чел\n\n"
        
        f"🔐 <b>ОБЯЗАТЕЛЬНАЯ ПОДПИСКА:</b>\n"
        f"└ 📢 Каналов в ОП: {len(channels)}"
    )
    
    await call.message.answer(text)
    await call.message.answer("👑 Админ-панель", reply_markup=get_admin_menu())

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

@router.callback_query(F.data == "confirm_broadcast")
async def confirm_broadcast(call: CallbackQuery, state: FSMContext):
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
            await call.bot.send_message(uid, text)
            sent += 1
            if i % 10 == 0:
                await status_msg.edit_text(f"📢 Рассылка...\nОтправлено: {sent}/{len(users)}")
            await asyncio.sleep(0.05)
        except Exception as e:
            failed += 1
            logger.error(f"Failed to send to {uid}: {e}")
    
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

# ================= УПРАВЛЕНИЕ АДМИНАМИ =================
@router.callback_query(F.data == "admin_manage")
async def admin_manage_menu_callback(call: CallbackQuery):
    user_id = call.from_user.id
    
    has_access, _, is_main, can_manage = check_admin_access(user_id, require_manage=True)
    
    if not has_access:
        await safe_answer(call, "❌ Нет прав для управления админами", show_alert=True)
        return
    
    await safe_answer(call)
    await call.message.edit_text(
        "👥 <b>Управление админами</b>",
        reply_markup=admin_manage_menu
    )

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
    await call.message.answer(
        "➕ <b>Добавление нового админа</b>\n\n"
        "Введите ID пользователя Telegram:"
    )

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
    
    await message.answer(
        "🔐 <b>Права админа</b>\n\n"
        "Разрешить этому админу добавлять других админов?",
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
        button_text = f"❌ {username} (ID: {admin['user_id']})"
        keyboard.append([InlineKeyboardButton(
            text=button_text,
            callback_data=f"admin_del_{admin['user_id']}"
        )])
    
    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_manage")])
    
    await call.message.answer(
        "🗑 <b>Выберите админа для удаления:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

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

# ================= УПРАВЛЕНИЕ ОП =================
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
    await call.message.answer(
        "📢 <b>Добавление канала в ОП</b>\n\n"
        "Введите ID канала (например: -1001234567890) или @username канала:"
    )

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
        keyboard.append([InlineKeyboardButton(
            text=f"❌ {ch['channel_name']}", 
            callback_data=f"op_del_{ch['channel_id']}"
        )])
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_op")])
    
    await call.message.answer(
        "🗑 <b>Выберите канал для удаления:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

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
        keyboard.append([InlineKeyboardButton(
            text=f"❌ {ch['channel_name']}", 
            callback_data=f"op_del_{ch['channel_id']}"
        )])
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_op")])
    
    await call.message.edit_text(
        "🗑 <b>Выберите канал для удаления:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

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

# ================= ТЕСТОВЫЕ КОМАНДЫ =================
@router.message(Command("test_captcha"))
async def test_captcha_command(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if not check_admin_access(user_id)[0]:
        await message.answer("❌ Только для админов")
        return
    
    # Генерируем капчу
    image_bytes, captcha_code = generate_captcha_image()
    
    # Отправляем только изображение, без ввода
    await message.answer_photo(
        photo=BufferedInputFile(file=image_bytes, filename="captcha.png"),
        caption=f"🔐 <b>ТЕСТ КАПЧИ</b>\n\n"
                f"Код: <code>{captcha_code}</code>\n"
                f"Размер: 800x300\n"
                f"Буквы: 80px"
    )

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