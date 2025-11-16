import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Config:
    # Bot
    BOT_TOKEN: str = os.getenv("BOT_TOKEN")
    ADMIN_ID: int = int(os.getenv("ADMIN_ID", 0))

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL")

    # Channel
    CHANNEL_USERNAME: str = os.getenv("CHANNEL_USERNAME")
    MAX_CHANNELS: int = 5

    # Features
    ENABLE_STATISTICS: bool = True
    ENABLE_RATINGS: bool = True
    ENABLE_SEARCH: bool = True
    CACHE_TTL: int = 3600

    # Limits
    MAX_BROADCAST_RATE: float = 0.03
    MAX_MOVIE_SIZE_MB: int = 2000

    # Messages
    WELCOME_MESSAGE: str = "🎬 Xush kelibsiz! Premium kino botiga marhamat!"


config = Config()