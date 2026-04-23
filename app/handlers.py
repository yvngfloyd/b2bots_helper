from __future__ import annotations

from html import escape

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from app.config import Settings
from app.keyboards import main_menu, restart_keyboard
from app.states import LeadForm


router = Router()


QUESTION_TEXT = {
    LeadForm.name: 'Как вас зовут?',
    LeadForm.business: 'Как называется ваш бизнес или проект?',
    LeadForm.niche: 'Какая у вас ниша?',
    LeadForm.city: 'Из какого вы города или региона?',
    LeadForm.current_flow: 'Как вы сейчас принимаете заявки и сообщения?',
    LeadForm.monthly_leads: 'Сколько примерно обращений или заявок у вас в месяц?',
    LeadForm.platforms: 'Откуда приходят клиенты? Например: Telegram, WhatsApp, сайт, Instagram, Avito и так далее',
    LeadForm.goal: 'Что вам сейчас нужно больше всего? Например: не терять лиды, отвечать быстрее, квалифицировать заявки, разгрузить менеджера',
    LeadForm.budget: 'Какой бюджет вы готовы рассматривать на внедрение бота?',
    LeadForm.timing: 'Когда хотите запуск? Например: срочно, в течение недели, месяца, позже',
    LeadForm.decision_maker: 'Вы сами принимаете решение по запуску или есть ещё согласование?',
    LeadForm.contact: 'Оставьте удобный контакт для связи. Например: @username, телефон, WhatsApp, Telegram',
    LeadForm.extra: 'Есть ли дополнительные детали, пожелания или задачи для бота?',
}


STATE_ORDER = [
    LeadForm.name,
    LeadForm.business,
    LeadForm.niche,
    LeadForm.city,
    LeadForm.current_flow,
    LeadForm.monthly_leads,
    LeadForm.platforms,
    LeadForm.goal,
    LeadForm.budget,
    LeadForm.timing,
    LeadForm.decision_maker,
    LeadForm.contact,
    LeadForm.extra,
]


FIELD_LABELS = {
    'name': 'Имя',
    'business': 'Бизнес / проект',
    'niche': 'Ниша',
    'city': 'Город / регион',
    'current_flow': 'Как сейчас принимаются заявки',
    'monthly_leads': 'Обращений в месяц',
    'platforms': 'Источники обращений',
    'goal': 'Главная задача',
    'budget': 'Бюджет',
    'timing': 'Срок запуска',
    'decision_maker': 'Кто принимает решение',
    'contact': 'Контакт для связи',
    'extra': 'Дополнительно',
}


async def send_welcome(message: Message, settings: Settings) -> None:
    text = (
        f'<b>{escape(settings.bot_title)}</b>\n\n'
        'Этот бот помогает быстро оставить заявку на внедрение бота для бизнеса.\n\n'
        'Я задам несколько коротких вопросов, чтобы понять, нужен ли вам бот, как он может помочь и что именно стоит предложить. '
        'После этого заявка уйдёт менеджеру в готовом виде.'
    )

    if settings.cover_file_id:
        await message.answer_photo(
            photo=settings.cover_file_id,
            caption=text,
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu(settings.site_url, settings.tg_channel_url),
        )
    else:
        await message.answer(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu(settings.site_url, settings.tg_channel_url),
            disable_web_page_preview=True,
        )


