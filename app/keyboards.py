from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.config import settings



def main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Оставить заявку", callback_data="start_form")
    builder.button(text="Сайт", url=settings.site_url)
    builder.button(text="Telegram-канал", url=settings.tg_channel_url)
    builder.adjust(1, 2)
    return builder.as_markup()



def cancel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Отменить заявку", callback_data="cancel_form")
    return builder.as_markup()
