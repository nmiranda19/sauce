import os
from datetime import date
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL: str = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY: str = os.environ["SUPABASE_SERVICE_KEY"]

# NHL season in YYYYYYYY format (e.g. 20252026)
SEASON_YEAR: int = int(os.environ.get("SEASON_YEAR", "20252026"))

# First day of the NHL regular season — used to compute week numbers
_raw = os.environ.get("SEASON_START_DATE", "2025-10-07")
SEASON_START_DATE: date = date.fromisoformat(_raw)

JWT_SECRET_KEY: str = os.environ.get("JWT_SECRET_KEY", "change-me-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_DAYS = 30

NHL_API_BASE = "https://api-web.nhle.com"
NHL_STATS_BASE = "https://api.nhle.com/stats/rest"

# Regular season game type code in the NHL API
NHL_REGULAR_SEASON = 2
