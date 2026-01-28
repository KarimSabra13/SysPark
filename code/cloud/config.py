import os

class Config:
    # Sécurité
    SECRET_KEY = os.getenv("FLASK_SECRET", "change_me")
    
    # Base de Données
    database_url = os.getenv("DATABASE_URL", "sqlite:///parking.db")
    if database_url and database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = database_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # MQTT
    MQTT_HOST = os.getenv("MQTT_HOST", "broker.hivemq.com")
    MQTT_PORT = 8883
    MQTT_SECRET = os.getenv("MQTT_SECRET", "CHANGE_ME")

    # Clés API & Services
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
    STRIPE_API_KEY = os.getenv("STRIPE_API_KEY")
    STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
    NGROK_BASE = os.getenv("NGROK_BASE")
    
    # Admin
    ADMIN_USER = os.getenv("ADMIN_USER", "admin")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")


