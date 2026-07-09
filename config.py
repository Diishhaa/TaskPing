import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base directories
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Database and CSV Export settings
DB_PATH = DATA_DIR / "hackathons.db"
CSV_PATH = DATA_DIR / "hackathons.csv"

# Polling configuration (e.g. run frequency in hours)
POLLING_INTERVAL_HOURS = int(os.getenv("POLLING_INTERVAL_HOURS", "3"))

# Scraping settings
REQUEST_TIMEOUT = 15  # seconds
MAX_RETRIES = 3
BACKOFF_FACTOR = 2.0

# Scoring Settings
MIN_SCORE_THRESHOLD = int(os.getenv("MIN_SCORE_THRESHOLD", "40"))

# Scoring Weights (total must sum to 100)
WEIGHTS = {
    "prize_money": 30,
    "deadline_urgency": 20,
    "online_preferred": 15,
    "participant_count": 10,
    "theme_relevance": 15,
    "popularity": 10
}

# Theme relevance priorities and their specific weights/sub-scores
THEME_WEIGHTS = {
    "artificial intelligence": 15,
    "ai": 15,
    "agentic ai": 15,
    "generative ai": 15,
    "machine learning": 15,
    "ml": 15,
    "healthcare": 10,
    "fintech": 10,
    "climate tech": 10,
    "accessibility": 10,
    "cybersecurity": 10,
    "open source": 10,
    "blockchain": 10,
    "web3": 10,
    "government": 10
}

# Keyword Alert Settings
ALERT_KEYWORDS = [
    "AI", "LLM", "Gemini", "OpenAI", "Healthcare", 
    "Flutter", "React", "Android", "Web3", "Blockchain"
]

# Telegram API settings
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") or os.getenv("CHAT_ID")

# Enabled collectors
ENABLED_PLATFORMS = {
    "devpost": True,
    "devfolio": True,
    "unstop": True,
    "mlh": True,
    "hack2skill": True,
    "luma": True,
    "google": True,
    "microsoft": True,
    "ieee": True
}
