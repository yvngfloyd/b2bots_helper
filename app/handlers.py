from __future__ import annotations

import logging
from html import escape
from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, User

from app.config import settings
from app.keyboards import (
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
    subscription_required_keyboard,
)
from app.states import LeadForm
from app.storage import get_form_snapshot, mark_completed, save_form_snapshot, upsert_started_user
from app.subscription import is_user_subscribed, resolve_subscription_chat_id

router = Router()
logger = logging.getLogger(__name__)

QUESTIONS: list[dict[str, Any]] = [
    {
        "state": LeadForm.business_type,
        "key": "business_type",
        "question": "1/9. Чем вы занимаетесь?",
        "options": final_business_types,
        "prefix": "business_type",
    },
    {
        "state": LeadForm.lead_source,
        "key": "lead_source",
        "question": "2/9. Откуда вам чаще всего пишут клиенты?",
        "options": lead_sources,
        "prefix": "lead_source",
    },
    {
        "state": LeadForm.current_problem,
        "key": "current_problem",
        "question": "3/9. Что сейчас происходит с заявками?",
        "options": current_problems,
        "prefix": "current_problem",
    },
    {
        "state": LeadForm.main_goal,
        "key": "main_goal",
        "question": "4/9. Что вам важнее всего?",
        "options": main_goals,
        "prefix": "main_goal",
    },
    {
        "state": LeadForm.integration_need,
        "key": "integration_need",
        "question": "5/9. Нужна ли интеграция с менеджером или CRM?",
        "options": integration_needs,
        "prefix": "integration_need",
    },
    {
        "state": LeadForm.launch_time,
        "key": "launch_time",
        "question": "6/9. Когда хотите запустить?",
        "options": launch_times,
        "prefix": "launch_time",
    },
    {
        "state": LeadForm.budget,
        "key": "budget",
        "question": "7/9. Какой бюджет рассматриваете?",
        "options": budgets,
        "prefix": "budget",
    },
]

FIELD_TITLES = {
    "business_type": "Ниша",
    "lead_source": "Источник заявок",
    "current_problem": "Текущая ситуация",
    "main_goal": "Главная задача",
    "integration_need": "Интеграция / CRM",
    "launch_time": "Срок запуска",
    "budget": "Бюджет",
    "task_description": "Что должен делать бот",
    "contact": "Контакт",
}


async def show_start(message: Message) -> None:
    text = (
        "<b>Бесплатная консультация B2Bots</b>\n\n"
        "Хотите получить бесплатную консультацию, чтобы понять, какой бот или автоматизация вам нужна?\n\n"
        "Нажмите кнопку ниже, подпишитесь на канал и ответьте на несколько коротких вопросов"
    )

    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    builder.button(text="Пройти консультацию", callback_data="form:start")
    builder.adjust(1)

    if settings.cover_file_id:
        await message.answer_photo(
            photo=settings.cover_file_id,
            caption=text,
            reply_markup=builder.as_markup(),
        )
    else:
        await message.answer(text, reply_markup=builder.as_markup())


@router.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    if message.from_user:
        upsert_started_user(
            settings.database_path,
            message.from_user.id,
            message.from_user.full_name,
            message.from_user.username,
        )
        await notify_owner_about_start(message, message.from_user)
    await show_start(message)


@router.callback_query(F.data == "form:start")
@router.callback_query(F.data == "form:restart")
async def start_form(callback: CallbackQuery, state: FSMContext) -> None:
    if not await ensure_subscription(callback, "start"):
        return
    await begin_form(callback, state)
    await callback.answer()


@router.callback_query(F.data == "subscription:check:start")
async def check_subscription_for_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not await ensure_subscription(callback, "start"):
        return
    await begin_form(callback, state)
    await callback.answer("Подписка подтверждена")


@router.callback_query(F.data == "subscription:check:continue")
async def check_subscription_for_continue(callback: CallbackQuery, state: FSMContext) -> None:
    if not await ensure_subscription(callback, "continue"):
        return
    resumed = await resume_saved_form(callback, state)
    await callback.answer("Подписка подтверждена" if resumed else "Начнем заявку заново")


