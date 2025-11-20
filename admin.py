import logging
from datetime import datetime, timedelta
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from asyncio import sleep

from database import Database, Movie
from config import config
from filters import IsAdmin, IsAdminCallback
from keyboards import (get_admin_panel_kb, get_back_to_admin_kb, get_cancel_kb,
                       get_confirmation_kb, get_quality_kb)
from utils import format_movie_info, format_number, create_progress_bar

router = Router()
logger = logging.getLogger(__name__)


# Admin States
class AdminStates(StatesGroup):
    # Kino qo'shish
    AddMovieFile = State()
    AddMovieCode = State()
    AddMovieTitle = State()
    AddMovieGenre = State()
    AddMovieDescription = State()
    AddMovieYear = State()
    AddMovieCountry = State()
    AddMovieDuration = State()
    AddMovieQuality = State()
    AddMovieIMDB = State()
    AddMovieThumbnail = State()

    # Kino tahrirlash
    EditMovieCode = State()
    EditMovieField = State()
    EditMovieValue = State()

    # Kino o'chirish
    DeleteMovieCode = State()
    DeleteMovieConfirm = State()

    # Rassilka
    BroadcastMessage = State()
    BroadcastConfirm = State()

    # Kanal qo'shish
    AddChannelUsername = State()
    AddChannelTitle = State()


# --- Admin Panel ---


@router.message(Command("admin"), IsAdmin())
async def admin_panel(message: Message, state: FSMContext, db: Database):
    """Admin panel"""
    await state.clear()

    stats = await db.get_global_stats()
    active_users = await db.get_active_users_count(7)

    text = ("🛠 <b>Admin Panel</b>\n\n"
            f"👥 Jami foydalanuvchilar: {format_number(stats['users_count'])}\n"
            f"🟢 Aktiv (7 kun): {format_number(active_users)}\n"
            f"🎬 Jami kinolar: {format_number(stats['movies_count'])}\n"
            f"👁 Jami ko'rishlar: {format_number(stats['total_views'])}\n\n"
            f"Quyidagi amallardan birini tanlang:")

    await message.answer(text,
                         reply_markup=get_admin_panel_kb(),
                         parse_mode="HTML")


@router.callback_query(F.data == "admin_panel_back", IsAdminCallback())
async def admin_panel_back(call: CallbackQuery, state: FSMContext,
                           db: Database):
    """Admin panelga qaytish"""
    await state.clear()
    await admin_panel(call.message, state, db)
    await call.answer()


# --- Kino Qo'shish ---


@router.callback_query(F.data == "admin_add_movie", IsAdminCallback())
async def add_movie_start(call: CallbackQuery, state: FSMContext):
    """Kino qo'shishni boshlash"""
    await state.clear()
    await call.message.edit_text(
        "📝 <b>Yangi kino qo'shish</b>\n\n"
        "1️⃣/11 Kino faylini (video yoki document) yuboring:\n\n"
        "💡 Maslahat: Video sifati HD yoki undan yuqori bo'lsin.",
        reply_markup=get_cancel_kb(),
        parse_mode="HTML")
    await state.set_state(AdminStates.AddMovieFile)
    await call.answer()


@router.message(AdminStates.AddMovieFile, IsAdmin())
async def get_movie_file(message: Message, state: FSMContext):
    """Kino faylini qabul qilish"""
    if message.video:
        file_id = message.video.file_id
    elif message.document:
        file_id = message.document.file_id
    else:
        await message.answer("❌ Iltimos, faqat video yoki document yuboring!")
        return

    await state.update_data(file_id=file_id)
    await message.answer(
        "2️⃣/11 Kino uchun noyob kodni kiriting:\n\n"
        "Masalan: <code>/code 1234</code>\n\n"
        "💡 Kod faqat raqamlardan iborat bo'lishi kerak.",
        reply_markup=get_cancel_kb(),
        parse_mode="HTML")
    await state.set_state(AdminStates.AddMovieCode)


