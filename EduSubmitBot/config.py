import os
from dotenv import load_dotenv

# Load .env from current directory
load_dotenv()

class Config:
    def __init__(self):
        self.bot_token = os.getenv('BOT_TOKEN')
        if not self.bot_token:
            raise ValueError("BOT_TOKEN is required in environment variables")

        self.db_url = os.getenv('DATABASE_URL', 'sqlite+aiosqlite:///./database.db')
        admin_ids_str = os.getenv('ADMIN_IDS', '')
        self.admin_ids = [int(x.strip()) for x in admin_ids_str.split(',') if x.strip().isdigit()]
        if not self.admin_ids:
            raise ValueError("ADMIN_IDS is required and must contain at least one valid Telegram ID")

        self.timezone = os.getenv('TIMEZONE', 'UTC')
        try:
            self.max_file_size = int(os.getenv('MAX_FILE_SIZE_MB', '50')) * 1024 * 1024  # bytes
        except ValueError:
            raise ValueError("MAX_FILE_SIZE_MB must be an integer")
        self.storage_path = os.getenv('STORAGE_PATH', './storage')

def load_config():
    return Config()