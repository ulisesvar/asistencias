import logging
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import ContextTypes

from .. import config, db
from ..geo import distance_meters

logger = logging.getLogger(__name__)


async def receive_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    location = update.message.location

    student = await db.get_student_by_telegram_id(user.id)
    if student is None:
        await update.message.reply_text(
            "No estas registrado todavia. Escribe /start para registrarte primero."
        )
        return

    session = await db.get_open_session()
    if session is None:
        await update.message.reply_text(
            "No hay ningun pase de lista abierto en este momento."
        )
        return

    closes_at = session["closes_at"]
    if closes_at.tzinfo is None:
        closes_at = closes_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > closes_at:
        await db.close_session(session["id"])
        await update.message.reply_text("El pase de lista ya cerro. Tu ubicacion no se registro.")
        return

    if await db.has_attended(session["id"], student["id"]):
        await update.message.reply_text("Tu asistencia ya estaba registrada para esta sesion.")
        return

    dist = distance_meters(
        location.latitude, location.longitude, config.CLASSROOM_LAT, config.CLASSROOM_LON
    )

    if dist > config.CLASSROOM_RADIUS_METERS:
        await update.message.reply_text(
            f"Tu ubicacion esta a {dist:.0f} m del salon (maximo permitido: "
            f"{config.CLASSROOM_RADIUS_METERS} m). No se registro tu asistencia."
        )
        return

    await db.record_attendance(
        session["id"], student["id"], location.latitude, location.longitude, dist
    )
    await update.message.reply_text(
        f"Asistencia registrada. Distancia al salon: {dist:.0f} m."
    )
