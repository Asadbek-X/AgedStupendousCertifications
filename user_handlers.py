import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineQueryResultArticle, InputTextMessageContent, InlineQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import Database
from utils import (
    check_subscription, format_movie_info, format_number,
    get_greeting, validate_rating
)
from keyboards import (
    get_main_menu_kb, get_rating_kb, get_genre_kb,
    get_pagination_kb, get_back_to_admin_kb
)

router = Router()
logger = logging.getLogger(__name__)

# FSM States
class UserStates(StatesGroup):
    SearchMovie = State()
    RatingReview = State()

# --- Asosiy Tugmalar ---

@router.message(F.text == "🔍 Qidirish")
async def search_movies_button(message: Message, state: FSMContext):
    """Qidirish tugmasi"""
    await message.answer(
        "🔍 Qidiruv\n\n"
        "Kino nomini yoki janrini kiriting:",
        reply_markup=get_main_menu_kb()
    )
    await state.set_state(UserStates.SearchMovie)

@router.message(UserStates.SearchMovie)
async def search_movies_handler(message: Message, state: FSMContext, db: Database):
    """Qidiruv natijalarini ko'rsatish"""
    query = message.text.strip()

    if len(query) < 2:
        await message.answer("❌ Kamida 2 ta belgi kiriting!")
        return

    movies = await db.search_movies(query, limit=10)

    if not movies:
        await message.answer(
            f"❌ '{query}' bo'yicha hech narsa topilmadi.\n\n"
            "💡 Maslahat: Boshqa so'z yoki janr bilan qidiring.",
            reply_markup=get_main_menu_kb()
        )
        await state.clear()
        return

    text = f"🔍 <b>'{query}'</b> bo'yicha {len(movies)} ta natija:\n\n"

    for i, movie in enumerate(movies, 1):
        rating = await db.get_movie_rating(movie.id)
        stars = "⭐️" * int(rating[0]) if rating[1] > 0 else "—"

        text += (
            f"{i}. <b>{movie.title}</b>\n"
            f"   {movie.genre} | {movie.quality} | {stars}\n"
            f"   Kod: <code>{movie.code}</code>\n\n"
        )

    text += "💡 Kino olish uchun kodini kiriting."

    await message.answer(text, parse_mode="HTML", reply_markup=get_main_menu_kb())
    await state.clear()

@router.message(F.text == "🎬 Top kinolar")
@router.message(Command("top"))
async def top_movies_handler(message: Message, db: Database):
    """Top kinolar"""
    movies = await db.get_top_movies(limit=10)

    if not movies:
        await message.answer("Hozircha kinolar yo'q.", reply_markup=get_main_menu_kb())
        return

    text = "🏆 <b>Top 10 kinolar</b>\n\n"

    for i, movie in enumerate(movies, 1):
        rating = await db.get_movie_rating(movie.id)
        stars = "⭐️" * int(rating[0]) if rating[1] > 0 else "—"
        views = format_number(movie.views_count)

        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."

        text += (
            f"{medal} <b>{movie.title}</b>\n"
            f"   {stars} | 👁 {views} | {movie.genre}\n"
            f"   Kod: <code>{movie.code}</code>\n\n"
        )

    await message.answer(text, parse_mode="HTML", reply_markup=get_main_menu_kb())

@router.message(F.text == "🆕 Yangi kinolar")
@router.message(Command("new"))
async def new_movies_handler(message: Message, db: Database):
    """Yangi kinolar"""
    movies = await db.get_recent_movies(limit=10)

    if not movies:
        await message.answer("Hozircha kinolar yo'q.", reply_markup=get_main_menu_kb())
        return

    text = "🆕 <b>Yangi qo'shilgan kinolar</b>\n\n"

    for i, movie in enumerate(movies, 1):
        rating = await db.get_movie_rating(movie.id)
        stars = "⭐️" * int(rating[0]) if rating[1] > 0 else "—"

        text += (
            f"{i}. <b>{movie.title}</b>\n"
            f"   {stars} | {movie.genre} | {movie.quality}\n"
            f"   Kod: <code>{movie.code}</code>\n\n"
        )

    await message.answer(text, parse_mode="HTML", reply_markup=get_main_menu_kb())

@router.message(F.text == "📊 Statistika")
@router.message(Command("stats"))
async def user_stats_handler(message: Message, db: Database):
    """Foydalanuvchi statistikasi"""
    user_stats = await db.get_user_stats(message.from_user.id)
    global_stats = await db.get_global_stats()

    text = f"📊 <b>Sizning statistikangiz</b>\n\n"
    text += f"👁 Ko'rilgan kinolar: {user_stats['views_count']}\n"
    text += f"⭐️ Berilgan baholar: {user_stats['ratings_count']}\n\n"

    text += f"🌍 <b>Umumiy statistika</b>\n\n"
    text += f"👥 Foydalanuvchilar: {format_number(global_stats['users_count'])}\n"
    text += f"🎬 Kinolar: {format_number(global_stats['movies_count'])}\n"
    text += f"👁 Jami ko'rishlar: {format_number(global_stats['total_views'])}\n"

    await message.answer(text, parse_mode="HTML", reply_markup=get_main_menu_kb())

