# ====== KEEP ALIVE (REPLIT 24/7) ======
from flask import Flask
from threading import Thread

app = Flask('')


@app.route('/')
def home():
    return "Bot ishlayapti!"


def run():
    app.run(host='0.0.0.0', port=8080)


def keep_alive():
    t = Thread(target=run)
    t.start()


# ====== ASOSIY BOT KODI PASTDA ======

import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, BotCommand
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from config import config
from database import Database
from admin import router as admin_router
from user_handlers import router as user_router
from utils import check_subscription, format_movie_info, send_movie_with_caption, validate_movie_code
from keyboards import get_main_menu_kb, get_movie_actions_kb

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Asosiy obyektlar
db = Database(config.DATABASE_URL)
bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()


# --- Handlerlar ---
@dp.message(CommandStart())
async def cmd_start(message: Message, db: Database, state: FSMContext):
    await state.clear()
    await db.add_user(message.from_user.id, message.from_user.username or "",
                      message.from_user.first_name or "")
    is_subscribed, kb = await check_subscription(message.from_user.id, db, bot)

    if not is_subscribed:
        await message.answer(
            "👋 Xush kelibsiz!\n\nBotdan foydalanish uchun kanallarga obuna bo‘ling:",
            reply_markup=kb)
        return

    if message.text and message.text.startswith('/start code_'):
        try:
            code = int(message.text.split('_')[1])
            await send_movie_to_user(message.from_user.id, code, db)
            return
        except:
            pass

    await message.answer(
        f"👋 Xush kelibsiz, {message.from_user.first_name} Kino codini kiriting!",
        reply_markup=get_main_menu_kb())


@dp.callback_query(F.data == "check_fsub")
async def check_subscription_callback(call: CallbackQuery, db: Database):
    is_subscribed, kb = await check_subscription(call.from_user.id, db, bot)

    if is_subscribed:
        await call.message.edit_text("✅ Obuna tasdiqlandi!")
        await call.message.answer("Asosiy menu:",
                                  reply_markup=get_main_menu_kb())
    else:
        await call.answer("❌ Hali obuna bo‘lmagansiz!", show_alert=True)
        await call.message.edit_reply_markup(reply_markup=kb)


@dp.message(F.text.isdigit())
async def handle_movie_code(message: Message, db: Database, state: FSMContext):
    state_now = await state.get_state()
    if state_now:
        return
    code = validate_movie_code(message.text)
    if not code:
        await message.answer("❌ Noto‘g‘ri kod!")
        return
    await send_movie_to_user(message.from_user.id, code, db)


async def send_movie_to_user(user_id: int, code: int, db: Database):
    is_subscribed, kb = await check_subscription(user_id, db, bot)
    if not is_subscribed:
        await bot.send_message(user_id,
                               "⚠️ Avval obuna bo‘ling:",
                               reply_markup=kb)
        return

    movie = await db.get_movie_by_code(code)
    if not movie:
        await bot.send_message(user_id, "❌ Kino topilmadi!")
        return

    await db.add_movie_view(user_id, movie.id)
    rating = await db.get_movie_rating(movie.id)
    user_rating = await db.get_user_movie_rating(user_id, movie.id)

    caption = format_movie_info(movie, rating, include_stats=True)

    try:
        await send_movie_with_caption(bot,
                                      user_id,
                                      movie,
                                      caption,
                                      reply_markup=get_movie_actions_kb(
                                          code, bool(user_rating)))
    except:
        await bot.send_message(user_id, "❌ Kino yuborishda xatolik!")


async def set_bot_commands():
    commands = [
        BotCommand(command="start", description="Botni ishga tushirish"),
        BotCommand(command="help", description="Yordam")
    ]
    await bot.set_my_commands(commands)


async def on_startup():
    await db.init_db()
    await set_bot_commands()


async def on_shutdown():
    await bot.session.close()


async def main():
    dp.include_router(admin_router)
    dp.include_router(user_router)

    dp["db"] = db
    dp["config"] = config

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    keep_alive()  # ← ***MUHIM: Replit 24/7 ishlashi uchun***

    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
