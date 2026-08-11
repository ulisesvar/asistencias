import logging
import re

from telegram import ReplyKeyboardRemove, Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from .. import db

logger = logging.getLogger(__name__)

ASKING_ACCOUNT_NUMBER = 1

ACCOUNT_NUMBER_RE = re.compile(r"^[A-Za-z0-9-]{3,20}$")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    existing = await db.get_student_by_telegram_id(user.id)
    if existing is not None:
        await update.message.reply_text(
            f"Ya estas registrado como cuenta {existing['account_number']}. "
            "Cuando el profesor abra el pase de lista, manda tu ubicacion para registrar tu asistencia."
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "Bienvenido. Vamos a registrarte.\n\n"
        "Escribe tu numero de cuenta:",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ASKING_ACCOUNT_NUMBER


async def receive_account_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    account_number = update.message.text.strip()

    if not ACCOUNT_NUMBER_RE.match(account_number):
        await update.message.reply_text(
            "Numero de cuenta invalido. Usa solo letras, numeros y guiones (3-20 caracteres). Intenta de nuevo:"
        )
        return ASKING_ACCOUNT_NUMBER

    if await db.get_student_by_account_number(account_number) is not None:
        await update.message.reply_text(
            "Ese numero de cuenta ya esta registrado. Si crees que es un error, contacta al profesor."
        )
        return ConversationHandler.END

    user = update.effective_user
    await db.register_student(user.id, user.username, account_number)

    await update.message.reply_text(
        f"Listo, {account_number} quedo registrado con tu usuario de Telegram "
        f"(@{user.username or user.id}).\n\n"
        "Cuando el profesor pida pasar lista, manda tu ubicacion aqui mismo."
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Registro cancelado. Escribe /start cuando quieras intentarlo de nuevo.")
    return ConversationHandler.END


def account_number_handler() -> MessageHandler:
    return MessageHandler(filters.TEXT & ~filters.COMMAND, receive_account_number)
