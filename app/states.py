from aiogram.fsm.state import State, StatesGroup


class LeadForm(StatesGroup):
    name = State()
    business = State()
    niche = State()
    city = State()
    current_flow = State()
    monthly_leads = State()
    platforms = State()
    goal = State()
    budget = State()
    timing = State()
    decision_maker = State()
    contact = State()
    extra = State()
