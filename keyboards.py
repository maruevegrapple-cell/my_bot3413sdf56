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
        InlineKeyboardButton(text="🎟 Ввести промокод", callback_data="promo")
    ],
    [InlineKeyboardButton(text="📢 Резервный канал", url=RESERVE_CHANNEL)]
])

video_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="▶️ Следующее видео", callback_data="videos")],
    [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu")]
])
