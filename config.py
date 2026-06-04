import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-change-in-prod')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///job_tracker.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    APP_PASSWORD = os.environ.get('APP_PASSWORD', 'changeme')
    LBA_API_KEY = os.environ.get('LBA_API_KEY', '')

    # ── n8n webhooks sortants ─────────────────────────────────────────────────
    N8N_WEBHOOK_ENRICH = os.environ.get('N8N_WEBHOOK_ENRICH', '')
    N8N_WEBHOOK_LM = os.environ.get('N8N_WEBHOOK_LM', '')

    # ── France Travail API (W1 — scraping alternance) ─────────────────────────
    FT_CLIENT_ID = os.environ.get('FT_CLIENT_ID', '')
    FT_CLIENT_SECRET = os.environ.get('FT_CLIENT_SECRET', '')