@router.message(AdminStates.AddMovieCode, Command("code"), IsAdmin())
async def get_movie_code(message: Message, state: FSMContext, db: Database,
                         command: CommandObject):
    """Kino kodini qabul qilish"""
    if not command.args or not command.args.isdigit():
        await message.answer(
            "❌ Kod faqat raqamlardan iborat bo'lishi kerak!\n\nMasalan: <code>/code 1234</code>",
            parse_mode="HTML")
        return

    movie_code = int(command.args)

    if await db.get_movie_by_code(movie_code):
        await message.answer(
            f"❌ <code>{movie_code}</code> kodi allaqachon mavjud. Boshqa kod kiriting.",
            parse_mode="HTML")
        return

    await state.update_data(code=movie_code)
    await message.answer(
        "3️⃣/11 Kino nomini kiriting:\n\n"
        "Masalan: <code>Avatar 2</code>",
        reply_markup=get_cancel_kb(),
        parse_mode="HTML")
    await state.set_state(AdminStates.AddMovieTitle)


@router.message(AdminStates.AddMovieCode, IsAdmin())
async def get_movie_code_invalid(message: Message):
    """Noto'g'ri kod formati"""
    await message.answer(
        "❌ Noto'g'ri format!\n\n"
        "Kodni quyidagi formatda kiriting:\n"
        "<code>/code 1234</code>",
        parse_mode="HTML")


@router.message(AdminStates.AddMovieTitle, IsAdmin())
async def get_movie_title(message: Message, state: FSMContext):
    """Kino nomini qabul qilish"""
    if not message.text or len(message.text) < 2:
        await message.answer("❌ Kino nomi juda qisqa!")
        return

    await state.update_data(title=message.text)
    await message.answer(
        "4️⃣/11 Kino janrini kiriting:\n\n"
        "Masalan: <code>Fantastika, Jangari</code>\n\n"
        "💡 Bir nechta janrni vergul bilan ajratib yozishingiz mumkin.",
        reply_markup=get_cancel_kb(),
        parse_mode="HTML")
    await state.set_state(AdminStates.AddMovieGenre)


@router.message(AdminStates.AddMovieGenre, IsAdmin())
async def get_movie_genre(message: Message, state: FSMContext):
    """Janrni qabul qilish"""
    if not message.text or len(message.text) < 2:
        await message.answer("❌ Janr noto'g'ri!")
        return

    await state.update_data(genre=message.text)
    await message.answer(
        "5️⃣/11 Kino tavsifini kiriting:\n\n"
        "Yoki o'tkazib yuborish uchun: <code>/skip</code>",
        reply_markup=get_cancel_kb(),
        parse_mode="HTML")
    await state.set_state(AdminStates.AddMovieDescription)


@router.message(AdminStates.AddMovieDescription, IsAdmin())
async def get_movie_description(message: Message, state: FSMContext):
    """Tavsifni qabul qilish"""
    description = None if message.text == "/skip" else message.text

    await state.update_data(description=description)
    await message.answer(
        "6️⃣/11 Kino yilini kiriting:\n\n"
        "Masalan: <code>2024</code>\n"
        "O'tkazish: <code>/skip</code>",
        reply_markup=get_cancel_kb(),
        parse_mode="HTML")
    await state.set_state(AdminStates.AddMovieYear)


@router.message(AdminStates.AddMovieYear, IsAdmin())
async def get_movie_year(message: Message, state: FSMContext):
    """Yilni qabul qilish"""
    year = None
    if message.text != "/skip":
        try:
            year = int(message.text)
            if year < 1900 or year > datetime.now().year + 5:
                await message.answer("❌ Noto'g'ri yil!")
                return
        except ValueError:
            await message.answer("❌ Yil raqamlardan iborat bo'lishi kerak!")
            return

    await state.update_data(year=year)
    await message.answer(
        "7️⃣/11 Mamlakatni kiriting:\n\n"
        "Masalan: <code>AQSH, Angliya</code>\n"
        "O'tkazish: <code>/skip</code>",
        reply_markup=get_cancel_kb(),
        parse_mode="HTML")
    await state.set_state(AdminStates.AddMovieCountry)


@router.message(AdminStates.AddMovieCountry, IsAdmin())
async def get_movie_country(message: Message, state: FSMContext):
    """Mamlakatni qabul qilish"""
    country = None if message.text == "/skip" else message.text

    await state.update_data(country=country)
    await message.answer(
        "8️⃣/11 Kino davomiyligini kiriting (daqiqalarda):\n\n"
        "Masalan: <code>120</code>\n"
        "O'tkazish: <code>/skip</code>",
        reply_markup=get_cancel_kb(),
        parse_mode="HTML")
    await state.set_state(AdminStates.AddMovieDuration)


