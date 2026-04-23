from aiogram.fsm.state import State, StatesGroup


class LeadForm(StatesGroup):
    business_type = State()
    lead_source = State()
    current_problem = State()
    main_goal = State()
    bot_type = State()
    requests_volume = State()
    has_website = State()
    integration_need = State()
    launch_time = State()
    budget = State()
    task_description = State()
    contact_method = State()
    manual_contact = State()
