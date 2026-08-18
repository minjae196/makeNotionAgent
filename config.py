import warnings
warnings.filterwarnings('ignore')

import os
from pathlib import Path
from dotenv import load_dotenv

# .env 파일 로드
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

NOTION_API_KEY = os.getenv("NOTION_API_KEY", "").strip()
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID", "3c062085085e80058a56fb06345ace8f").strip().replace("-", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
# 최신 3세대 플래시 모델 기본값
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview").strip()

# Notion API Headers
NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}
