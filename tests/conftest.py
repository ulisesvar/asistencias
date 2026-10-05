import os

# bot.config exige estas variables al importarse. Valores de prueba, nunca reales.
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:TEST-PLACEHOLDER-TOKEN")
os.environ.setdefault("TEACHER_IDS", "1")
os.environ.setdefault("CLASSROOM_LAT", "0")
os.environ.setdefault("CLASSROOM_LON", "0")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.pop("ACADEMIC_API_BASE_URL", None)
os.environ.pop("ACADEMIC_API_KEY", None)
