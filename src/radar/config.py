from pathlib import Path
import os
from dotenv import load_dotenv

# Root project directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Load .env file
load_dotenv(PROJECT_ROOT / ".env")

# Data and Cache paths
DATA_DIR = PROJECT_ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"
DB_PATH = DATA_DIR / "radar.db"

# Briefings output path
BRIEFINGS_DIR = PROJECT_ROOT / "briefings"

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)
BRIEFINGS_DIR.mkdir(parents=True, exist_ok=True)

# API Configurations
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", None)
USER_AGENT = "TechIntelligenceRadar/1.0 (AutonomousResearchAgent)"

# Thresholds
MIN_GITHUB_STARS_DEFAULT = 30
DEFAULT_DAYS_LOOKBACK = 7
NOVELTY_SCORE_THRESHOLD = 6.0

# Gmail SMTP & Morning Briefing Configurations
GMAIL_USER = os.getenv("GMAIL_USER", "").strip()
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "").strip().replace(" ", "")
BRIEFING_RECIPIENT = os.getenv("BRIEFING_RECIPIENT", "").strip() or GMAIL_USER
BRIEFING_TIME = os.getenv("BRIEFING_TIME", "08:00").strip()

# Watchlist & Trending settings
raw_topics = os.getenv("CORE_TOPICS", "AI Agents, Model Context Protocol")
CORE_TOPICS = [t.strip() for t in raw_topics.split(",") if t.strip()]
INCLUDE_TRENDING_AI = os.getenv("INCLUDE_TRENDING_AI", "true").lower() in ("true", "1", "yes")
BRIEFING_ITEMS_LIMIT = int(os.getenv("BRIEFING_ITEMS_LIMIT", "8"))
