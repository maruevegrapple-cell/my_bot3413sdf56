from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

main_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🎥 Смотреть видео", callback_data="video")],
    [InlineKeyboardButton(text="🍬 Шоп конфет", callback_data="shop")],
    [InlineKeyboardButton(text="👤 Профиль", callback_data="profile")],
    [InlineKeyboardButton(text="🎁 Бонус", callback_data="bonus")],
    [InlineKeyboardButton(text="💳 Пополнить баланс", callback_data="pay")],
    [InlineKeyboardButton(text="📢 Резервный канал", url="https://t.me/your_channel")]
])
