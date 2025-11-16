from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery
from config import config

class IsAdmin(BaseFilter):
    """Admin tekshirish filteri"""
    async def __call__(self, message: Message) -> bool:
        return message.from_user.id == config.ADMIN_ID

class IsAdminCallback(BaseFilter):
    """Callback uchun admin filteri"""
    async def __call__(self, callback: CallbackQuery) -> bool:
        return callback.from_user.id == config.ADMIN_ID