async def start_form_flow(target: Message | CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(LeadForm.name)

    text = (
        'Отлично, начинаем\n\n'
        'Ответьте в одном сообщении на каждый вопрос. '
        'Если какой-то пункт неактуален, напишите "нет" или "не знаю".'
    )

    if isinstance(target, CallbackQuery):
        await target.message.answer(text, reply_markup=ReplyKeyboardRemove())
        await target.message.answer(QUESTION_TEXT[LeadForm.name])
        await target.answer()
    else:
        await target.answer(text, reply_markup=ReplyKeyboardRemove())
        await target.answer(QUESTION_TEXT[LeadForm.name])


@router.message(CommandStart())
async def cmd_start(message: Message, settings: Settings, state: FSMContext) -> None:
    await state.clear()
    await send_welcome(message, settings)


@router.message(Command('menu'))
async def cmd_menu(message: Message, settings: Settings, state: FSMContext) -> None:
    await state.clear()
    await send_welcome(message, settings)


@router.message(Command('cancel'))
async def cmd_cancel(message: Message, state: FSMContext, settings: Settings) -> None:
    await state.clear()
    await message.answer('Заявка отменена', reply_markup=ReplyKeyboardRemove())
    await send_welcome(message, settings)


@router.callback_query(F.data == 'start_form')
async def callback_start_form(callback: CallbackQuery, state: FSMContext) -> None:
    await start_form_flow(callback, state)


@router.message(F.text.casefold() == 'оставить заявку')
async def text_start_form(message: Message, state: FSMContext) -> None:
    await start_form_flow(message, state)


@router.message(LeadForm.name)
async def process_name(message: Message, state: FSMContext) -> None:
    await save_and_next(message, state, 'name', LeadForm.business)


@router.message(LeadForm.business)
async def process_business(message: Message, state: FSMContext) -> None:
    await save_and_next(message, state, 'business', LeadForm.niche)


@router.message(LeadForm.niche)
async def process_niche(message: Message, state: FSMContext) -> None:
    await save_and_next(message, state, 'niche', LeadForm.city)


@router.message(LeadForm.city)
async def process_city(message: Message, state: FSMContext) -> None:
    await save_and_next(message, state, 'city', LeadForm.current_flow)


@router.message(LeadForm.current_flow)
async def process_flow(message: Message, state: FSMContext) -> None:
    await save_and_next(message, state, 'current_flow', LeadForm.monthly_leads)


@router.message(LeadForm.monthly_leads)
async def process_leads(message: Message, state: FSMContext) -> None:
    await save_and_next(message, state, 'monthly_leads', LeadForm.platforms)


@router.message(LeadForm.platforms)
async def process_platforms(message: Message, state: FSMContext) -> None:
    await save_and_next(message, state, 'platforms', LeadForm.goal)


@router.message(LeadForm.goal)
async def process_goal(message: Message, state: FSMContext) -> None:
    await save_and_next(message, state, 'goal', LeadForm.budget)


@router.message(LeadForm.budget)
async def process_budget(message: Message, state: FSMContext) -> None:
    await save_and_next(message, state, 'budget', LeadForm.timing)


@router.message(LeadForm.timing)
async def process_timing(message: Message, state: FSMContext) -> None:
    await save_and_next(message, state, 'timing', LeadForm.decision_maker)


@router.message(LeadForm.decision_maker)
async def process_decision_maker(message: Message, state: FSMContext) -> None:
    await save_and_next(message, state, 'decision_maker', LeadForm.contact)


@router.message(LeadForm.contact)
async def process_contact(message: Message, state: FSMContext) -> None:
    await save_and_next(message, state, 'contact', LeadForm.extra)


@router.message(LeadForm.extra)
async def process_extra(message: Message, state: FSMContext, settings: Settings) -> None:
    await state.update_data(extra=message.text.strip())
    data = await state.get_data()
    await state.clear()

    lead_text = build_lead_message(message, data, settings)

    await message.bot.send_message(
        chat_id=settings.owner_chat_id,
        text=lead_text,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )

    await message.answer(
        'Готово. Заявка отправлена. Скоро с вами свяжутся',
        reply_markup=ReplyKeyboardRemove(),
    )
    await message.answer(
        'Пока ждёте, можете посмотреть сайт или Telegram-канал',
        reply_markup=main_menu(settings.site_url, settings.tg_channel_url),
    )


async def save_and_next(message: Message, state: FSMContext, field_name: str, next_state) -> None:
    value = (message.text or '').strip()
    await state.update_data(**{field_name: value})
    await state.set_state(next_state)
    await message.answer(QUESTION_TEXT[next_state])



def build_lead_message(message: Message, data: dict, settings: Settings) -> str:
    user = message.from_user
    username = f'@{user.username}' if user and user.username else 'не указан'
    full_name = ' '.join(filter(None, [user.first_name if user else '', user.last_name if user else ''])).strip() or 'не указано'

    lines = [
        f'<b>Новая заявка в {escape(settings.bot_title)}</b>',
        '',
        '<b>Данные пользователя.</b>',
        f'Telegram ID: <code>{user.id if user else "unknown"}</code>',
        f'Username: {escape(username)}',
        f'Имя в Telegram: {escape(full_name)}',
        '',
        '<b>Ответы по анкете.</b>',
    ]

    for key, label in FIELD_LABELS.items():
        value = escape(str(data.get(key, 'не указано')))
        lines.append(f'<b>{escape(label)}:</b> {value}')

    if user:
        deep_link = f'tg://user?id={user.id}'
        lines.extend(['', f'<a href="{deep_link}">Открыть профиль в Telegram</a>'])

    return '\n'.join(lines)
