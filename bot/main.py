import logging
import sys
from pathlib import Path

from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from . import config, db
from .handlers import admin, attendance, registration

logging.basicConfig(
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def _on_startup(application: Application) -> None:
    await db.init_pool()
    logger.info("Bot iniciado. Sala configurada en (%s, %s), radio %sm.",
                config.CLASSROOM_LAT, config.CLASSROOM_LON, config.CLASSROOM_RADIUS_METERS)


async def _on_shutdown(application: Application) -> None:
    await db.close_pool()


async def _heartbeat(context) -> None:
    Path(config.HEARTBEAT_FILE).touch()


def build_application() -> Application:
    application = (
        Application.builder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .post_init(_on_startup)
        .post_shutdown(_on_shutdown)
        .build()
    )

    registration_conv = ConversationHandler(
        entry_points=[CommandHandler("start", registration.start)],
        states={
            registration.ASKING_ACCOUNT_NUMBER: [registration.account_number_handler()],
        },
        fallbacks=[CommandHandler("cancel", registration.cancel)],
    )

    application.add_handler(registration_conv)
    application.add_handler(CommandHandler("pase", admin.open_attendance))
    application.add_handler(CommandHandler("cerrar", admin.close_attendance))
    application.add_handler(CommandHandler("estado", admin.status))
    application.add_handler(MessageHandler(filters.LOCATION, attendance.receive_location))

    application.job_queue.run_repeating(
        _heartbeat, interval=config.HEARTBEAT_INTERVAL_SECONDS, first=0
    )

    return application


def main() -> None:
    application = build_application()
    application.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
