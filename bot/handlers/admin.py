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


_RESULT_LABELS = {
    "SUCCESS": "OK",
    "NOT_REGISTERED": "no registrado",
    "NO_OPEN_SESSION": "sin pase abierto",
    "SESSION_EXPIRED": "pase ya cerrado",
    "ALREADY_ATTENDED": "ya habia asistido",
    "OUT_OF_RANGE": "fuera de rango",
}


async def attempt_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not _is_teacher(user.id):
        await update.message.reply_text("No tienes permiso para usar este comando.")
        return

    if not context.args:
        await update.message.reply_text("Uso: /historial [numero de cuenta]")
        return

    account_number = context.args[0]
    student = await db.get_student_by_account_number(account_number)
    if student is None:
        await update.message.reply_text(f"No existe ningun alumno con cuenta {account_number}.")
        return

    attempts = await db.list_attempts_for_student(student["id"])
    if not attempts:
        await update.message.reply_text(f"{account_number} no tiene intentos registrados todavia.")
        return

    lines = [f"Ultimos intentos de {account_number}:"]
    for a in attempts:
        label = _RESULT_LABELS.get(a["result"], a["result"])
        line = f"- {a['created_at']:%Y-%m-%d %H:%M %Z} [{label}]"
        if a["distance_meters"] is not None:
            line += f" dist={a['distance_meters']:.0f}m"
        if a["latitude"] is not None:
            line += f" ({a['latitude']:.5f}, {a['longitude']:.5f})"
        if a["horizontal_accuracy"] is not None:
            line += f" precision={a['horizontal_accuracy']:.0f}m"
        if a["session_id"] is not None:
            line += f" sesion=#{a['session_id']}"
        lines.append(line)

    await update.message.reply_text("\n".join(lines))
