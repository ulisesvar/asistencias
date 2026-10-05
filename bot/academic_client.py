"""Cliente de solo lectura hacia el servicio academico.

Unica operacion: obtener la evaluacion actual de UN alumno. El bot no calcula
calificaciones; solo pide el resultado y lo presenta.

La credencial (ACADEMIC_API_KEY) viaja unicamente en el header X-API-Key. Nunca
se escribe en logs, mensajes ni excepciones.
"""

import logging
from typing import Any
from urllib.parse import quote

import httpx

from . import config

logger = logging.getLogger(__name__)

# httpx registra en INFO la URL completa de cada peticion (incluiria el numero de
# cuenta en la ruta). Se sube el nivel para que eso no llegue a los logs.
logging.getLogger("httpx").setLevel(logging.WARNING)


class AcademicApiError(Exception):
    """Fallo al consultar la evaluacion. El mensaje es interno; nunca se muestra al alumno.

    `kind` es una etiqueta corta y segura para logs (no contiene datos del alumno).
    """

    def __init__(self, kind: str, status_code: int | None = None) -> None:
        self.kind = kind
        self.status_code = status_code
        super().__init__(kind if status_code is None else f"{kind} (HTTP {status_code})")


class StudentNotFoundInAcademicError(AcademicApiError):
    """404: cuenta desconocida o alumno fuera del curso de la credencial."""


def is_configured() -> bool:
    return bool(config.ACADEMIC_API_BASE_URL and config.ACADEMIC_API_KEY)


def _classify_status(status_code: int) -> AcademicApiError:
    if status_code == 404:
        return StudentNotFoundInAcademicError("not_found", status_code)
    if status_code == 401:
        return AcademicApiError("unauthorized", status_code)
    if status_code == 403:
        return AcademicApiError("forbidden", status_code)
    if status_code == 429:
        return AcademicApiError("rate_limited", status_code)
    if status_code >= 500:
        return AcademicApiError("server_error", status_code)
    return AcademicApiError("unexpected_status", status_code)


async def fetch_evaluation(
    account_number: str, *, transport: httpx.AsyncBaseTransport | None = None
) -> dict[str, Any]:
    """GET /bot/evaluation/{account_number}. `account_number` debe venir del registro del
    alumno en la base de datos, nunca de texto escrito por el alumno en el comando.
    """
    if not is_configured():
        raise AcademicApiError("not_configured")

    url = f"{config.ACADEMIC_API_BASE_URL.rstrip('/')}/bot/evaluation/{quote(account_number, safe='')}"
    try:
        async with httpx.AsyncClient(
            timeout=config.ACADEMIC_API_TIMEOUT_SECONDS,
            follow_redirects=False,
            transport=transport,
        ) as client:
            response = await client.get(
                url,
                headers={"X-API-Key": config.ACADEMIC_API_KEY, "Accept": "application/json"},
            )
    except httpx.TimeoutException:
        raise AcademicApiError("timeout") from None
    except httpx.HTTPError as exc:
        # Solo el tipo de excepcion: su texto puede incluir la URL.
        raise AcademicApiError(f"connection_error:{type(exc).__name__}") from None

    if response.status_code != 200:
        raise _classify_status(response.status_code)

    try:
        data = response.json()
    except ValueError:
        raise AcademicApiError("malformed_response", response.status_code) from None
    if not isinstance(data, dict):
        raise AcademicApiError("malformed_response", response.status_code)
    return data
