from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import CHANNEL_LINK, ANON_CHAT_LINK, SUBSCRIPTIONS, PRIVATE_PRICE_STARS, PRIVATE_PRICE_USD, CANDY_PACKS

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

# ================= МЕНЮ ВИДЕО =================
video_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="👍 Лайк", callback_data="like_video"),
     InlineKeyboardButton(text="👎 Дизлайк", callback_data="dislike_video")],
    [InlineKeyboardButton(text="▶️ Следующее видео", callback_data="videos")],
    [InlineKeyboardButton(text="🏠 В меню", callback_data="menu_back")]
])

# ================= МЕНЮ МАГАЗИНА (НОВОЕ) =================
def get_shop_menu(balance: int = 0):
    """Главное меню магазина с паками конфет"""
    keyboard = [
        [
            InlineKeyboardButton(text="20 🍬", callback_data="buy_pack_20"),
            InlineKeyboardButton(text="35 🍬", callback_data="buy_pack_35"),
            InlineKeyboardButton(text="70 🍬", callback_data="buy_pack_70")
        ],
        [
            InlineKeyboardButton(text="180 🍬", callback_data="buy_pack_180")
        ],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_payment_methods_menu(pack_amount: int, usd_amount: float, stars_amount: int):
    """Меню выбора способа оплаты после выбора пака"""
    keyboard = [
        [InlineKeyboardButton(text="🏦 СБП (скоро)", callback_data="pay_sbp")],
        [InlineKeyboardButton(text="🪙 CryptoBot", callback_data=f"pay_method_cryptobot_{pack_amount}_{usd_amount}")],
        [InlineKeyboardButton(text="💎 xRocket", callback_data=f"pay_method_xrocket_{pack_amount}_{usd_amount}")],
        [InlineKeyboardButton(text="⭐️ Telegram Stars", callback_data=f"pay_method_stars_{pack_amount}_{stars_amount}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="shop")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_crypto_currency_menu(pack_amount: int, usd_amount: float, method: str):
    """Меню выбора валюты для CryptoBot или xRocket"""
    keyboard = [
        [
            InlineKeyboardButton(text="💵 USDT", callback_data=f"{method}_asset_{pack_amount}_{usd_amount}_USDT"),
            InlineKeyboardButton(text="💎 TON", callback_data=f"{method}_asset_{pack_amount}_{usd_amount}_TON")
        ],
        [
            InlineKeyboardButton(text="₿ BTC", callback_data=f"{method}_asset_{pack_amount}_{usd_amount}_BTC"),
            InlineKeyboardButton(text="Ξ ETH", callback_data=f"{method}_asset_{pack_amount}_{usd_amount}_ETH")
        ],
        [
            InlineKeyboardButton(text="🔶 BNB", callback_data=f"{method}_asset_{pack_amount}_{usd_amount}_BNB"),
            InlineKeyboardButton(text="🟣 LTC", callback_data=f"{method}_asset_{pack_amount}_{usd_amount}_LTC")
        ],
        [
            InlineKeyboardButton(text="🌞 TRX", callback_data=f"{method}_asset_{pack_amount}_{usd_amount}_TRX"),
            InlineKeyboardButton(text="💲 USDC", callback_data=f"{method}_asset_{pack_amount}_{usd_amount}_USDC")
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"back_to_payment_methods_{pack_amount}_{usd_amount}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_invoice_payment_menu(pay_url: str, invoice_id: str, method: str, pack_amount: int, crypto_amount: float, asset: str):
    """Меню с кнопкой оплаты и проверки для CryptoBot/xRocket"""
    keyboard = [
        [InlineKeyboardButton(text=f"💰 Оплатить {crypto_amount} {asset}", url=pay_url)],
        [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_{method}_{invoice_id}_{pack_amount}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="shop")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_stars_payment_menu(pack_amount: int, stars_amount: int):
    """Меню для оплаты звездами"""
    keyboard = [
        [InlineKeyboardButton(text="⭐️ Перейти к оплате", url=ANON_CHAT_LINK)],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"back_to_payment_methods_{pack_amount}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# ================= АДМИН-МЕНЮ ДЛЯ ПОДТВЕРЖДЕНИЯ ЗВЕЗД =================
def get_stars_approve_menu(request_id: int, pack_amount: int, user_id: int):
    """Меню для админа с кнопками Одобрить/Отклонить"""
    keyboard = [
        [
            InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_stars_{request_id}_{pack_amount}_{user_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_stars_{request_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# ================= МЕНЮ ЗАДАНИЙ С КАТЕГОРИЯМИ =================
def get_categories_menu():
    """Меню выбора категории заданий"""
    keyboard = [
        [InlineKeyboardButton(text="🥉 ЛЕГКИЕ ЗАДАЧИ", callback_data="tasks_category_easy")],
        [InlineKeyboardButton(text="🥈 СРЕДНИЕ ЗАДАЧИ", callback_data="tasks_category_medium")],
        [InlineKeyboardButton(text="🥇 ЛУЧШИЕ ЗАДАЧИ", callback_data="tasks_category_hard")],
        [InlineKeyboardButton(text="🏠 В меню", callback_data="menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_tasks_menu_by_category(tasks, category: str):
    """
    Создает клавиатуру со списком заданий для конкретной категории.
    Эмодзи статуса:
    - 🔄 - задание на проверке (pending)
    - ✅ - задание полностью выполнено (все возможные разы)
    - 📋 - задание еще не начато
    """
    keyboard = []
    
    for task in tasks:
        completed = task.get("completed", 0)
        max_completions = task.get("max_completions", 1)
        status = task.get("status")
        
        # Определяем эмодзи статуса
        if completed >= max_completions:
            emoji = "✅"
            status_text = " (выполнено)"
        elif status == "pending":
            emoji = "🔄"
            status_text = " (на проверке)"
        else:
            emoji = "📋"
            status_text = ""
        
        if max_completions > 1:
            counter = f" [{completed}/{max_completions}]"
        else:
            counter = ""
        
        keyboard.append([InlineKeyboardButton(
            text=f"{emoji} {task['title']}{status_text}{counter} | +{task['reward']} 🍬",
            callback_data=f"task_{task['id']}"
        )])
    
    keyboard.append([InlineKeyboardButton(text="🔄 Обновить", callback_data=f"tasks_refresh_{category}")])
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад к категориям", callback_data="tasks")])
    keyboard.append([InlineKeyboardButton(text="🏠 В меню", callback_data="menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_task_action_menu(task_id: int, task_title: str, task_reward: int, task_type: str, task_data: str, task_status: str = None):
    keyboard = []
    if task_status != "approved" and task_status != "pending":
        if task_type == "link":
            keyboard.append([InlineKeyboardButton(text="🔗 Перейти по ссылке", url=task_data)])
            keyboard.append([InlineKeyboardButton(text="✅ Я выполнил", callback_data=f"submit_task_{task_id}")])
        elif task_type == "text":
            keyboard.append([InlineKeyboardButton(text="📝 Выполнить задание", callback_data=f"do_task_{task_id}")])
        elif task_type == "photo" or task_type == "video":
            keyboard.append([InlineKeyboardButton(text="📤 Отправить доказательство", callback_data=f"do_task_{task_id}")])
    elif task_status == "pending":
        keyboard.append([InlineKeyboardButton(text="⏳ На проверке", callback_data="nothing")])
    elif task_status == "approved":
        keyboard.append([InlineKeyboardButton(text="✅ Выполнено", callback_data="nothing")])
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
            InlineKeyboardButton(text="💎 Выдать подписку", callback_data="admin_give_subscription"),
            InlineKeyboardButton(text="🔐 Управление ОП", callback_data="admin_op")
        ],
        [
            InlineKeyboardButton(text="📹 Загрузить видео", callback_data="admin_upload_url"),
            InlineKeyboardButton(text="📋 Управление заданиями", callback_data="admin_tasks")
        ],
        [
            InlineKeyboardButton(text="🗑 Управление заявками", callback_data="admin_manage_requests")
        ]
    ]
    if is_main_admin or can_manage_admins:
        buttons.append([InlineKeyboardButton(text="👥 Управление админами", callback_data="admin_manage")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ================= АДМИН-МЕНЮ ЗАДАНИЙ (С КАТЕГОРИЯМИ) =================
admin_tasks_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="➕ Создать задание", callback_data="admin_task_add")],
    [InlineKeyboardButton(text="✏️ Редактировать задание", callback_data="admin_task_edit")],
    [InlineKeyboardButton(text="🗑 Удалить задание", callback_data="admin_task_remove")],
    [InlineKeyboardButton(text="📋 Список заданий", callback_data="admin_task_list")],
    [InlineKeyboardButton(text="📂 Управление категориями", callback_data="admin_task_categories")],
    [InlineKeyboardButton(text="⏳ На проверке", callback_data="admin_task_pending")],
    [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_panel")]
])


def get_category_management_menu():
    """Меню управления категориями заданий"""
    keyboard = [
        [InlineKeyboardButton(text="🥉 ЛЕГКИЕ ЗАДАЧИ", callback_data="admin_category_easy")],
        [InlineKeyboardButton(text="🥈 СРЕДНИЕ ЗАДАЧИ", callback_data="admin_category_medium")],
        [InlineKeyboardButton(text="🥇 ЛУЧШИЕ ЗАДАЧИ", callback_data="admin_category_hard")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_tasks")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_tasks_by_category_menu(tasks, category: str):
    """Меню со списком заданий для выбора (для переноса в другую категорию)"""
    keyboard = []
    for task in tasks:
        keyboard.append([InlineKeyboardButton(
            text=f"{task['title']} | +{task['reward']} 🍬",
            callback_data=f"admin_move_task_{task['id']}_{category}"
        )])
    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_task_categories")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_move_category_menu(task_id: int):
    """Меню выбора категории для переноса задания"""
    keyboard = [
        [InlineKeyboardButton(text="🥉 ЛЕГКИЕ ЗАДАЧИ", callback_data=f"admin_move_to_easy_{task_id}")],
        [InlineKeyboardButton(text="🥈 СРЕДНИЕ ЗАДАЧИ", callback_data=f"admin_move_to_medium_{task_id}")],
        [InlineKeyboardButton(text="🥇 ЛУЧШИЕ ЗАДАЧИ", callback_data=f"admin_move_to_hard_{task_id}")],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_task_categories")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# ================= КЛАВИАТУРА ВЫБОРА КАТЕГОРИИ ПРИ СОЗДАНИИ ЗАДАНИЯ =================
task_category_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🥉 ЛЕГКИЕ ЗАДАЧИ", callback_data="task_category_easy")],
    [InlineKeyboardButton(text="🥈 СРЕДНИЕ ЗАДАЧИ", callback_data="task_category_medium")],
    [InlineKeyboardButton(text="🥇 ЛУЧШИЕ ЗАДАЧИ", callback_data="task_category_hard")]
])


# ================= МЕНЮ УПРАВЛЕНИЯ ЗАЯВКАМИ =================
def get_requests_menu(pending_tasks):
    keyboard = []
    for task in pending_tasks:
        keyboard.append([InlineKeyboardButton(
            text=f"⏳ {task['title']} | @{task['username']} | +{task['reward']}🍬",
            callback_data=f"admin_view_request_{task['id']}"
        )])
    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_request_action_menu(record_id: int, task_title: str, username: str, user_id: int, task_id: int, reward: int, proof: str):
    keyboard = [
        [
            InlineKeyboardButton(text="✅ Одобрить", callback_data=f"admin_approve_request_{record_id}_{user_id}_{task_id}_{reward}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"admin_reject_request_{record_id}_{user_id}_{task_id}")
        ],
        [InlineKeyboardButton(text="📝 Отправить на доработку", callback_data=f"admin_rework_request_{record_id}_{user_id}_{task_id}")],
        [InlineKeyboardButton(text="🗑 Удалить заявку", callback_data=f"admin_delete_request_{record_id}_{user_id}_{task_id}")],
        [InlineKeyboardButton(text="🔙 Назад к списку", callback_data="admin_manage_requests")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# ================= МЕНЮ ПОДТВЕРЖДЕНИЯ ДОРАБОТКИ =================
rework_confirm_menu = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="✅ Да, отправить", callback_data="confirm_rework"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_rework")
    ]
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


# ================= МЕНЮ ПОДПИСОК =================
subscriptions_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text=f"{SUBSCRIPTIONS['op']['name']} | {SUBSCRIPTIONS['op']['stars']}⭐️ / {SUBSCRIPTIONS['op']['usd']}$", callback_data="buy_subscription_op")],
    [InlineKeyboardButton(text=f"{SUBSCRIPTIONS['base']['name']} | {SUBSCRIPTIONS['base']['stars']}⭐️ / {SUBSCRIPTIONS['base']['usd']}$", callback_data="buy_subscription_base")],
    [InlineKeyboardButton(text=f"{SUBSCRIPTIONS['newbie']['name']} | {SUBSCRIPTIONS['newbie']['stars']}⭐️ / {SUBSCRIPTIONS['newbie']['usd']}$", callback_data="buy_subscription_newbie")],
    [InlineKeyboardButton(text="⬅️ Назад в магазин", callback_data="shop")]
])


# ================= МЕНЮ ПРИВАТКИ =================
private_pay_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text=f"⭐️ {PRIVATE_PRICE_STARS} звезд", callback_data="private_stars")],
    [InlineKeyboardButton(text=f"💰 Криптовалюта (${PRIVATE_PRICE_USD})", callback_data="private_crypto")],
    [InlineKeyboardButton(text="⬅️ Назад в магазин", callback_data="shop")]
])


# ================= МЕНЮ ВЫБОРА ВАЛЮТЫ ДЛЯ ПРИВАТКИ =================
def get_private_crypto_menu(assets):
    from payments import get_asset_icon
    keyboard = []
    row = []
    for i, asset in enumerate(assets):
        icon = get_asset_icon(asset)
        row.append(InlineKeyboardButton(text=f"{icon} {asset}", callback_data=f"private_asset_{asset}"))
        if (i + 1) % 2 == 0:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="buy_private")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# ================= МЕНЮ ПОДТВЕРЖДЕНИЯ =================
confirm_menu = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_broadcast"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_broadcast")
    ]
])