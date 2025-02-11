import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID")
    
config = Config() 