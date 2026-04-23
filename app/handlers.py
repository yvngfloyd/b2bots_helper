from __future__ import annotations

from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.config import settings
from app.keyboards import (
    bot_types,
    budgets,
    contact_methods,
    current_problems,
    final_business_types,
    final_links_keyboard,
    integration_needs,
    launch_times,
    lead_sources,
    main_goals,
    make_choice_keyboard,
    needs_help_options,
    requests_volumes,
    website_options,
    weak_bot_options,
)
from app.states import LeadForm

router = Router()

QUESTIONS: list[dict[str, Any]] = [
    {
        "state": LeadForm.business_type,
        "key": "business_type",
        "question": "1/12. Чем вы занимаетесь?",
        "options": final_business_types,
        "prefix": "business_type",
    },
    {
        "state": LeadForm.lead_source,
        "key": "lead_source",
        "question": "2/12. Откуда вам чаще всего пишут клиенты?",
        "options": lead_sources,
        "prefix": "lead_source",
    },
    {
        "state": LeadForm.current_problem,
        "key": "current_problem",
        "question": "3/12. Что сейчас происходит с заявками?",
        "options": current_problems,
        "prefix": "current_problem",
    },
    {
        "state": LeadForm.main_goal,
        "key": "main_goal",
        "question": "4/12. Что вам важнее всего?",
        "options": main_goals,
        "prefix": "main_goal",
    },
    {
        "state": LeadForm.bot_type,
        "key": "bot_type",
        "question": "5/12. Какой бот вам ближе?",
        "options": bot_types,
        "prefix": "bot_type",
    },
    {
        "state": LeadForm.requests_volume,
        "key": "requests_volume",
        "question": "6/12. Сколько у вас примерно обращений?",
        "options": requests_volumes,
        "prefix": "requests_volume",
    },
    {
        "state": LeadForm.has_website,
        "key": "has_website",
        "question": "7/12. Есть ли у вас сайт?",
        "options": website_options,
        "prefix": "has_website",
    },
    {
        "state": LeadForm.integration_need,
        "key": "integration_need",
        "question": "8/12. Нужна ли интеграция с менеджером или CRM?",
        "options": integration_needs,
        "prefix": "integration_need",
    },
    {
        "state": LeadForm.launch_time,
        "key": "launch_time",
        "question": "9/12. Когда хотите запустить?",
        "options": launch_times,
        "prefix": "launch_time",
    },
    {
        "state": LeadForm.budget,
        "key": "budget",
        "question": "10/12. Какой бюджет рассматриваете?",
        "options": budgets,
        "prefix": "budget",
    },
]

STATE_ORDER = [item["state"] for item in QUESTIONS] + [LeadForm.task_description, LeadForm.contact_method, LeadForm.manual_contact]

FIELD_TITLES = {
    "business_type": "Ниша",
    "lead_source": "Источник заявок",
    "current_problem": "Текущая ситуация",
    "main_goal": "Главная задача",
    "bot_type": "Какой бот нужен",
    "requests_volume": "Объем обращений",
    "has_website": "Наличие сайта",
    "integration_need": "Интеграция / CRM",
    "launch_time": "Срок запуска",
    "budget": "Бюджет",
    "task_description": "Что должен делать бот",
    "contact": "Контакт",
}


async def show_start(message: Message) -> None:
    text = (
        "<b>B2Bots Helper</b>\n\n"
        "Помогу быстро оставить заявку на разработку бота для бизнеса\n\n"
        "Нажмите кнопку ниже и ответьте на несколько коротких вопросов"
    )

    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    builder.button(text="Оставить заявку", callback_data="form:start")
    builder.adjust(1)

    if settings.cover_file_id:
        await message.answer_photo(photo=settings.cover_file_id, caption=text, reply_markup=builder.as_markup())
    else:
        await message.answer(text, reply_markup=builder.as_markup())


@router.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await show_start(message)


