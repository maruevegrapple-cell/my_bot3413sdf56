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
    update_last_bonus, add_video, mark_video_watched, get_user_watched_videos
)
from keyboards import (
    fake_menu, main_menu, video_menu, shop_menu, get_admin_menu, 
    confirm_menu, subscribe_menu, op_menu, admin_manage_menu
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

# ================= ГЕНЕРАЦИЯ КАПЧИ =================
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
            "C:\\Windows\\Fonts\\arialbd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "arial.ttf"
        ]
        
        for path in font_paths:
            if os.path.exists(path):
                font = ImageFont.truetype(path, 80)
                print(f"✅ Загружен шрифт: {path}")
                break
    except:
        font = None
    
    if font is None:
        font = ImageFont.load_default()
        print("⚠️ Используется встроенный шрифт")
    
    # Рисуем буквы
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
    
    # Добавляем немного шума
    for _ in range(100):
        x = random.randint(0, width)
        y = random.randint(0, height)
        draw.point((x, y), fill=(100, 100, 100))
    
    bio = io.BytesIO()
    image.save(bio, 'PNG', quality=95)
    bio.seek(0)
    
    print(f"✅ Капча сгенерирована: {code}")
    return bio.getvalue(), code

# ================= БЛОКИРОВКА ПЕРЕСЫЛКИ =================
@router.message(F.forward_from | F.forward_from_chat)
async def block_forward(message: Message):
    await message.delete()

# ================= ЗАГРУЗКА ВИДЕО АДМИНАМИ =================
@router.message(F.video)
async def handle_video(message: Message, bot: Bot):
    """Обработка видео - разделяем админов и обычных пользователей"""
    user_id = message.from_user.id
    
    # Проверяем, админ ли это
    has_access, _, _, _ = check_admin_access(user_id)
    
    if has_access:
        # Это админ - загружаем видео напрямую в базу
        await upload_video(message)
    else:
        # Это обычный пользователь - проверяем, в режиме ли предложки
        await handle_suggestion_video(message, bot)

async def upload_video(message: Message):
    """Загрузка видео админом"""
    user_id = message.from_user.id
    
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

# ================= ПРЕДЛОЖКА =================
@router.callback_query(F.data == "suggestion")
async def suggestion_start(call: CallbackQuery, state: FSMContext):
    """Начало предложки - включаем режим приема видео"""
    user_id = call.from_user.id
    
    if not await check_access(call.bot, user_id, state, call=call):
        return
    
    await safe_answer(call)
    
    # Добавляем пользователя в режим предложки
    suggestion_mode.add(user_id)
    
    await call.message.answer(
        "🎬 <b>ПРЕДЛОЖКА</b>\n\n"
        "📹 Отправьте видео, которое хотите предложить для добавления в бота.\n\n"
        "✅ Если видео одобрят, вы получите +3 🍬\n"
        "❌ Если отклонят, вы получите уведомление\n\n"
        "⏳ Режим предложки активен 5 минут или до отправки видео"
    )
    
    # Запускаем таймер для автоматического выхода из режима
    async def exit_suggestion_mode():
        await asyncio.sleep(300)  # 5 минут
        if user_id in suggestion_mode:
            suggestion_mode.discard(user_id)
            try:
                await call.message.answer("⏰ Время вышло. Режим предложки отключен.")
            except:
                pass
    
    asyncio.create_task(exit_suggestion_mode())

async def handle_suggestion_video(message: Message, bot: Bot):
    """Обработка видео от обычного пользователя в режиме предложки"""
    user_id = message.from_user.id
    
    # Проверяем, в режиме ли предложки пользователь
    if user_id not in suggestion_mode:
        # Если не в режиме предложки, игнорируем
        return
    
    # Убираем пользователя из режима предложки
    suggestion_mode.discard(user_id)
    
    username = message.from_user.username or "нет username"
    file_id = message.video.file_id
    file_name = message.video.file_name or "без названия"
    duration = message.video.duration
    file_size = message.video.file_size
    
    logger.info(f"📹 ПРЕДЛОЖКА: Видео от пользователя {user_id} (@{username})")
    
    # Проверяем размер видео (Telegram ограничение 50MB)
    if file_size > 50 * 1024 * 1024:  # 50MB в байтах
        await message.answer("❌ Видео слишком большое. Максимальный размер: 50MB")
        return
    
    # Генерируем короткий уникальный ID для видео (последние 8 символов от file_id)
    short_id = file_id[-8:]
    
    # Сохраняем видео во временное хранилище с коротким ключом
    suggested_videos[short_id] = {
        "user_id": user_id,
        "username": username,
        "file_name": file_name,
        "duration": duration,
        "message_id": message.message_id,
        "file_id": file_id  # сохраняем оригинальный file_id
    }
    
    # Получаем информацию о пользователе из БД
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    balance = user["balance"] if user else 0
    
    # Получаем список всех админов
    admins = get_all_admins()
    
    # Создаем клавиатуру для админов с КОРОТКИМИ callback_data
    admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Одобрить", callback_data=f"app_{short_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"rej_{short_id}")
        ]
    ])
    
    # Отправляем видео ВСЕМ админам
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
        except Exception as e:
            logger.error(f"Не удалось отправить видео админу {admin_id}: {e}")
    
    if sent_count > 0:
        await message.answer(
            "✅ <b>Видео отправлено на модерацию!</b>\n\n"
            "Администраторы проверят его и сообщат о решении."
        )
    else:
        await message.answer("❌ Ошибка при отправке видео. Попробуйте позже.")
        # Удаляем из хранилища в случае ошибки
        if short_id in suggested_videos:
            del suggested_videos[short_id]

