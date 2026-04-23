from aiogram.fsm.state import State, StatesGroup


class LeadForm(StatesGroup):
    name = State()
    business_name = State()
    niche = State()
    city = State()
    current_process = State()
    lead_volume = State()
    lead_sources = State()
    main_goal = State()
    budget = State()
    timeline = State()
    decision_maker = State()
    contact = State()
    extra = State()
