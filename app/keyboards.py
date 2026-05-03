from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def make_choice_keyboard(prefix: str, options: list[str], back: bool = True) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for idx, option in enumerate(options, start=1):
        builder.button(text=option, callback_data=f"{prefix}:{idx}")
    if back:
        builder.button(text="← Назад", callback_data="nav:back")
    builder.adjust(1)
    return builder.as_markup()


final_business_types = [
    "Услуги",
    "Продажи / магазин",
    "Онлайн-школа",
    "Клиника / бьюти",
    "Недвижимость",
    "Авто / сервис",
    "Другое",
]

lead_sources = [
    "Telegram",
    "WhatsApp",
    "Instagram / соцсети",
    "Сайт",
    "Авито / маркетплейсы",
    "Сразу из нескольких каналов",
]

current_problems = [
    "Отвечаем вручную",
    "Отвечаем не сразу",
    "Теряем часть заявок",
    "Нет системы",
    "Уже есть бот, но слабый",
]

main_goals = [
    "Не терять заявки",
    "Отвечать 24/7",
    "Квалифицировать клиентов",
    "Собирать контакты",
    "Передавать заявки менеджеру",
    "Автоматизировать всё сразу",
]

integration_needs = [
    "Да, обязательно",
    "Желательно",
    "Пока не нужна",
    "Не знаю",
]

launch_times = [
    "Как можно скорее",
    "В течение недели",
    "В течение месяца",
    "Просто изучаю варианты",
]

budgets = [
    "До 10 000 ₽",
    "10–30 000 ₽",
    "30–50 000 ₽",
    "50 000 ₽+",
    "Пока не определился",
]

contact_methods = [
    "Подставить мой username",
    "Написать телефон вручную",
    "Написать другой контакт",
]


def final_links_keyboard(site_url: str, tg_channel_url: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Перейти на сайт", url=site_url)
    builder.button(text="Перейти в Telegram-канал", url=tg_channel_url)
    builder.button(text="Оставить новую заявку", callback_data="form:restart")
    builder.adjust(1)
    return builder.as_markup()


def subscription_required_keyboard(channel_url: str, check_callback_data: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Подписаться на канал", url=channel_url)
    builder.button(text="Проверить подписку", callback_data=check_callback_data)
    builder.adjust(1)
    return builder.as_markup()
