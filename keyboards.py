from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import CHANNEL_LINK, ANON_CHAT_LINK

# ================= ФЕЙК МЕНЮ =================
fake_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📥 Скачать видео с YouTube", callback_data="fake_download")],
    [InlineKeyboardButton(text="💱 Курс BTC", callback_data="fake_rate")],
    [InlineKeyboardButton(text="🎲 Играть в кости", callback_data="fake_dice")],
])

# ================= МЕНЮ ПОДПИСКИ =================
subscribe_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📢 Подписаться на канал", url=CHANNEL_LINK)],
    [InlineKeyboardButton(text="✅ Я подписался", callback_data="check_subscribe")]
])

# ================= ОСНОВНОЕ МЕНЮ =================
main_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="▶️ Смотреть видео", callback_data="videos")],
    [
        InlineKeyboardButton(text="🍬 Купить конфеты", callback_data="shop"),
        InlineKeyboardButton(text="👤 Профиль", callback_data="profile")
    ],
    [
        InlineKeyboardButton(text="🎁 Бонус", callback_data="bonus"),
        InlineKeyboardButton(text="🎟 Промокод", callback_data="promo")
    ],
    [
        InlineKeyboardButton(text="📋 Задания", callback_data="tasks"),
        InlineKeyboardButton(text="🎬 Предложка", callback_data="suggestion")
    ],
    [
        InlineKeyboardButton(text="🆘 Поддержка", callback_data="support"),
        InlineKeyboardButton(text="📢 Наш канал", url=CHANNEL_LINK)
    ]
])

# ================= МЕНЮ ЗАДАНИЙ =================
def get_tasks_menu(user_tasks):
    keyboard = []
    for task in user_tasks:
        if task.get("status") == "approved":
            emoji = "✅"
        elif task.get("status") == "pending":
            emoji = "⏳"
        else:
            emoji = "❌"
        
        keyboard.append([InlineKeyboardButton(
            text=f"{emoji} {task['title']} | +{task['reward']} 🍬",
            callback_data=f"task_{task['id']}"
        )])
    
    keyboard.append([InlineKeyboardButton(text="🔄 Обновить список", callback_data="tasks_refresh")])
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_task_action_menu(task_id: int, task_title: str, task_reward: int, task_status: str = None):
    keyboard = []
    if task_status != "approved" and task_status != "pending":
        keyboard.append([InlineKeyboardButton(text="✅ Выполнить задание", callback_data=f"do_task_{task_id}")])
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад к заданиям", callback_data="tasks")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# ================= АДМИН-МЕНЮ =================
def get_admin_menu(is_main_admin: bool = False, can_manage_admins: bool = False):
    buttons = [
        [
            InlineKeyboardButton(text="▶️ Смотреть видео", callback_data="videos"),
            InlineKeyboardButton(text="👤 Профиль", callback_data="profile")
        ],
        [
            InlineKeyboardButton(text="🎟 Создать промо", callback_data="admin_add_promo"),
            InlineKeyboardButton(text="🎁 Бонус", callback_data="bonus")
        ],
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")
        ],
        [
            InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast"),
            InlineKeyboardButton(text="🍬 Магазин", callback_data="shop")
        ],
        [
            InlineKeyboardButton(text="➕ Добавить баланс", callback_data="admin_add_balance"),
            InlineKeyboardButton(text="➖ Снять баланс", callback_data="admin_remove_balance")
        ],
        [
            InlineKeyboardButton(text="🔐 Управление ОП", callback_data="admin_op"),
            InlineKeyboardButton(text="📹 Загрузить видео", callback_data="admin_upload_url")
        ],
        [
            InlineKeyboardButton(text="📋 Управление заданиями", callback_data="admin_tasks")
        ]
    ]
    
    if is_main_admin or can_manage_admins:
        buttons.append([InlineKeyboardButton(text="👥 Управление админами", callback_data="admin_manage")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ================= АДМИН-МЕНЮ ЗАДАНИЙ =================
admin_tasks_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="➕ Создать задание", callback_data="admin_task_add")],
    [InlineKeyboardButton(text="🗑 Удалить задание", callback_data="admin_task_remove")],
    [InlineKeyboardButton(text="📋 Список заданий", callback_data="admin_task_list")],
    [InlineKeyboardButton(text="⏳ На проверке", callback_data="admin_task_pending")],
    [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_panel")]
])

# ================= МЕНЮ УПРАВЛЕНИЯ АДМИНАМИ =================
admin_manage_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="➕ Добавить админа", callback_data="admin_add")],
    [InlineKeyboardButton(text="🗑 Удалить админа", callback_data="admin_remove")],
    [InlineKeyboardButton(text="📋 Список админов", callback_data="admin_list")],
    [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")]
])

# ================= МЕНЮ УПРАВЛЕНИЯ ОП =================
op_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="➕ Добавить канал", callback_data="op_add")],
    [InlineKeyboardButton(text="🗑 Удалить канал", callback_data="op_remove")],
    [InlineKeyboardButton(text="📋 Список каналов", callback_data="op_list")],
    [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_panel")]
])

# ================= МАГАЗИН =================
shop_menu = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="🍬 50 • 💵 0.2", callback_data="pay_50"),
        InlineKeyboardButton(text="🍬 100 • 💵 0.3", callback_data="pay_100")
    ],
    [
        InlineKeyboardButton(text="🍬 140 • 💵 0.4", callback_data="pay_140"),
        InlineKeyboardButton(text="🍬 170 • 💵 0.5", callback_data="pay_170")
    ],
    [
        InlineKeyboardButton(text="🍬 200 • 💵 0.6", callback_data="pay_200"),
        InlineKeyboardButton(text="🍬 333 • 💵 1.0", callback_data="pay_333")
    ],
    [InlineKeyboardButton(text="✏️ Свое количество, дешевле на 25%", callback_data="pay_custom")],
    [InlineKeyboardButton(text="⭐️ Для оплаты звездами нажми на меня!", url=ANON_CHAT_LINK)],
    [InlineKeyboardButton(text="🔐 ПРИВАТКА | 599 ⭐️ / $5", callback_data="pay_private")],
    [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu")]
])

# ================= ВИДЕО МЕНЮ =================
video_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="▶️ Следующее видео", callback_data="videos")],
    [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu")]
])

# ================= МЕНЮ ПОДТВЕРЖДЕНИЯ =================
confirm_menu = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_broadcast"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_broadcast")
    ]
])