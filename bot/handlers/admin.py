import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.error import Forbidden
from telegram.ext import ContextTypes

from .. import config, db

logger = logging.getLogger(__name__)


def _is_teacher(user_id: int) -> bool:
    return user_id in config.TEACHER_IDS


async def open_attendance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not _is_teacher(user.id):
        await update.message.reply_text("No tienes permiso para usar este comando.")
        return

    minutes = config.SESSION_DEFAULT_MINUTES
    if context.args:
        try:
            minutes = int(context.args[0])
            if minutes < 1 or minutes > 120:
                raise ValueError
        except ValueError:
            await update.message.reply_text("Duracion invalida. Usa: /pase [minutos entre 1 y 120]")
            return

    session = await db.open_session(user.id, minutes)
    await update.message.reply_text(
        f"Pase de lista abierto por {minutes} minutos (sesion #{session['id']}). "
        "Avisando a los alumnos registrados..."
    )

    students = await db.list_registered_students()
    sent, failed = 0, 0
    for student in students:
        try:
            await context.bot.send_message(
                chat_id=student["telegram_id"],
                text=(
                    f"El profesor abrio el pase de lista por {minutes} minutos.\n"
                    "Manda tu ubicacion actual a este chat para registrar tu asistencia."
                ),
            )
            sent += 1
        except Forbidden:
            failed += 1
            logger.warning("No se pudo notificar al alumno %s (bloqueo el bot)", student["telegram_id"])

    await update.message.reply_text(f"Notificados: {sent}. Fallidos: {failed}.")


async def close_attendance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not _is_teacher(user.id):
        await update.message.reply_text("No tienes permiso para usar este comando.")
        return

    session = await db.get_open_session()
    if session is None:
        await update.message.reply_text("No hay ningun pase de lista abierto.")
        return

    await db.close_session(session["id"])
    count = await db.count_attendances(session["id"])
    await update.message.reply_text(f"Pase de lista #{session['id']} cerrado. Asistencias registradas: {count}.")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not _is_teacher(user.id):
        await update.message.reply_text("No tienes permiso para usar este comando.")
        return

    session = await db.get_open_session()
    if session is None:
        await update.message.reply_text("No hay ningun pase de lista abierto.")
        return

    count = await db.count_attendances(session["id"])
    await update.message.reply_text(
        f"Sesion #{session['id']} abierta hasta {session['closes_at']:%Y-%m-%d %H:%M %Z}.\n"
        f"Asistencias registradas hasta ahora: {count}."
    )
