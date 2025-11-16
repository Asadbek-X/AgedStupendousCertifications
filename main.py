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
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Asosiy ob'ektlar
db = Database(config.DATABASE_URL)
bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()

# --- Asosiy Handlerlar ---

@dp.message(CommandStart())
async def cmd_start(message: Message, db: Database, state: FSMContext):
    """Start buyrug'i"""
    await state.clear()

    # Foydalanuvchini bazaga qo'shish
    await db.add_user(
        message.from_user.id,
        message.from_user.username or "",
        message.from_user.first_name or ""
    )

    # Obuna tekshirish
    is_subscribed, kb = await check_subscription(message.from_user.id, db, bot)

    if not is_subscribed:
        await message.answer(
            "👋 Xush kelibsiz!\n\n"
            "Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
            reply_markup=kb
        )
        return

    # Deep-linking orqali kino kodi
    if message.text and message.text.startswith('/start code_'):
        try:
            movie_code = int(message.text.split('_')[1])
            await send_movie_to_user(message.from_user.id, movie_code, db)
            return
        except (IndexError, ValueError):
            pass

    # Asosiy xush kelibsiz xabari
    greeting = f"👋 Xush kelibsiz, {message.from_user.first_name}!\n\n"
    greeting += "🎬 Bu bot orqali siz kinolarni tomosha qilishingiz mumkin.\n\n"
    greeting += "📝 Quyidagi tugmalardan foydalaning yoki kino kodini kiriting."

    await message.answer(greeting, reply_markup=get_main_menu_kb())

@dp.callback_query(F.data == "check_fsub")
async def check_subscription_callback(call: CallbackQuery, db: Database):
    """Obuna tekshirish callback"""
    is_subscribed, kb = await check_subscription(call.from_user.id, db, bot)

    if is_subscribed:
        await call.message.edit_text(
            "✅ Ajoyib! Barcha kanallarga obuna bo'lgansiz.\n\n"
            "Endi kino kodini kiriting yoki quyidagi tugmalardan foydalaning.",
            reply_markup=None
        )
        await call.message.answer("Asosiy menu:", reply_markup=get_main_menu_kb())
        await call.answer("✅ Obuna tasdiqlandi!")
    else:
        await call.answer("❌ Hali barcha kanallarga obuna bo'lmadingiz!", show_alert=True)
        await call.message.edit_reply_markup(reply_markup=kb)

@dp.message(F.text.isdigit())
async def handle_movie_code(message: Message, db: Database, state: FSMContext):
    """Kino kodini qayta ishlash"""
    # FSM holati tekshiruvi (admin konfliktini oldini olish)
    current_state = await state.get_state()
    if current_state is not None:
        return

    movie_code = validate_movie_code(message.text)
    if not movie_code:
        await message.answer("❌ Noto'g'ri kod formati!")
        return

    await send_movie_to_user(message.from_user.id, movie_code, db)

async def send_movie_to_user(user_id: int, movie_code: int, db: Database):
    """Foydalanuvchiga kino yuborish"""
    # Obuna tekshirish
    is_subscribed, kb = await check_subscription(user_id, db, bot)
    if not is_subscribed:
        await bot.send_message(
            user_id,
            "⚠️ Kinoni olishdan oldin kanallarga obuna bo'ling:",
            reply_markup=kb
        )
        return

    # Kinoni topish
    movie = await db.get_movie_by_code(movie_code)
    if not movie:
        await bot.send_message(
            user_id,
            f"❌ <code>{movie_code}</code> kodli kino topilmadi.\n\n"
            "🔍 Qidirish tugmasidan foydalaning yoki to'g'ri kodni kiriting.",
            parse_mode="HTML",
            reply_markup=get_main_menu_kb()
        )
        return

    # Ko'rishni qayd qilish
    await db.add_movie_view(user_id, movie.id)

    # Reytingni olish
    rating = await db.get_movie_rating(movie.id)
    user_rating = await db.get_user_movie_rating(user_id, movie.id)

    # Ma'lumotlarni formatlash
    caption = format_movie_info(movie, rating, include_stats=True)

    # Kinoni yuborish
    try:
        await send_movie_with_caption(
            bot,
            user_id,
            movie,
            caption,
            reply_markup=get_movie_actions_kb(movie_code, bool(user_rating))
        )
        logger.info(f"User {user_id} kinoni ko'rdi: {movie.title} (kod: {movie_code})")
    except Exception as e:
        logger.error(f"Kino yuborishda xatolik: {e}")
        await bot.send_message(
            user_id,
            "❌ Kino yuborishda xatolik yuz berdi. Iltimos qayta urinib ko'ring."
        )

# --- Bot buyruqlari ---

async def set_bot_commands():
    """Bot buyruqlarini sozlash"""
    commands = [
        BotCommand(command="start", description="Botni ishga tushirish"),
        BotCommand(command="help", description="Yordam"),
        BotCommand(command="search", description="Kino qidirish"),
        BotCommand(command="top", description="Top kinolar"),
        BotCommand(command="new", description="Yangi kinolar"),
        BotCommand(command="stats", description="Statistika"),
        BotCommand(command="admin", description="Admin panel (faqat admin)"),
    ]
    await bot.set_my_commands(commands)

# --- Startup va Shutdown ---

async def on_startup():
    """Bot ishga tushganda"""
    logger.info("Bot ishga tushmoqda...")

    # Database
    await db.init_db()
    logger.info("Database tayyor")

    # Bot buyruqlari
    await set_bot_commands()
    logger.info("Bot buyruqlari o'rnatildi")

    # Admin xabarnoma
    try:
        await bot.send_message(config.ADMIN_ID, "✅ Bot muvaffaqiyatli ishga tushdi!")
    except Exception:
        pass

    logger.info("Bot ishga tushdi!")

async def on_shutdown():
    """Bot to'xtaganda"""
    logger.info("Bot to'xtatilmoqda...")

    # Admin xabarnoma
    try:
        await bot.send_message(config.ADMIN_ID, "⚠️ Bot to'xtatildi!")
    except Exception:
        pass

    await bot.session.close()
    logger.info("Bot to'xtatildi")

# --- Asosiy funksiya ---

async def main():
    """Asosiy funksiya"""
    # Routerlarni ulash
    dp.include_router(admin_router)
    dp.include_router(user_router)

    # Middleware data
    dp["db"] = db
    dp["config"] = config

    # Startup va shutdown
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Polling
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot foydalanuvchi tomonidan to'xtatildi")
    except Exception as e:
        logger.error(f"Botda xatolik: {e}", exc_info=True)