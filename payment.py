from aiogram import Router, types
from config import ADMIN_IDS

router = Router()

@router.callback_query(lambda c: c.data == "pay")
async def pay(call: types.CallbackQuery):
    text = (
        "Курс:\n"
        "1$ = 299 конфет\n"
        "75 ⭐ Telegram\n\n"
        "Если вам нужно больше,\n"
        "умножайте свое число на 2\n\n"
        "Оплата принимается:\n"
        "• CryptoBot\n"
        "• Telegram Stars\n\n"
        "Для покупки напишите:\n"
        "@balikcyda"
    )
    await call.message.answer(text)

    for admin in ADMIN_IDS:
        await call.bot.send_message(
            admin,
            f"🔔 Запрос на покупку\n\n"
            f"👤 @{call.from_user.username}\n"
            f"🆔 {call.from_user.id}"
        )