@router.message(AdminStates.AddMovieDuration, IsAdmin())
async def get_movie_duration(message: Message, state: FSMContext):
    """Davomiylikni qabul qilish"""
    duration = None
    if message.text != "/skip":
        try:
            duration = int(message.text)
            if duration < 1 or duration > 500:
                await message.answer("❌ Noto'g'ri davomiylik!")
                return
        except ValueError:
            await message.answer(
                "❌ Davomiylik raqamlardan iborat bo'lishi kerak!")
            return

    await state.update_data(duration=duration)
    await message.answer("9️⃣/11 Sifatni tanlang:",
                         reply_markup=get_quality_kb(),
                         parse_mode="HTML")
    await state.set_state(AdminStates.AddMovieQuality)


@router.callback_query(AdminStates.AddMovieQuality,
                       F.data.startswith("quality_"), IsAdminCallback())
async def get_movie_quality(call: CallbackQuery, state: FSMContext):
    """Sifatni qabul qilish"""
    quality = call.data.split("_")[1]

    await state.update_data(quality=quality)
    await call.message.edit_text(
        "🔟/11 IMDb reytingini kiriting:\n\n"
        "Masalan: <code>8.5</code>\n"
        "O'tkazish: <code>/skip</code>",
        parse_mode="HTML")
    await state.set_state(AdminStates.AddMovieIMDB)
    await call.answer()


@router.message(AdminStates.AddMovieIMDB, IsAdmin())
async def get_movie_imdb(message: Message, state: FSMContext):
    """IMDb reytingini qabul qilish"""
    imdb_rating = None
    if message.text != "/skip":
        try:
            imdb_rating = float(message.text)
            if imdb_rating < 0 or imdb_rating > 10:
                await message.answer("❌ Reyting 0 dan 10 gacha bo'lishi kerak!"
                                     )
                return
        except ValueError:
            await message.answer("❌ Reyting raqam bo'lishi kerak!")
            return

    await state.update_data(imdb_rating=imdb_rating)
    await message.answer(
        "1️⃣1️⃣/11 Thumbnail (rasm) yuboring:\n\n"
        "O'tkazish: <code>/skip</code>",
        reply_markup=get_cancel_kb(),
        parse_mode="HTML")
    await state.set_state(AdminStates.AddMovieThumbnail)


@router.message(AdminStates.AddMovieThumbnail, IsAdmin())
async def finalize_movie(message: Message, state: FSMContext, db: Database,
                         bot: Bot):
    """Kinoni yakunlash va saqlash"""
    thumbnail_file_id = None

    if message.text != "/skip":
        if message.photo:
            thumbnail_file_id = message.photo[-1].file_id
        else:
            await message.answer("❌ Rasm yuboring yoki /skip kiriting!")
            return

    data = await state.get_data()

    # Kinoni bazaga qo'shish
    try:
        movie: Movie = await db.add_movie(code=data['code'],
                                          file_id=data['file_id'],
                                          title=data['title'],
                                          genre=data['genre'],
                                          description=data.get('description'),
                                          year=data.get('year'),
                                          country=data.get('country'),
                                          duration=data.get('duration'),
                                          quality=data.get('quality', 'HD'),
                                          imdb_rating=data.get('imdb_rating'),
                                          thumbnail_file_id=thumbnail_file_id)

        logger.info(f"Yangi kino qo'shildi: {movie.title} (kod: {movie.code})")

    except Exception as e:
        logger.error(f"Kino qo'shishda xatolik: {e}")
        await message.answer(f"❌ Xatolik: {e}")
        await state.clear()
        return

    # Kanalga post yuborish
    bot_info = await bot.get_me()
    rating = await db.get_movie_rating(movie.id)

    post_text = format_movie_info(movie, rating)
    post_text += f"\n\n👇 Kinoni olish uchun botga o'ting:"

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text="🎬 Kinoni olish",
              url=f"https://t.me/{bot_info.username}?start=code_{movie.code}")

    try:
        if thumbnail_file_id:
            await bot.send_photo(chat_id=config.CHANNEL_USERNAME,
                                 photo=thumbnail_file_id,
                                 caption=post_text,
                                 reply_markup=kb.as_markup(),
                                 parse_mode="HTML")
        else:
            await bot.send_message(chat_id=config.CHANNEL_USERNAME,
                                   text=post_text,
                                   reply_markup=kb.as_markup(),
                                   parse_mode="HTML")
        await message.answer(
            f"✅ Kino muvaffaqiyatli qo'shildi va kanalga joylandi!\n\n"
            f"🎬 Nomi: {movie.title}\n"
            f"🔢 Kod: <code>{movie.code}</code>",
            parse_mode="HTML")
    except Exception as e:
        logger.error(f"Kanalga yuborishda xatolik: {e}")
        await message.answer(
            f"✅ Kino bazaga qo'shildi, lekin kanalga joylashda xatolik!\n\n"
            f"🔢 Kod: <code>{movie.code}</code>\n\n"
            f"❌ Xatolik: {e}",
            parse_mode="HTML")

    await state.clear()
    await admin_panel(message, state, db)