@router.message(F.text == "ℹ️ Ma'lumot")
@router.message(Command("help"))
async def help_handler(message: Message):
    """Yordam"""
    text = (
        "ℹ️ <b>Bot haqida ma'lumot</b>\n\n"
        "Bu bot orqali siz minglab kinolarni bepul tomosha qilishingiz mumkin.\n\n"
        "<b>Qanday foydalanish:</b>\n"
        "1️⃣ Kino kodini kiriting\n"
        "2️⃣ Yoki qidirish tugmasidan foydalaning\n"
        "3️⃣ Top va yangi kinolarni ko'ring\n\n"
        "<b>Buyruqlar:</b>\n"
        "/start - Botni ishga tushirish\n"
        "/search - Kino qidirish\n"
        "/top - Top kinolar\n"
        "/new - Yangi kinolar\n"
        "/stats - Statistika\n"
        "/help - Yordam\n\n"
        "❓ Savollar bo'lsa admin bilan bog'laning."
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_menu_kb())

# --- Baho berish ---

@router.callback_query(F.data.startswith("rate_"))
async def rate_movie_callback(call: CallbackQuery, db: Database):
    """Kinoga baho berish"""
    movie_code = int(call.data.split("_")[1])

    await call.message.answer(
        "⭐️ Kinoga baho bering:\n\n"
        "1 ⭐️ - Juda yomon\n"
        "2 ⭐️ - Yomon\n"
        "3 ⭐️ - O'rtacha\n"
        "4 ⭐️ - Yaxshi\n"
        "5 ⭐️ - A'lo!",
        reply_markup=get_rating_kb(movie_code)
    )
    await call.answer()

@router.callback_query(F.data.startswith("rating_"))
async def save_rating_callback(call: CallbackQuery, state: FSMContext, db: Database):
    """Bahoni saqlash"""
    parts = call.data.split("_")
    movie_code = int(parts[1])
    rating = int(parts[2])

    if not validate_rating(rating):
        await call.answer("❌ Noto'g'ri baho!", show_alert=True)
        return

    movie = await db.get_movie_by_code(movie_code)
    if not movie:
        await call.answer("❌ Kino topilmadi!", show_alert=True)
        return

    # Bahoni saqlash
    await db.add_rating(call.from_user.id, movie.id, rating)

    # Yangilangan reytingni olish
    avg_rating, count = await db.get_movie_rating(movie.id)

    await call.message.edit_text(
        f"✅ Rahmat! Sizning bahongiz qabul qilindi.\n\n"
        f"🎬 {movie.title}\n"
        f"⭐️ Sizning bahoyingiz: {'⭐️' * rating}\n"
        f"📊 O'rtacha baho: {'⭐️' * int(avg_rating)} ({avg_rating}/5)\n"
        f"👥 Jami {count} ta baho"
    )
    await call.answer("✅ Baho saqlandi!")

@router.callback_query(F.data == "cancel_rating")
async def cancel_rating(call: CallbackQuery):
    """Bahoni bekor qilish"""
    await call.message.delete()
    await call.answer("Bekor qilindi")

@router.callback_query(F.data.startswith("movie_stats_"))
async def movie_stats_callback(call: CallbackQuery, db: Database):
    """Kino statistikasi"""
    movie_code = int(call.data.split("_")[2])
    movie = await db.get_movie_by_code(movie_code)

    if not movie:
        await call.answer("❌ Kino topilmadi!", show_alert=True)
        return

    rating = await db.get_movie_rating(movie.id)

    text = f"📊 <b>{movie.title}</b>\n\n"
    text += f"👁 Ko'rishlar: {format_number(movie.views_count)}\n"

    if rating[1] > 0:
        text += f"⭐️ Baho: {'⭐️' * int(rating[0])} ({rating[0]}/5)\n"
        text += f"👥 Baholar soni: {rating[1]}\n"
    else:
        text += "⭐️ Hali baholanmagan\n"

    text += f"\n🔢 Kod: <code>{movie.code}</code>"

    await call.message.answer(text, parse_mode="HTML")
    await call.answer()

# --- Inline Mode ---

@router.inline_query()
async def inline_query_handler(inline_query: InlineQuery, db: Database):
    """Inline rejim"""
    query = inline_query.query.strip()

    if not query:
        await inline_query.answer([])
        return

    # Agar kod kiritilgan bo'lsa
    if query.startswith("code_"):
        try:
            code = int(query.split("_")[1])
            movie = await db.get_movie_by_code(code)

            if movie:
                bot_info = await inline_query.bot.get_me()
                results = [
                    InlineQueryResultArticle(
                        id=str(movie.id),
                        title=movie.title,
                        description=f"{movie.genre} | {movie.quality}",
                        input_message_content=InputTextMessageContent(
                            message_text=f"🎬 {movie.title}\n\n"
                                       f"Kodni kiriting: {movie.code}\n"
                                       f"yoki: t.me/{bot_info.username}?start=code_{movie.code}"
                        )
                    )
                ]
                await inline_query.answer(results, cache_time=60)
                return
        except (ValueError, IndexError):
            pass

    # Qidiruv
    movies = await db.search_movies(query, limit=20)

    if not movies:
        await inline_query.answer([])
        return

    bot_info = await inline_query.bot.get_me()
    results = []

    for movie in movies:
        rating = await db.get_movie_rating(movie.id)
        stars = "⭐️" * int(rating[0]) if rating[1] > 0 else ""

        results.append(
            InlineQueryResultArticle(
                id=str(movie.id),
                title=movie.title,
                description=f"{movie.genre} | {movie.quality} {stars}",
                input_message_content=InputTextMessageContent(
                    message_text=f"🎬 <b>{movie.title}</b>\n\n"
                               f"{movie.genre} | {movie.quality}\n"
                               f"Kod: <code>{movie.code}</code>\n\n"
                               f"👉 @{bot_info.username}",
                    parse_mode="HTML"
                )
            )
        )

    await inline_query.answer(results, cache_time=300)