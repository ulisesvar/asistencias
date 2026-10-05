import logging

from telegram import Update
from telegram.ext import ContextTypes

from .. import academic_client, db
from ..evaluation_format import MalformedEvaluationError, format_evaluation

logger = logging.getLogger(__name__)

NOT_REGISTERED = "No estas registrado todavia. Escribe /start para registrarte primero."
PRIVATE_ONLY = "Por privacidad, usa /calif en un chat privado conmigo."
UNAVAILABLE = (
    "No fue posible consultar tu información académica en este momento. "
    "Inténtalo nuevamente más tarde."
)
NOT_FOUND = (
    "No encontré calificaciones asociadas a tu cuenta. "
    "Si crees que es un error, contacta al profesor."
)


async def grades(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/calif: la calificacion actual del propio alumno.

    La cuenta se obtiene SOLO del registro del alumno (telegram_id -> students);
    los argumentos del comando se ignoran por completo.
    """
    user = update.effective_user
    message = update.message

    if update.effective_chat is not None and update.effective_chat.type != "private":
        await message.reply_text(PRIVATE_ONLY)
        return

    student = await db.get_student_by_telegram_id(user.id)
    if student is None:
        await message.reply_text(NOT_REGISTERED)
        return

    try:
        data = await academic_client.fetch_evaluation(student["account_number"])
        text = format_evaluation(data)
    except academic_client.StudentNotFoundInAcademicError:
        logger.warning("/calif: cuenta no encontrada en el servicio academico (telegram_id=%s)", user.id)
        await message.reply_text(NOT_FOUND)
        return
    except academic_client.AcademicApiError as exc:
        logger.error("/calif: fallo al consultar el servicio academico: %s (telegram_id=%s)", exc, user.id)
        await message.reply_text(UNAVAILABLE)
        return
    except MalformedEvaluationError as exc:
        logger.error("/calif: respuesta con formato inesperado: %s (telegram_id=%s)", exc, user.id)
        await message.reply_text(UNAVAILABLE)
        return

    await message.reply_text(text)
