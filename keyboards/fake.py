from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

fake_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🎥 Скачать видео с YouTube", callback_data="yt")],
    [InlineKeyboardButton(text="💱 Узнать курс валют", callback_data="rate")],
    [InlineKeyboardButton(text="🎲 Сыграть в кости", callback_data="dice")]
])