async def begin_form(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.update_data(history=[])
    await ask_question(
        callback.message,
        state,
        0,
        edit=_can_edit_text(callback.message),
        user_id=callback.from_user.id,
    )

@router.callback_query(F.data == "reminder:continue")
async def continue_form(callback: CallbackQuery, state: FSMContext) -> None:
    if not await ensure_subscription(callback, "continue"):
        return
    resumed = await resume_saved_form(callback, state)
    if resumed:
        await callback.answer()
    else:
        await callback.answer("Начнем заявку заново")


async def resume_saved_form(callback: CallbackQuery, state: FSMContext) -> bool:
    snapshot = get_form_snapshot(settings.database_path, callback.from_user.id)
    if snapshot is None:
        await state.clear()
        await state.update_data(history=[])
        await ask_question(callback.message, state, 0, user_id=callback.from_user.id)
        return False

    await state.set_data(snapshot.form_data)
    await show_saved_step(callback.message, state, snapshot.current_step, callback.from_user.id)
    return True


async def ensure_subscription(callback: CallbackQuery, next_action: str) -> bool:
    chat_id = resolve_subscription_chat_id(settings.subscription_channel_id, settings.tg_channel_url)
    if chat_id is None:
        logger.error(
            "Subscription gate is enabled, but SUBSCRIPTION_CHANNEL_ID cannot be resolved from TG_CHANNEL_URL=%s",
            settings.tg_channel_url,
        )
        if callback.message:
            await callback.message.answer(
                "Пока не получается проверить подписку на канал. Напишите нам в канал, и мы поможем продолжить.",
                reply_markup=subscription_required_keyboard(settings.tg_channel_url, f"subscription:check:{next_action}"),
            )
        await callback.answer("Проверка подписки не настроена")
        return False

    if await is_user_subscribed(callback.bot, callback.from_user.id, chat_id):
        return True

    if callback.message:
        await callback.message.answer(
            (
                "<b>Перед консультацией подпишитесь на канал B2Bots</b>\n\n"
                "Там показываем примеры автоматизаций и сценарии, которые помогают не терять заявки.\n\n"
                "После подписки нажмите «Проверить подписку», и бот сразу продолжит анкету."
            ),
            reply_markup=subscription_required_keyboard(settings.tg_channel_url, f"subscription:check:{next_action}"),
        )
    await callback.answer("Сначала подпишитесь на канал")
    return False


async def ask_question(
    message: Message,
    state: FSMContext,
    index: int,
    edit: bool = False,
    user_id: int | None = None,
) -> None:
    item = QUESTIONS[index]
    await state.set_state(item["state"])

    data = await state.get_data()
    history = data.get("history", [])
    if not history or history[-1] != index:
        history.append(index)
        await state.update_data(history=history)

    await save_current_form_snapshot(message, state, item["prefix"], user_id=user_id)

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


@router.callback_query(F.data == "nav:back")
async def go_back(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    history = data.get("history", [])

    current_state = await state.get_state()
    if current_state == LeadForm.task_description.state:
        await ask_question(
            callback.message,
            state,
            len(QUESTIONS) - 1,
            edit=_can_edit_text(callback.message),
            user_id=callback.from_user.id,
        )
        await callback.answer()
        return

    if current_state == LeadForm.contact_method.state:
        await state.set_state(LeadForm.task_description)
        await save_current_form_snapshot(
            callback.message,
            state,
            "task_description",
            user_id=callback.from_user.id,
        )
        await callback.message.edit_text("8/9. Коротко опишите, что бот должен делать")
        await callback.answer()
        return

    if current_state == LeadForm.manual_contact.state:
        await state.set_state(LeadForm.contact_method)
        await save_current_form_snapshot(
            callback.message,
            state,
            "contact_method",
            user_id=callback.from_user.id,
        )
        await callback.message.edit_text(
            "9/9. Как удобно с вами связаться?",
            reply_markup=make_choice_keyboard("contact_method", contact_methods, back=True),
        )
        await callback.answer()
        return

    if len(history) >= 2:
        history.pop()
        previous_index = history.pop()
        await state.update_data(history=history)
        await ask_question(
            callback.message,
            state,
            previous_index,
            edit=_can_edit_text(callback.message),
            user_id=callback.from_user.id,
        )

    await callback.answer()


@router.callback_query(
    F.data.startswith(
        (
            "business_type:",
            "lead_source:",
            "current_problem:",
            "main_goal:",
            "integration_need:",
            "launch_time:",
            "budget:",
        )
    )
)
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
        await ask_question(
            callback.message,
            state,
            current_index + 1,
            edit=_can_edit_text(callback.message),
            user_id=callback.from_user.id,
        )
    else:
        await state.set_state(LeadForm.task_description)
        await save_current_form_snapshot(
            callback.message,
            state,
            "task_description",
            user_id=callback.from_user.id,
        )
        await callback.message.edit_text("8/9. Коротко опишите, что бот должен делать")

    await callback.answer()


@router.message(LeadForm.task_description)
async def process_task_description(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if len(text) < 5:
        await message.answer("Пожалуйста, напишите чуть подробнее, хотя бы в 5 символов")
        return

    await state.update_data(task_description=text)
    await state.set_state(LeadForm.contact_method)
    await save_current_form_snapshot(message, state, "contact_method")
    await message.answer(
        "9/9. Как удобно с вами связаться?",
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
        await save_current_form_snapshot(
            callback.message,
            state,
            "manual_contact",
            user_id=callback.from_user.id,
        )
        await callback.message.edit_text("Напишите ваш телефон одним сообщением")
        await callback.answer()
        return

    await state.set_state(LeadForm.manual_contact)
    await save_current_form_snapshot(
        callback.message,
        state,
        "manual_contact",
        user_id=callback.from_user.id,
    )
    await callback.message.edit_text(
        "Напишите ваш username, Telegram-ссылку или другой удобный контакт одним сообщением"
    )
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
        f"<b>{FIELD_TITLES['integration_need']}:</b> {data.get('integration_need', '-')}\n"
        f"<b>{FIELD_TITLES['launch_time']}:</b> {data.get('launch_time', '-')}\n"
        f"<b>{FIELD_TITLES['budget']}:</b> {data.get('budget', '-')}\n\n"
        f"<b>{FIELD_TITLES['task_description']}:</b>\n{data.get('task_description', '-')}\n\n"
        f"<b>{FIELD_TITLES['contact']}:</b> {contact}"
    )

    await message.bot.send_message(settings.owner_chat_id, lead_text)
    if message.from_user:
        mark_completed(settings.database_path, message.from_user.id)
    await state.clear()

    thanks_text = (
        "<b>Спасибо, заявка отправлена!</b>\n\n"
        "В скором времени свяжемся с вами"
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


async def notify_owner_about_start(message: Message, user: User) -> None:
    username = f"@{user.username}" if user.username else "не указан"
    text = (
        "<b>Пользователь нажал /start</b>\n\n"
        f"<b>Имя в Telegram:</b> {escape(user.full_name)}\n"
        f"<b>Username:</b> {escape(username)}\n"
        f"<b>User ID:</b> <code>{user.id}</code>"
    )
    try:
        await message.bot.send_message(settings.owner_chat_id, text)
    except Exception:
        logger.exception("Failed to notify owner about /start from user_id=%s", user.id)


async def show_saved_step(message: Message, state: FSMContext, current_step: str, user_id: int) -> None:
    question_index = find_question_index_by_prefix(current_step)
    if question_index is not None:
        await ask_question(message, state, question_index, user_id=user_id)
        return

    if current_step == "task_description":
        await state.set_state(LeadForm.task_description)
        await save_current_form_snapshot(message, state, "task_description", user_id=user_id)
        await message.answer("8/9. Коротко опишите, что бот должен делать")
        return

    if current_step == "contact_method":
        await state.set_state(LeadForm.contact_method)
        await save_current_form_snapshot(message, state, "contact_method", user_id=user_id)
        await message.answer(
            "9/9. Как удобно с вами связаться?",
            reply_markup=make_choice_keyboard("contact_method", contact_methods, back=True),
        )
        return

    if current_step == "manual_contact":
        await state.set_state(LeadForm.manual_contact)
        await save_current_form_snapshot(message, state, "manual_contact", user_id=user_id)
        await message.answer("Напишите ваш username, Telegram-ссылку или другой удобный контакт одним сообщением")
        return

    await state.clear()
    await state.update_data(history=[])
    await ask_question(message, state, 0, user_id=user_id)


async def save_current_form_snapshot(
    message: Message,
    state: FSMContext,
    current_step: str,
    *,
    user_id: int | None = None,
) -> None:
    resolved_user_id = user_id
    if resolved_user_id is None and message.from_user:
        resolved_user_id = message.from_user.id
    if resolved_user_id is None:
        return

    save_form_snapshot(
        settings.database_path,
        resolved_user_id,
        current_step=current_step,
        form_data=await state.get_data(),
    )


def find_question_index_by_prefix(prefix: str) -> int | None:
    for index, item in enumerate(QUESTIONS):
        if item["prefix"] == prefix:
            return index
    return None


def _can_edit_text(message: Message | None) -> bool:
    return bool(message and not message.photo)