@router.callback_query(F.data.startswith("app_"))
async def suggest_approve(call: CallbackQuery, state: FSMContext, bot: Bot):
    """Админ одобрил видео"""
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    short_id = call.data.replace("app_", "")
    video_data = suggested_videos.get(short_id)
    
    if not video_data:
        await safe_answer(call, "❌ Видео не найдено в хранилище", show_alert=True)
        await call.message.delete()
        return
    
    file_id = video_data["file_id"]  # берем оригинальный file_id из хранилища
    user_id = video_data["user_id"]
    
    # Добавляем видео в базу
    try:
        cursor.execute("INSERT INTO videos (file_id) VALUES (?)", (file_id,))
        
        # Начисляем награду пользователю
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", 
                      (SUGGESTION_REWARD, user_id))
        
        # Получаем новый баланс для сообщения
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        new_balance = cursor.fetchone()["balance"]
        
        conn.commit()
        
        logger.info(f"✅ Видео одобрено: {file_id}, пользователь {user_id} получил +{SUGGESTION_REWARD} 🍬")
        
        # Отправляем уведомление пользователю
        try:
            await bot.send_message(
                user_id,
                f"✅ <b>Видео одобрено!</b>\n\n"
                f"Ваше предложенное видео было одобрено администратором.\n"
                f"🎁 Начислено +{SUGGESTION_REWARD} 🍬\n"
                f"💰 Текущий баланс: {new_balance} 🍬"
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление пользователю {user_id}: {e}")
        
        await safe_answer(call, f"✅ Видео одобрено! Пользователю начислено +{SUGGESTION_REWARD} 🍬")
        
        # Удаляем сообщение у админа
        await call.message.delete()
        
    except Exception as e:
        logger.error(f"Ошибка при одобрении видео: {e}")
        await safe_answer(call, "❌ Ошибка при одобрении видео", show_alert=True)
    
    # Удаляем из временного хранилища
    if short_id in suggested_videos:
        del suggested_videos[short_id]

@router.callback_query(F.data.startswith("rej_"))
async def suggest_reject(call: CallbackQuery, state: FSMContext, bot: Bot):
    """Админ отклонил видео"""
    if not check_admin_access(call.from_user.id)[0]:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    short_id = call.data.replace("rej_", "")
    video_data = suggested_videos.get(short_id)
    
    if not video_data:
        await safe_answer(call, "❌ Видео не найдено в хранилище", show_alert=True)
        await call.message.delete()
        return
    
    user_id = video_data["user_id"]
    
    # Отправляем уведомление пользователю
    try:
        await bot.send_message(
            user_id,
            f"❌ <b>Видео отклонено</b>\n\n"
            f"Ваше предложенное видео не прошло модерацию.\n"
            f"Попробуйте предложить другое видео."
        )
        
        await safe_answer(call, "❌ Видео отклонено, пользователь уведомлен")
        
        # Удаляем сообщение у админа
        await call.message.delete()
        
    except Exception as e:
        logger.error(f"Ошибка при отклонении видео: {e}")
        await safe_answer(call, "❌ Ошибка при отклонении видео", show_alert=True)
    
    # Удаляем из временного хранилища
    if short_id in suggested_videos:
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
        conn.commit()
        
        cursor.execute("SELECT COUNT(*) as count FROM videos")
        total = cursor.fetchone()["count"]
        
        await message.answer(
            f"✅ <b>ВИДЕО УСПЕШНО ДОБАВЛЕНО!</b>\n\n"
            f"📹 <b>File ID:</b> <code>{file_id}</code>\n"
            f"📊 <b>Размер:</b> {file_size // (1024 * 1024)} MB\n"
            f"🎥 <b>Всего видео в базе:</b> {total}\n\n"
            f"💡 Теперь можно смотреть!"
        )
        
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
async def start(message: Message, state: FSMContext, bot: Bot):
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
    
    # ========== ЕСЛИ В ССЫЛКЕ ЕСТЬ РЕФ КОД ==========
    if has_ref_in_link:
        logger.info(f"✅ Пользователь {user_id} перешел по реферальной ссылке")
        
        if user:
            logger.info(f"🔄 Пользователь {user_id} уже существует. Бонус рефереру НЕ начислен.")
        else:
            logger.info(f"🆕 Создаем НОВОГО пользователя {user_id} с реферером {referrer_id}")
            new_ref_code = generate_ref_code()
            cursor.execute("""
                INSERT INTO users (user_id, username, referrer, is_verified, ref_code, subscribe_bonus_received, is_admin)
                VALUES (?, ?, ?, 0, ?, 0, 0)
            """, (user_id, username, referrer_id, new_ref_code))
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
        
        if is_verified(user_id):
            logger.info(f"✅ Пользователь {user_id} верифицирован, проверяем подписку")
            is_subscribed = await check_subscription(bot, user_id)
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
    
    if is_verified(user_id):
        is_subscribed = await check_subscription(bot, user_id)
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
async def process_captcha(message: Message, state: FSMContext, bot: Bot):
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
        is_subscribed = await check_subscription(bot, user_id)
        
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

# ================= МАГАЗИН =================
@router.callback_query(F.data == "shop")
async def shop(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    
    if not await check_access(bot, user_id, state, call=call):
        return
    
    text = (
        "🍬 <b>Магазин конфет</b>\n\n"
        "💰 Выберите количество конфет для покупки:\n\n"
        "⭐️ Для оплаты звездами нажми на кнопку ниже\n"
        "⭐️ 1 телеграмм звезда = 3 конфеты 🍬\n"
        "⭐️ 15 телеграмм звезд (минималка) = 45 конфет 🍬"
    )
    
    await call.message.answer(
        text,
        reply_markup=shop_menu
    )

# ================= КАСТОМНАЯ ОПЛАТА =================
@router.message(CustomPayStates.waiting_for_amount)
async def process_custom_pay(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    
    if not await check_access(bot, user_id, state, message=message):
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
        
        # СКИДКА 25% - цена 0.003 USD за конфету
        usdt = round(amount * 0.003, 2)
        
        if usdt < 0.1:
            usdt = 0.1
        
        # Показываем выгоду
        standard_price = round(amount * 0.004, 2)
        savings = round(standard_price - usdt, 2)
        
        await state.update_data(pay_amount=amount, pay_usdt=usdt, pay_custom=True)
        
        # Показываем меню выбора валюты
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
            f"🍬 Конфет: {amount}\n"
            f"💵 Цена: {usdt} USD\n"
            f"💰 Экономия: {savings} USD\n\n"
            f"⭐️ Это выгоднее стандартных пакетов!\n\n"
            f"Выберите валюту для оплаты:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        
    except ValueError:
        await message.answer("❌ Введите корректное число")
        return

# ================= ВЫБОР ВАЛЮТЫ =================
@router.callback_query(F.data.startswith("pay_asset_"))
async def pay_with_asset(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    
    logger.info(f"💰 pay_with_asset ВЫЗВАНА с data: {call.data}")
    
    await safe_answer(call)
    
    if not await check_access(bot, user_id, state, call=call):
        return
    
    asset = call.data.replace("pay_asset_", "")
    logger.info(f"✅ Выбрана валюта: {asset}")
    
    data = await state.get_data()
    amount = data.get('pay_amount')
    usdt = data.get('pay_usdt')
    
    if not amount or not usdt:
        await call.message.answer("❌ Ошибка: данные платежа не найдены")
        return
    
    logger.info(f"💰 Сумма: {amount} конфет = ${usdt}")
    
    # СОЗДАЕМ СЧЕТ - ВСЯ КОНВЕРТАЦИЯ ВНУТРИ create_invoice
    try:
        invoice = create_invoice(usdt, asset)
        logger.info(f"🧾 Счет создан: {invoice}")
    except Exception as e:
        logger.error(f"❌ Ошибка создания счета: {e}")
        await call.message.answer("❌ Ошибка при создании платежа")
        return
    
    # Получаем конвертированную сумму из ответа
    crypto_amount = invoice.get("crypto_amount", usdt)
    rate = invoice.get("rate", "")
    
    # Сохраняем в БД
    cursor.execute(
        "INSERT INTO payments (invoice_id, user_id, amount, paid) VALUES (?, ?, ?, 0)",
        (invoice["invoice_id"], user_id, amount)
    )
    conn.commit()
    
    icon = get_asset_icon(asset)
    
    # Формируем текст с курсом если есть
    rate_text = f"\n💰 К оплате: {crypto_amount} {asset}"
    if rate:
        rate_text = f"\n1 {asset} = ${rate}\n💰 К оплате: {crypto_amount} {asset}"
    
    # Отправляем сообщение
    await call.message.answer(
        f"💳 <b>Оплата в {icon} {asset}</b>\n\n"
        f"🍬 Конфет: {amount}\n"
        f"💵 Сумма: ${usdt}{rate_text}\n\n"
        f"🔄 Курс обновлен в реальном времени",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"💰 Оплатить {crypto_amount} {asset}", url=invoice["pay_url"])],
            [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_{invoice['invoice_id']}")]
        ])
    )
    
    await state.clear()

# ================= ОПЛАТА (ПАКЕТЫ) =================
@router.callback_query(F.data.startswith("pay_"))
async def pay(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    
    # ВАЖНО: пропускаем pay_asset_
    if call.data.startswith("pay_asset_"):
        return
    
    logger.info(f"💰 pay called with data: {call.data}")
    
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
        await call.message.answer("💰 Введите желаемое количество конфет (число):")
        return
    
    if call.data not in prices:
        logger.warning(f"❌ Unknown pay data: {call.data}")
        return
    
    amount, usdt = prices[call.data]
    logger.info(f"✅ Selected: {amount} candies for ${usdt}")
    
    await state.update_data(pay_amount=amount, pay_usdt=usdt, pay_custom=False)
    
    # Показываем меню выбора валюты
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
        f"💳 <b>Выберите валюту для оплаты</b>\n\n"
        f"🍬 Конфет: {amount}\n"
        f"💵 Сумма: ${usdt}\n\n"
        f"Курс будет сконвертирован автоматически:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

# ================= ПРОВЕРКА ПОДПИСКИ =================
@router.callback_query(F.data == "check_subscribe")
async def check_subscribe_callback(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    
    await safe_answer(call)
    
    is_subscribed = await check_subscription(bot, user_id)
    
    if is_subscribed:
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
        
        await call.message.answer(f"✅ <b>Доступ получен!</b>{bonus_text}")
        await call.message.answer("🎥 Видео платформа", reply_markup=main_menu)
    else:
        try:
            await call.message.answer("❌ Вы еще не подписались на канал!")
        except:
            pass

# ================= ПРОВЕРКА ПЛАТЕЖА =================
@router.callback_query(F.data.startswith("check_"))
async def check_payment(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    
    if call.data == "check_subscribe":
        return
    
    await safe_answer(call)
    
    if not await check_access(bot, user_id, state, call=call):
        return
    
    invoice_id = call.data.split("_", 1)[1]
    logger.info(f"🔍 Проверка платежа: {invoice_id}")
    
    cursor.execute("SELECT user_id, amount, paid FROM payments WHERE invoice_id = ?", (invoice_id,))
    row = cursor.fetchone()
    
    if not row:
        await call.message.answer("❌ Платёж не найден")
        return
    
    result = check_invoice(invoice_id)
    logger.info(f"📊 Результат проверки: {result}")
    
    if result.get("paid", False):
        if row["paid"] == 1:
            await call.message.answer("✅ Этот платёж уже был обработан")
            return
        
        cursor.execute("UPDATE payments SET paid = 1 WHERE invoice_id = ?", (invoice_id,))
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (row["amount"], row["user_id"]))
        
        cursor.execute("SELECT referrer FROM users WHERE user_id = ?", (row["user_id"],))
        user = cursor.fetchone()
        if user and user["referrer"]:
            ref_bonus = int(row["amount"] * REF_PERCENT / 100)
            if ref_bonus > 0:
                cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", 
                             (ref_bonus, user["referrer"]))
                try:
                    await bot.send_message(
                        user["referrer"],
                        f"💰 Ваш реферал купил {row['amount']} 🍬\n"
                        f"➕ Вы получили {ref_bonus} 🍬 ({REF_PERCENT}%)"
                    )
                except:
                    pass
        
        conn.commit()
        
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (row["user_id"],))
        new_balance = cursor.fetchone()["balance"]
        
        await call.message.answer(
            f"✅ <b>Оплата успешно подтверждена!</b>\n\n"
            f"🍬 Начислено: +{row['amount']} конфет\n"
            f"💰 Текущий баланс: {new_balance} 🍬"
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

# ================= ПОДДЕРЖКА - НОВОЕ СООБЩЕНИЕ =================
@router.callback_query(F.data == "support")
async def support_start(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    
    if not await check_access(bot, user_id, state, call=call):
        return
    
    await safe_answer(call)
    
    await state.set_state(SubscribeStates.waiting_for_support_message)
    
    await call.message.answer(
        "📝 <b>ПОДДЕРЖКА</b>\n\n"
        "Напишите ваше сообщение или отправьте скриншот.\n"
        "Администратор ответит вам в ближайшее время.\n\n"
        "💡 Вы можете прикрепить фото к сообщению"
    )

# ================= ПОДДЕРЖКА - ОБРАБОТКА ТЕКСТА =================
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
    
    reply_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Ответить", callback_data=f"reply_{user_id}")]
    ])
    
    try:
        await bot.send_message(
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

# ================= ПОДДЕРЖКА - ОБРАБОТКА ФОТО =================
@router.message(SubscribeStates.waiting_for_support_message, F.photo)
async def support_photo_handler(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    user_text = message.caption or "Без описания"
    
    # Получаем фото самого высокого качества
    photo = message.photo[-1]
    file_id = photo.file_id
    
    cursor.execute("SELECT username FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    username = user["username"] if user and user["username"] else "нет username"
    
    # Создаем клавиатуру для ответа
    reply_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Ответить", callback_data=f"reply_{user_id}")]
    ])
    
    try:
        # Отправляем фото админу
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
        
        await message.answer(
            "✅ <b>Скриншот отправлен!</b>\n\n"
            "Администратор ответит вам в ближайшее время."
        )
        
    except Exception as e:
        logger.error(f"Failed to forward support photo: {e}")
        await message.answer("❌ Ошибка при отправке скриншота. Попробуйте позже.")
    
    await state.clear()

# ================= ПОДДЕРЖКА - ОТВЕТ АДМИНА =================
@router.message(AdminStates.waiting_for_support_reply)
async def support_reply_send(message: Message, state: FSMContext, bot: Bot):
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
        await bot.send_message(
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

@router.callback_query(F.data.startswith("reply_"))
async def support_reply_start(call: CallbackQuery, state: FSMContext, bot: Bot):
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
            await bot.send_message(
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
        await bot.send_message(
            target_user_id,
            f"⚠️ Администратор снял {amount} 🍬 с вашего баланса\nТекущий баланс: {new_balance} 🍬"
        )
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

# ================= АДМИН - УПРАВЛЕНИЕ ОП =================
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

# ================= АДМИН - СТАТИСТИКА =================
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
        [InlineKeyboardButton(text="🔍 Поиск платежей", callback_data="admin_search_payments")],
        [InlineKeyboardButton(text="👤 Поиск пользователей", callback_data="admin_search_users")]
    ])
    
    await call.message.answer(text)
    await call.message.answer("📊 <b>Дополнительная статистика</b>", reply_markup=keyboard)

# ================= АДМИН - ТОП РЕФЕРОВ =================
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

# ================= АДМИН - ПОИСК ПЛАТЕЖЕЙ =================
@router.callback_query(F.data == "admin_search_payments")
async def admin_search_payments_start(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    
    has_access, _, _, _ = check_admin_access(user_id)
    
    if not has_access:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    await safe_answer(call)
    await state.set_state(AdminStates.waiting_for_payment_search)
    await call.message.answer(
        "🔍 <b>Поиск платежей</b>\n\n"
        "Введите ID пользователя или username для поиска:\n"
        "Например: <code>123456789</code> или <code>@username</code>"
    )

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

# ================= АДМИН - ПОИСК ПОЛЬЗОВАТЕЛЕЙ =================
@router.callback_query(F.data == "admin_search_users")
async def admin_search_users_start(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    
    has_access, _, _, _ = check_admin_access(user_id)
    
    if not has_access:
        await safe_answer(call, "❌ Нет доступа", show_alert=True)
        return
    
    await safe_answer(call)
    await state.set_state(AdminStates.waiting_for_user_search)
    await call.message.answer(
        "👤 <b>Поиск пользователей</b>\n\n"
        "Введите ID пользователя, username или часть username для поиска:"
    )

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
        await safe_answer(call, "❌ Ошибка загрузки. Попробуйте позже.", show_alert=True)
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
async def videos(call: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = call.from_user.id
    
    logger.info(f"🎥 Videos request from user {user_id}")
    
    if not await check_access(bot, user_id, state, call=call):
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