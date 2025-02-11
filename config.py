from dataclasses import dataclass
from os import getenv
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Config:
    BOT_TOKEN: str = getenv('BOT_TOKEN')
    GROUP_CHAT_ID: int = int(getenv('GROUP_CHAT_ID'))
    ADMIN_ID: int = int(getenv('ADMIN_ID'))

config = Config() 