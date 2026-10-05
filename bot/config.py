import os


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Falta la variable de entorno obligatoria: {name}")
    return value


def _int(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


def _float(name: str) -> float:
    return float(_required(name))


def _teacher_ids(name: str) -> set[int]:
    raw = os.environ.get(name, "")
    return {int(part.strip()) for part in raw.split(",") if part.strip()}


TELEGRAM_BOT_TOKEN = _required("TELEGRAM_BOT_TOKEN")
TEACHER_IDS = _teacher_ids("TEACHER_IDS")

CLASSROOM_LAT = _float("CLASSROOM_LAT")
CLASSROOM_LON = _float("CLASSROOM_LON")
CLASSROOM_RADIUS_METERS = _int("CLASSROOM_RADIUS_METERS", 50)

SESSION_DEFAULT_MINUTES = _int("SESSION_DEFAULT_MINUTES", 10)

DATABASE_URL = _required("DATABASE_URL")

# Consulta de calificaciones (/calif). Opcionales: si faltan, /calif responde que no esta
# disponible y el resto del bot (asistencia) funciona igual.
ACADEMIC_API_BASE_URL = os.environ.get("ACADEMIC_API_BASE_URL", "").strip()
ACADEMIC_API_KEY = os.environ.get("ACADEMIC_API_KEY", "").strip()
ACADEMIC_API_TIMEOUT_SECONDS = float(os.environ.get("ACADEMIC_API_TIMEOUT_SECONDS", "10"))

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

HEARTBEAT_FILE = os.environ.get("HEARTBEAT_FILE", "/tmp/bot_heartbeat")
HEARTBEAT_INTERVAL_SECONDS = _int("HEARTBEAT_INTERVAL_SECONDS", 30)

if not TEACHER_IDS:
    raise RuntimeError(
        "TEACHER_IDS no debe estar vacio: define al menos un ID de Telegram autorizado a tomar asistencia"
    )
