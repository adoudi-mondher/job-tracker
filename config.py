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
    # URL du webhook n8n déclenchant l'enrichissement automatique (W2)
    N8N_WEBHOOK_ENRICH = os.environ.get('N8N_WEBHOOK_ENRICH', '')
    # URL du webhook n8n déclenchant la génération de lettre de motivation (W3)
    N8N_WEBHOOK_LM = os.environ.get('N8N_WEBHOOK_LM', '')
    # ─────────────────────────────────────────────────────────────────────────