# --- Kino O‘chirish ---


@router.callback_query(F.data == "admin_delete_movie", IsAdminCallback())
async def delete_movie_start(call: CallbackQuery, state: FSMContext):
    """Kino o'chirishni boshlash"""
    await state.clear()
    await call.message.edit_text(
        "🗑 Kino kodini kiriting:\n\n"
        "Masalan: <code>/del 1234</code>",
        parse_mode="HTML",
        reply_markup=get_cancel_kb())
    await state.set_state(AdminStates.DeleteMovieCode)
    await call.answer()


@router.message(AdminStates.DeleteMovieCode, Command("del"), IsAdmin())
async def delete_movie_code(message: Message, state: FSMContext, db: Database,
                            command: CommandObject):
    """Kino kodini qabul qilish"""
    if not command.args or not command.args.isdigit():
        await message.answer(
            "❌ Kod noto‘g‘ri!\nMasalan: <code>/del 1234</code>",
            parse_mode="HTML")
        return

    code = int(command.args)
    movie = await db.get_movie_by_code(code)

    if not movie:
        await message.answer("❌ Bunday kodli kino topilmadi!")
        return

    await state.update_data(movie_id=movie.id)

    await message.answer(
        f"🗑 Siz <b>{movie.title}</b> (kod: {movie.code}) ni o‘chirmoqchimisiz?",
        reply_markup=get_confirmation_kb("delete_movie"),
        parse_mode="HTML")
    await state.set_state(AdminStates.DeleteMovieConfirm)


@router.callback_query(F.data == "confirm_delete_movie",
                       AdminStates.DeleteMovieConfirm, IsAdminCallback())
async def delete_movie_confirm(call: CallbackQuery, state: FSMContext,
                               db: Database):
    """Kino o'chirishni tasdiqlash"""
    data = await state.get_data()
    movie_id = data.get("movie_id")

    if not movie_id:
        await call.answer("Xatolik!", show_alert=True)
        return

    movie = await db.get_movie_by_id(movie_id)

    await db.delete_movie(movie_id)

    await state.clear()
    await call.message.edit_text(
        f"✅ Kino o‘chirildi!\n\n"
        f"🎬 <b>{movie.title}</b>", parse_mode="HTML")
    await call.answer()


# --- Statistika ---


@router.callback_query(F.data == "admin_stats", IsAdminCallback())
async def admin_stats(call: CallbackQuery, db: Database):
    """Admin statistika"""
    stats = await db.get_global_stats()
    active_1d = await db.get_active_users_count(1)
    active_7d = await db.get_active_users_count(7)
    active_30d = await db.get_active_users_count(30)

    top_movies = await db.get_top_movies(5)

    text = "📊 <b>Batafsil Statistika</b>\n\n"
    text += "<b>👥 Foydalanuvchilar:</b>\n"
    text += f"Jami: {format_number(stats['users_count'])}\n"
    text += f"🟢 Aktiv (24 soat): {format_number(active_1d)}\n"
    text += f"🟡 Aktiv (7 kun): {format_number(active_7d)}\n"
    text += f"🔵 Aktiv (30 kun): {format_number(active_30d)}\n\n"

    text += "<b>🎬 Kinolar:</b>\n"
    text += f"Jami: {format_number(stats['movies_count'])}\n"
    text += f"Jami ko'rishlar: {format_number(stats['total_views'])}\n\n"

    if top_movies:
        text += "<b>🔥 Top 5 kinolar:</b>\n"
        for i, movie in enumerate(top_movies, 1):
            text += f"{i}. {movie.title} - {format_number(movie.views_count)} 👁\n"

    await call.message.edit_text(text,
                                 reply_markup=get_back_to_admin_kb(),
                                 parse_mode="HTML")
    await call.answer()


# --- Rassilka ---