@router.callback_query(F.data == "form:start")
@router.callback_query(F.data == "form:restart")
async def start_form(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.update_data(history=[])
    await ask_question(callback.message, state, 0, edit=True)
    await callback.answer()


async def ask_question(message: Message, state: FSMContext, index: int, edit: bool = False) -> None:
    item = QUESTIONS[index]
    await state.set_state(item["state"])

    data = await state.get_data()
    history = data.get("history", [])
    if not history or history[-1] != index:
        history.append(index)
        await state.update_data(history=history)

    text = item["question"]
    markup = make_choice_keyboard(item["prefix"], item["options"], back=index > 0)

    if edit:
        await message.edit_text(text, reply_markup=markup)
    else:
        await message.answer(text, reply_markup=markup)


def find_question_by_prefix(prefix: str) -> dict[str, Any] | None:
    for item in QUESTIONS:
        if item["prefix"] == prefix:
            return item
    return None


@router.callback_query(F.data.startswith("nav:back"))
async def go_back(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    history = data.get("history", [])

    current_state = await state.get_state()
    if current_state == LeadForm.task_description.state:
        await ask_question(callback.message, state, len(QUESTIONS) - 1, edit=True)
        await callback.answer()
        return

    if current_state == LeadForm.contact_method.state:
        await state.set_state(LeadForm.task_description)
        await callback.message.edit_text("11/12. Коротко опишите, что бот должен делать")
        await callback.answer()
        return

    if current_state == LeadForm.manual_contact.state:
        await state.set_state(LeadForm.contact_method)
        await callback.message.edit_text(
            "12/12. Как удобно с вами связаться?",
            reply_markup=make_choice_keyboard("contact_method", contact_methods, back=True),
        )
        await callback.answer()
        return

    if len(history) >= 2:
        history.pop()
        previous_index = history.pop()
        await state.update_data(history=history)
        await ask_question(callback.message, state, previous_index, edit=True)
    await callback.answer()


@router.callback_query(F.data.startswith(("business_type:", "lead_source:", "current_problem:", "main_goal:", "bot_type:", "requests_volume:", "has_website:", "integration_need:", "launch_time:", "budget:")))
async def process_choice(callback: CallbackQuery, state: FSMContext) -> None:
    prefix, raw_index = callback.data.split(":", 1)
    item = find_question_by_prefix(prefix)
    if item is None:
        await callback.answer()
        return

    option_index = int(raw_index) - 1
    answer = item["options"][option_index]
    await state.update_data(**{item["key"]: answer})

    current_index = next(i for i, q in enumerate(QUESTIONS) if q["prefix"] == prefix)

    if current_index < len(QUESTIONS) - 1:
        await ask_question(callback.message, state, current_index + 1, edit=True)
    else:
        await state.set_state(LeadForm.task_description)
        await callback.message.edit_text("11/12. Коротко опишите, что бот должен делать")

    await callback.answer()


@router.message(LeadForm.task_description)
async def process_task_description(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if len(text) < 5:
        await message.answer("Пожалуйста, напишите чуть подробнее, хотя бы в 5 символов")
        return

    await state.update_data(task_description=text)
    await state.set_state(LeadForm.contact_method)
    await message.answer(
        "12/12. Как удобно с вами связаться?",
        reply_markup=make_choice_keyboard("contact_method", contact_methods, back=True),
    )


@router.callback_query(F.data.startswith("contact_method:"))
async def process_contact_method(callback: CallbackQuery, state: FSMContext) -> None:
    _, raw_index = callback.data.split(":", 1)
    answer = contact_methods[int(raw_index) - 1]

    if answer == "Подставить мой username":
        username = callback.from_user.username
        contact = f"@{username}" if username else "Username не указан"
        await finalize_application(callback.message, state, contact)
        await callback.answer()
        return

    if answer == "Написать телефон вручную":
        await state.set_state(LeadForm.manual_contact)
        await callback.message.edit_text("Напишите ваш телефон одним сообщением")
        await callback.answer()
        return

    await state.set_state(LeadForm.manual_contact)
    await callback.message.edit_text("Напишите ваш username, Telegram-ссылку или другой удобный контакт одним сообщением")
    await callback.answer()


@router.message(LeadForm.manual_contact)
async def process_manual_contact(message: Message, state: FSMContext) -> None:
    contact = (message.text or "").strip()
    if len(contact) < 3:
        await message.answer("Напишите корректный контакт")
        return

    await finalize_application(message, state, contact)


async def finalize_application(message: Message, state: FSMContext, contact: str) -> None:
    await state.update_data(contact=contact)
    data = await state.get_data()

    username = f"@{message.from_user.username}" if message.from_user and message.from_user.username else "не указан"
    full_name = message.from_user.full_name if message.from_user else "не указано"
    user_id = message.from_user.id if message.from_user else 0

    lead_text = (
        "<b>Новая заявка B2Bots Helper</b>\n\n"
        f"<b>Имя в Telegram:</b> {full_name}\n"
        f"<b>Username:</b> {username}\n"
        f"<b>User ID:</b> <code>{user_id}</code>\n\n"
        f"<b>{FIELD_TITLES['business_type']}:</b> {data.get('business_type', '-')}\n"
        f"<b>{FIELD_TITLES['lead_source']}:</b> {data.get('lead_source', '-')}\n"
        f"<b>{FIELD_TITLES['current_problem']}:</b> {data.get('current_problem', '-')}\n"
        f"<b>{FIELD_TITLES['main_goal']}:</b> {data.get('main_goal', '-')}\n"
        f"<b>{FIELD_TITLES['bot_type']}:</b> {data.get('bot_type', '-')}\n"
        f"<b>{FIELD_TITLES['requests_volume']}:</b> {data.get('requests_volume', '-')}\n"
        f"<b>{FIELD_TITLES['has_website']}:</b> {data.get('has_website', '-')}\n"
        f"<b>{FIELD_TITLES['integration_need']}:</b> {data.get('integration_need', '-')}\n"
        f"<b>{FIELD_TITLES['launch_time']}:</b> {data.get('launch_time', '-')}\n"
        f"<b>{FIELD_TITLES['budget']}:</b> {data.get('budget', '-')}\n\n"
        f"<b>{FIELD_TITLES['task_description']}:</b>\n{data.get('task_description', '-')}\n\n"
        f"<b>{FIELD_TITLES['contact']}:</b> {contact}"
    )

    await message.bot.send_message(settings.owner_chat_id, lead_text)
    await state.clear()

    thanks_text = (
        "<b>Спасибо, заявка отправлена</b>\n\n"
        "Я уже получил ваши ответы. Ниже можете перейти на сайт или в Telegram-канал"
    )
    await message.answer(
        thanks_text,
        reply_markup=final_links_keyboard(settings.site_url, settings.tg_channel_url),
    )


@router.message()
async def fallback_message(message: Message, state: FSMContext) -> None:
    current_state = await state.get_state()

    if current_state in {item["state"].state for item in QUESTIONS}:
        await message.answer("Здесь лучше выбрать вариант кнопкой ниже")
        return

    if current_state is None:
        await show_start(message)
        return

    await message.answer("Используйте кнопки или завершите текущий шаг")
