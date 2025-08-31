import os
from dotenv import load_dotenv

load_dotenv()

APP_SECRET_KEY = os.getenv("APP_SECRET_KEY", "dev-secret")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
OAUTH_REDIRECT_URI = os.getenv("OAUTH_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
DB_URL = os.getenv("DB_URL", "sqlite:///./data.db")
ENV = os.getenv("ENV", "local")
GMAIL_SCOPE = os.getenv("GMAIL_SCOPE", "https://www.googleapis.com/auth/gmail.readonly")
