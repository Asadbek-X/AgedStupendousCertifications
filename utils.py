import logging
from typing import Tuple, Optional
from datetime import datetime
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database import Database, Movie

logger = logging.getLogger(__name__)

async def check_subscription(user_id: int, db: Database, bot: Bot) -> Tuple[bool, Optional[InlineKeyboardMarkup]]:
    """
    Majburiy obuna kanallarini tekshiradi
    Returns: (is_subscribed, keyboard)
    """
    channels = await db.get_required_channels()
    if not channels:
        return True, None

    not_subscribed_channels = []

    for ch in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch.channel_id, user_id=user_id)
            if member.status in ['left', 'kicked']:
                not_subscribed_channels.append(ch)
        except Exception as e:
            logger.warning(f"Kanal tekshirishda xatolik {ch.channel_id}: {e}")
            not_subscribed_channels.append(ch)

    if not not_subscribed_channels:
        return True, None

    kb = InlineKeyboardBuilder()
    for ch in not_subscribed_channels:
        url_link = await get_channel_invite_link(bot, ch.channel_id)
        kb.button(text=f"➕ {ch.title}", url=url_link)

    kb.button(text="✅ Obuna bo'ldim, tekshirish", callback_data="check_fsub")
    kb.adjust(1)

    return False, kb.as_markup()

async def get_channel_invite_link(bot: Bot, channel_id: int) -> str:
    """Kanal linkini olish"""
    try:
        chat_info = await bot.get_chat(channel_id)
        if chat_info.username:
            return f"https://t.me/{chat_info.username}"
        elif channel_id < 0:
            return f"https://t.me/c/{str(channel_id)[4:]}"
    except Exception:
        pass
    return "https://t.me/"

def format_movie_info(movie: Movie, rating: Tuple[float, int] = None, include_stats: bool = False) -> str:
    """Kino ma'lumotlarini formatlash"""
    text = f"🎬 <b>{movie.title}</b>\n\n"

    if movie.description:
        text += f"📝 {movie.description}\n\n"

    text += f"🎭 Janr: {movie.genre}\n"

    if movie.year:
        text += f"📅 Yil: {movie.year}\n"

    if movie.country:
        text += f"🌍 Mamlakat: {movie.country}\n"

    if movie.duration:
        hours = movie.duration // 60
        minutes = movie.duration % 60
        duration_str = f"{hours}s {minutes}d" if hours > 0 else f"{minutes}d"
        text += f"⏱ Davomiyligi: {duration_str}\n"

    text += f"🎥 Sifat: {movie.quality}\n"

    if movie.imdb_rating:
        text += f"⭐️ IMDb: {movie.imdb_rating}/10\n"

    if rating:
        avg_rating, count = rating
        if count > 0:
            stars = "⭐️" * int(avg_rating)
            text += f"📊 Baho: {stars} ({avg_rating}/5) - {count} ta ovoz\n"

    if include_stats:
        text += f"👁 Ko'rishlar: {movie.views_count}\n"

    text += f"\n🔢 Kod: <code>{movie.code}</code>"

    return text

def format_duration(minutes: int) -> str:
    """Davomiylikni formatlash"""
    if minutes < 60:
        return f"{minutes} daqiqa"
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours} soat {mins} daqiqa" if mins > 0 else f"{hours} soat"

def format_number(num: int) -> str:
    """Raqamni formatlash (1000 -> 1K)"""
    if num < 1000:
        return str(num)
    elif num < 1000000:
        return f"{num/1000:.1f}K"
    else:
        return f"{num/1000000:.1f}M"

def get_greeting() -> str:
    """Vaqtga qarab salomlashish"""
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return "🌅 Xayrli tong"
    elif 12 <= hour < 17:
        return "☀️ Xayrli kun"
    elif 17 <= hour < 21:
        return "🌆 Xayrli kech"
    else:
        return "🌙 Xayrli tun"

def escape_markdown(text: str) -> str:
    """Markdown maxsus belgilarni escape qilish"""
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

async def send_movie_with_caption(bot: Bot, chat_id: int, movie: Movie, caption: str, reply_markup=None):
    """Kinoni caption bilan yuborish"""
    try:
        if movie.thumbnail_file_id:
            await bot.send_video(
                chat_id=chat_id,
                video=movie.file_id,
                thumbnail=movie.thumbnail_file_id,
                caption=caption,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
        else:
            await bot.send_video(
                chat_id=chat_id,
                video=movie.file_id,
                caption=caption,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
    except Exception as e:
        logger.error(f"Video yuborishda xatolik: {e}")
        # Document sifatida yuborishga harakat
        try:
            await bot.send_document(
                chat_id=chat_id,
                document=movie.file_id,
                caption=caption,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
        except Exception as doc_error:
            logger.error(f"Document yuborishda xatolik: {doc_error}")
            raise

def validate_rating(rating: int) -> bool:
    """Baho validatsiyasi"""
    return 1 <= rating <= 5

def validate_movie_code(code: str) -> Optional[int]:
    """Kino kodi validatsiyasi"""
    try:
        code_int = int(code)
        if code_int > 0:
            return code_int
    except ValueError:
        pass
    return None

async def log_admin_action(db: Database, admin_id: int, action: str, details: str = ""):
    """Admin harakatlarini loglash"""
    logger.info(f"Admin {admin_id} | Action: {action} | Details: {details}")

def create_progress_bar(current: int, total: int, length: int = 10) -> str:
    """Progress bar yaratish"""
    filled = int((current / total) * length)
    bar = '█' * filled + '░' * (length - filled)
    percentage = int((current / total) * 100)
    return f"{bar} {percentage}%"