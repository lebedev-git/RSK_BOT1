from aiogram.fsm.state import State, StatesGroup

class AttendanceStates(StatesGroup):
    marking_attendance = State()
    
class TeamManagement(StatesGroup):
    creating_team = State()
    adding_members = State()
    removing_members = State() 