@router.callback_query(F.data == "admin_broadcast", IsAdminCallback())
async def broadcast_start(call: CallbackQuery, state: FSMContext):
    """Rassilkani boshlash"""
    await state.clear()
    await call.message.edit_text(
        "📢 <b>Rassilka</b>\n\n"
        "Yubormoqchi bo'lgan xabaringizni yuboring (matn, rasm, video, va h.k.):",
        reply_markup=get_cancel_kb(),
        parse_mode="HTML")
    await state.set_state(AdminStates.BroadcastMessage)
    await call.answer()


@router.message(AdminStates.BroadcastMessage, IsAdmin())
async def broadcast_confirm(message: Message, state: FSMContext):
    """Rassilkani tasdiqlash"""
    await state.update_data(message_id=message.message_id,
                            chat_id=message.chat.id)
    await message.answer(
        "✅ Xabar qabul qilindi!\n\n"
        "Rostdan ham barcha foydalanuvchilarga yuborilsinmi?",
        reply_markup=get_confirmation_kb("broadcast"))
    await state.set_state(AdminStates.BroadcastConfirm)


@router.callback_query(F.data == "confirm_broadcast",
                       AdminStates.BroadcastConfirm, IsAdminCallback())
async def broadcast_execute(call: CallbackQuery, state: FSMContext,
                            db: Database, bot: Bot):
    """Rassilkani bajarish"""
    data = await state.get_data()
    await state.clear()

    user_ids = await db.get_all_user_ids()
    total = len(user_ids)
    sent = 0
    failed = 0
    blocked = 0

    msg = await call.message.edit_text(f"📤 Rassilka boshlandi...\n\n"
                                       f"{create_progress_bar(0, total)}\n"
                                       f"0 / {total}")

    for i, user_id in enumerate(user_ids, 1):
        try:
            await bot.copy_message(chat_id=user_id,
                                   from_chat_id=data['chat_id'],
                                   message_id=data['message_id'])
            sent += 1
        except TelegramForbiddenError:
            blocked += 1
        except Exception:
            failed += 1

        # Progress yangilash (har 50 tadan)
        if i % 50 == 0 or i == total:
            try:
                await msg.edit_text(f"📤 Rassilka davom etmoqda...\n\n"
                                    f"{create_progress_bar(i, total)}\n"
                                    f"{i} / {total}")
            except:
                pass

        await sleep(config.MAX_BROADCAST_RATE)

    result_text = (f"✅ <b>Rassilka yakunlandi!</b>\n\n"
                   f"📊 Natijalar:\n"
                   f"✅ Yuborildi: {sent}\n"
                   f"🚫 Bloklangan: {blocked}\n"
                   f"❌ Xatolik: {failed}\n"
                   f"📊 Jami: {total}")

    await msg.edit_text(result_text, parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data == "cancel_broadcast", IsAdminCallback())
async def broadcast_cancel(call: CallbackQuery, state: FSMContext,
                           db: Database):
    """Rassilkani bekor qilish"""
    await state.clear()
    await call.message.edit_text("❌ Rassilka bekor qilindi")
    await admin_panel(call.message, state, db)
    await call.answer()


# --- Majburiy Obuna ---


@router.callback_query(F.data == "admin_fsub", IsAdminCallback())
async def fsub_menu(call: CallbackQuery, db: Database):
    """Majburiy obuna menyusi"""
    channels = await db.get_required_channels()
    channel_count = len(channels)

    text = f"🔐 <b>Majburiy obuna kanallari ({channel_count}/{config.MAX_CHANNELS})</b>\n\n"

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()

    if channels:
        for ch in channels:
            try:
                chat_info = await call.bot.get_chat(ch.channel_id)
                link = f"@{chat_info.username}" if chat_info.username else f"ID: {ch.channel_id}"
            except Exception:
                link = f"ID: {ch.channel_id} (Topilmadi)"

            text += f"• {ch.title} | {link}\n"
            kb.button(text=f"❌ {ch.title}",
                      callback_data=f"fsub_del_{ch.channel_id}")
    else:
        text += "Hozircha majburiy obuna kanallari yo'q."

    if channel_count < config.MAX_CHANNELS:
        kb.button(text="➕ Kanal qo'shish", callback_data="fsub_add")
    else:
        text += f"\n\n🛑 Maksimal kanal soniga ({config.MAX_CHANNELS}) yetildi."

    kb.button(text="⬅️ Ortga", callback_data="admin_panel_back")
    kb.adjust(1)

    await call.message.edit_text(text,
                                 reply_markup=kb.as_markup(),
                                 parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data == "fsub_add", IsAdminCallback())
