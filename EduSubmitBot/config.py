import os
from dotenv import load_dotenv

# Load .env from current directory
load_dotenv()

class Config:
    def __init__(self):
        self.bot_token = os.getenv('BOT_TOKEN')
        self.db_url = os.getenv('DATABASE_URL', 'sqlite+aiosqlite:///./database.db')
        admin_ids_str = os.getenv('ADMIN_IDS', '')
        self.admin_ids = [int(x.strip()) for x in admin_ids_str.split(',') if x.strip().isdigit()]
        self.timezone = os.getenv('TIMEZONE', 'UTC')
        self.max_file_size = int(os.getenv('MAX_FILE_SIZE_MB', '50')) * 1024 * 1024  # bytes
        self.storage_path = os.getenv('STORAGE_PATH', './storage')

def load_config():
    return Config()