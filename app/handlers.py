from __future__ import annotations

from html import escape

from aiogram import Bot, Dispatcher, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.config import settings
from app.keyboards import cancel_keyboard, main_menu
from app.states import LeadForm

router = Router()

QUESTIONS: list[tuple[str, str]] = [
    ("name", "Как вас зовут?"),
    ("business_name", "Как называется ваш бизнес или проект?"),
    ("niche", "Какая у вас ниша или чем вы занимаетесь?"),
    ("city", "Из какого вы города или региона?"),
    (
        "current_process",
        "Как вы сейчас принимаете заявки и сообщения от клиентов? Например: вручную в Telegram, WhatsApp, Instagram, через менеджера, CRM и так далее.",
    ),
    ("lead_volume", "Сколько обращений или заявок у вас примерно в месяц?"),
    (
        "lead_sources",
        "Откуда к вам сейчас чаще всего приходят клиенты? Например: Telegram, реклама, сайт, сарафан, Avito и так далее.",
    ),
    (
        "main_goal",
        "Какую задачу вы хотите решить ботом в первую очередь? Например: не терять лидов, быстрее отвечать, квалифицировать заявки, собирать контакты, разгрузить менеджера.",
    ),
    ("budget", "Какой бюджет вы готовы рассматривать на внедрение?"),
    ("timeline", "Когда вам желательно запустить решение?"),
    ("decision_maker", "Кто принимает решение по внедрению? Вы лично или еще кто-то участвует?"),
    (
        "contact",
        "Оставьте удобный контакт для связи: @username, телефон, Telegram или несколько вариантов сразу.",
    ),
    (
        "extra",
        "Есть ли дополнительные детали, которые важно учесть? Если нет, напишите: нет.",
    ),
]


async def send_welcome(message: Message) -> None:
    text = (
        "<b>B2Bots Helper</b>\n\n"
        "Помогаю быстро понять, нужен ли вашему бизнесу бот и какой сценарий подойдёт лучше всего. "
        "Заполните короткую анкету, и я передам готовую заявку на разбор."
    )

    if settings.cover_file_id:
        try:
            await message.answer_photo(
                photo=settings.cover_file_id,
                caption=text,
                reply_markup=main_menu(),
            )
            return
        except TelegramBadRequest:
            pass

    await message.answer(text, reply_markup=main_menu())


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await send_welcome(message)


@router.callback_query(F.data == "start_form")
async def start_form(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(LeadForm.name)
    await callback.message.answer(
        "Отлично. Давайте начнём.\n\nКак вас зовут?",
        reply_markup=cancel_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "cancel_form")
async def cancel_form(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.answer("Заявка отменена")
    await callback.message.answer("Можно начать заново в любой момент", reply_markup=main_menu())
    await callback.answer()


async def ask_next_question(message: Message, state: FSMContext, current_key: str) -> None:
    keys = [key for key, _ in QUESTIONS]
    try:
        current_index = keys.index(current_key)
    except ValueError:
        await state.clear()
        await message.answer("Произошла ошибка. Нажмите /start и начните заново")
        return

    next_index = current_index + 1
    if next_index >= len(QUESTIONS):
        await finish_form(message, state)
        return

    next_key, next_question = QUESTIONS[next_index]
    await state.set_state(getattr(LeadForm, next_key))
    await message.answer(next_question, reply_markup=cancel_keyboard())


async def finish_form(message: Message, state: FSMContext) -> None:
    data = await state.get_data()

    user = message.from_user
    username = f"@{user.username}" if user and user.username else "нет"
    full_name = " ".join(part for part in [user.first_name if user else None, user.last_name if user else None] if part) or "нет"

    text = (
        "<b>Новая заявка B2Bots Helper</b>\n\n"
        f"<b>Имя из анкеты:</b> {escape(data.get('name', '-'))}\n"
        f"<b>Бизнес / проект:</b> {escape(data.get('business_name', '-'))}\n"
        f"<b>Ниша:</b> {escape(data.get('niche', '-'))}\n"
        f"<b>Город / регион:</b> {escape(data.get('city', '-'))}\n"
        f"<b>Как сейчас принимают заявки:</b> {escape(data.get('current_process', '-'))}\n"
        f"<b>Объём заявок:</b> {escape(data.get('lead_volume', '-'))}\n"
        f"<b>Источники клиентов:</b> {escape(data.get('lead_sources', '-'))}\n"
        f"<b>Главная задача:</b> {escape(data.get('main_goal', '-'))}\n"
        f"<b>Бюджет:</b> {escape(data.get('budget', '-'))}\n"
        f"<b>Срок запуска:</b> {escape(data.get('timeline', '-'))}\n"
        f"<b>Кто принимает решение:</b> {escape(data.get('decision_maker', '-'))}\n"
        f"<b>Контакт:</b> {escape(data.get('contact', '-'))}\n"
        f"<b>Дополнительно:</b> {escape(data.get('extra', '-'))}\n\n"
        f"<b>Telegram user id:</b> {user.id if user else '-'}\n"
        f"<b>Username:</b> {escape(username)}\n"
        f"<b>Имя профиля:</b> {escape(full_name)}"
    )

    bot: Bot = message.bot
    await bot.send_message(chat_id=settings.owner_chat_id, text=text)

    await state.clear()
    await message.answer(
        "Спасибо. Заявка отправлена. Я свяжусь с вами после просмотра деталей",
        reply_markup=main_menu(),
    )


for field_name, _question in QUESTIONS:
    @router.message(getattr(LeadForm, field_name))
    async def _capture_answer(message: Message, state: FSMContext, field_name: str = field_name) -> None:
        if not message.text:
            await message.answer("Пожалуйста, отправьте ответ текстом")
            return
        await state.update_data(**{field_name: message.text.strip()})
        await ask_next_question(message, state, field_name)


async def build_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.include_router(router)
    return dp
