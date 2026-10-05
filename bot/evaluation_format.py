"""Presentacion de la evaluacion actual de un alumno para Telegram.

Solo formatea lo que devuelve el servicio academico; no calcula nada. Distingue
siempre null (aun no evaluado -> "Pendiente") de 0 (cero real -> "0 / 100").
No muestra nombres de actividades de Moodle ni identificadores internos: las
actividades se etiquetan por su posicion dentro de la categoria.
"""

import unicodedata
from typing import Any

PENDING = "Pendiente"

_TASKS = "tasks"
_EXAMS = "exams"
_PARTICIPATION = "participation"

_KIND_BY_NAME = {
    _TASKS: {"entregables/tareas", "tareas", "tasks"},
    _EXAMS: {"examenes", "exams"},
    _PARTICIPATION: {
        "participacion/asistencia",
        "asistencia/participacion",
        "participation/attendance",
    },
}


_TITLES = {_TASKS: "Tareas", _EXAMS: "Exámenes", _PARTICIPATION: "A/P"}


class MalformedEvaluationError(ValueError):
    """La respuesta no tiene la forma esperada."""


def _normalize(name: str) -> str:
    stripped = unicodedata.normalize("NFD", name)
    stripped = "".join(c for c in stripped if not unicodedata.combining(c))
    return "".join(stripped.lower().split()).replace(" ", "")


def _kind(category_name: str) -> str | None:
    normalized = _normalize(category_name)
    for kind, names in _KIND_BY_NAME.items():
        if normalized in names:
            return kind
    return None


def _number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MalformedEvaluationError("valor numerico invalido")
    return float(value)


def _plain(value: float) -> str:
    """80.0 -> '80'; 66.67 -> '66.67'."""
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return text or "0"


def _score(value: Any) -> str:
    number = _number(value)
    return PENDING if number is None else f"{_plain(number)} / 100"


def _two_decimals(value: Any) -> str:
    number = _number(value)
    return PENDING if number is None else f"{number:.2f}"


def _item_label(kind: str | None, position: int) -> str:
    if kind == _TASKS:
        return f"Tarea {position}"
    if kind == _EXAMS:
        return f"Examen {position}"
    return f"Actividad {position}"


def _category_block(category: dict[str, Any]) -> list[str]:
    name = category.get("name")
    items = category.get("items")
    if not isinstance(name, str) or not isinstance(items, list):
        raise MalformedEvaluationError("categoria invalida")

    kind = _kind(name)
    title = _TITLES.get(kind, name) if kind else name

    weight = _number(category.get("weight_percent"))
    if weight is None:
        raise MalformedEvaluationError("peso invalido")

    lines = [title]
    # Solo las actividades que cuentan para la calificacion; se numeran por su
    # posicion entre ellas, en el orden en que las entrega el servicio.
    counted = [i for i in items if isinstance(i, dict) and i.get("counts_toward_current_grade")]
    for position, item in enumerate(counted, start=1):
        lines.append(f"{_item_label(kind, position)}: {_score(item.get('score_100'))}")

    contribution = _number(category.get("contribution_points"))
    lines.append(f"Promedio: {_two_decimals(category.get('category_score_100'))}")
    lines.append(f"Peso: {_plain(weight)}%")
    lines.append(
        f"Aportación: {PENDING}"
        if contribution is None
        else f"Aportación: {contribution:.2f} / {_plain(weight)}"
    )
    return lines


def format_evaluation(data: dict[str, Any]) -> str:
    categories = data.get("categories")
    if not isinstance(categories, list):
        raise MalformedEvaluationError("categorias ausentes")

    grade_10 = _number(data.get("current_grade_10"))
    evaluated_weight = _number(data.get("evaluated_weight_percent"))

    lines = ["Tu calificación actual", ""]
    if grade_10 is None:
        lines.append(PENDING)
        lines.append("Aún no hay actividades evaluadas.")
    else:
        lines.append(f"{grade_10:.2f} / 10")

    for category in categories:
        if not isinstance(category, dict):
            raise MalformedEvaluationError("categoria invalida")
        lines.append("")
        lines.extend(_category_block(category))

    lines.append("")
    if grade_10 is not None:
        lines.append(f"Calificación actual: {grade_10:.2f} / 10")
    if evaluated_weight is not None and evaluated_weight < 100:
        lines.append(f"Peso evaluado: {_plain(evaluated_weight)}%")
        lines.append("Aún no es tu calificación final: faltan actividades por evaluar.")
    return "\n".join(lines).rstrip()
