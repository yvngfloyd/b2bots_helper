from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder



def main_menu(site_url: str, tg_channel_url: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text='Оставить заявку', callback_data='start_form')
    )
    builder.row(
        InlineKeyboardButton(text='Сайт', url=site_url),
        InlineKeyboardButton(text='Telegram-канал', url=tg_channel_url),
    )
    return builder.as_markup()



def yes_no_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text='Да'), KeyboardButton(text='Нет')]],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder='Выберите вариант',
    )



def restart_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text='Оставить ещё одну заявку', callback_data='start_form'))
    return builder.as_markup()