async def fsub_add_start(call: CallbackQuery, state: FSMContext, db: Database):
    """Kanal qo'shishni boshlash"""
    if await db.count_required_channels() >= config.MAX_CHANNELS:
        await call.answer(
            f"Maksimal {config.MAX_CHANNELS} ta kanal qo'shish mumkin.",
            show_alert=True)
        return

    await call.message.edit_text(
        "Yangi kanal <b>Username</b>'ini kiriting:\n\n"
        "Masalan: <code>@mychannel</code>\n\n"
        "⚠️ Bot ushbu kanalga <b>Admin</b> qilingan bo'lishi kerak!",
        parse_mode="HTML")
    await state.set_state(AdminStates.AddChannelUsername)
    await call.answer()


@router.message(AdminStates.AddChannelUsername, IsAdmin())
async def fsub_add_username(message: Message, state: FSMContext, bot: Bot):
    """Kanal username'ini qabul qilish"""
    channel_username = message.text.strip()
    if not channel_username.startswith('@'):
        channel_username = '@' + channel_username

    try:
        chat = await bot.get_chat(channel_username)
        channel_id = chat.id

        member = await bot.get_chat_member(chat_id=channel_id, user_id=bot.id)
        if member.status not in ['administrator', 'creator']:
            await message.answer("❌ Bot bu kanalning admini emas!")
            return

        await state.update_data(channel_id=channel_id)
        await message.answer(
            "Kanal nomini kiriting (bu nom tugmada ko'rinadi):")
        await state.set_state(AdminStates.AddChannelTitle)

    except TelegramBadRequest:
        await message.answer(
            "❌ Bunday kanal topilmadi! Username'ni to'g'ri kiriting.")
    except Exception as e:
        await message.answer(f"❌ Xatolik: {e}")


@router.message(AdminStates.AddChannelTitle, IsAdmin())
async def fsub_add_finish(message: Message, state: FSMContext, db: Database):
    """Kanalni qo'shishni yakunlash"""
    data = await state.get_data()
    channel_id = data["channel_id"]
    title = message.text

    try:
        await db.add_required_channel(channel_id, title)
        await message.answer(f"✅ Kanal qo'shildi:\n{title} (ID: {channel_id})")
    except Exception:
        await message.answer("❌ Bu kanal allaqachon qo'shilgan!")

    await state.clear()
    await admin_panel(message, state, db)


@router.callback_query(F.data.startswith("fsub_del_"), IsAdminCallback())
async def fsub_delete(call: CallbackQuery, db: Database):
    """Kanalni o'chirish"""
    channel_id = int(call.data.split("_")[2])
    await db.delete_required_channel(channel_id)
    await call.answer("✅ Kanal o'chirildi!")
    await fsub_menu(call, db)


# --- Bekor qilish ---


@router.callback_query(F.data == "cancel", IsAdminCallback())
async def cancel_action(call: CallbackQuery, state: FSMContext, db: Database):
    """Amalni bekor qilish"""
    await state.clear()
    await call.message.edit_text("❌ Bekor qilindi")
    await admin_panel(call.message, state, db)
    await call.answer()
    # 1. "🎭 Janrlar" tugmasini bosganda
    @router.message(F.text == "🎭 Janrlar")
    async def show_genre_menu(message: Message):
        await message.answer("🎭 Janrni tanlang:", reply_markup=get_genre_kb())

    # 2. Janr tugmasi bosilganda
    @router.callback_query(F.data.startswith("genre_"))
    async def genre_selected(callback: CallbackQuery, db: Database):
        await callback.answer()

        # Tugmadan janr nomini olish
        genre_name = callback.data.split("_", 1)[1]

        # Bazadan janr bo‘yicha kinolarni olish
        movies = await db.get_movies_by_genre(genre_name)

        if not movies:
            await callback.message.answer(
                f"❌ <b>{genre_name}</b> janrida kino topilmadi.")
            return

        # Har bir kinoni alohida chiqarish
        for movie in movies:
            caption = format_movie_info(movie)
            await callback.message.answer_video(
                video=movie.file_id,
                caption=caption,
                reply_markup=get_movie_actions_kb(movie.code),
                parse_mode="HTML")
