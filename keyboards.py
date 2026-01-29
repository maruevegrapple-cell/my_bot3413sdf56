from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import RESERVE_CHANNEL

fake_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📥 Скачать видео", callback_data="fake_download")],
    [InlineKeyboardButton(text="💱 Курс валют", callback_data="fake_rate")],
    [InlineKeyboardButton(text="🎲 Кости", callback_data="fake_dice")]
])

main_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="▶️ Смотреть видео", callback_data="videos")],
    [
        InlineKeyboardButton(text="🍬 Шоп конфет", callback_data="shop"),
        InlineKeyboardButton(text="👤 Профиль", callback_data="profile")
    ],
    [
        InlineKeyboardButton(text="🎁 Бонус", callback_data="bonus"),
        InlineKeyboardButton(text="🎟 Промокод", callback_data="promo")
    ],
    [InlineKeyboardButton(text="📢 Резервный канал", url=RESERVE_CHANNEL)]
])

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
        InlineKeyboardButton(text="🍬 333 • 💵 1", callback_data="pay_333")
    ],
    [InlineKeyboardButton(text="✏️ Свое количество", callback_data="pay_custom")],
    [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu")]
])

video_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="▶️ Следующее видео", callback_data="videos")],
    [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu")]
])
