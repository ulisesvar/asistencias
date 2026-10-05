"""/calif: lectura de la calificacion actual del propio alumno.

Sin red ni base de datos reales: la plataforma academica se simula con
httpx.MockTransport y el alumno con un doble de db.get_student_by_telegram_id.
La llave usada aqui es un valor de prueba, no una credencial real.
"""

import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from telegram.ext import CommandHandler, ConversationHandler, MessageHandler

from bot import academic_client, config, db
from bot.handlers import grades

TEST_KEY = "test-key-NOT-A-REAL-CREDENTIAL-0000"
BASE_URL = "https://academic.test"

SENSITIVE_NAMES = ("Tarea Secreta Moodle", "Parcial Final Moodle", "Foro Interno")


def _evaluation(**overrides):
    body = {
        "student_id": 7,
        "course_id": 1,
        "weighted_points_earned": 62.12,
        "evaluated_weight_percent": 100.0,
        "current_score_100": 62.12,
        "current_grade_10": 6.21,
        "categories": [
            {
                "category_id": 11,
                "name": "Entregables / tareas",
                "weight_percent": 40.0,
                "category_score_100": 40.0,
                "contribution_points": 16.0,
                "counted_items": 3,
                "graded_items": 2,
                "ungraded_items": 1,
                "items": [
                    _item(101, "Tarea Secreta Moodle", 80),
                    _item(102, "Foro Interno", None),
                    _item(103, "Otra Actividad", 0),
                ],
            },
            {
                "category_id": 12,
                "name": "Exámenes",
                "weight_percent": 40.0,
                "category_score_100": 90.0,
                "contribution_points": 36.0,
                "counted_items": 1,
                "graded_items": 1,
                "ungraded_items": 0,
                "items": [_item(201, "Parcial Final Moodle", 90)],
            },
            {
                "category_id": 13,
                "name": "Participación / asistencia",
                "weight_percent": 20.0,
                "category_score_100": 50.62,
                "contribution_points": 10.12,
                "counted_items": 0,
                "graded_items": 0,
                "ungraded_items": 0,
                "items": [],
            },
        ],
    }
    body.update(overrides)
    return body


def _item(item_id, name, score, counts=True):
    return {
        "grade_item_id": item_id,
        "name": name,
        "activity_type": "assign",
        "grade": score,
        "max_grade": 100.0,
        "score_100": score,
        "counts_toward_current_grade": counts,
    }


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setattr(config, "ACADEMIC_API_BASE_URL", BASE_URL)
    monkeypatch.setattr(config, "ACADEMIC_API_KEY", TEST_KEY)
    monkeypatch.setattr(config, "ACADEMIC_API_TIMEOUT_SECONDS", 5.0)


class FakeApi:
    """Registra las peticiones y responde lo configurado, sin red."""

    def __init__(self, handler):
        self.requests: list[httpx.Request] = []
        self._handler = handler

    def transport(self):
        def respond(request):
            self.requests.append(request)
            return self._handler(request)

        return httpx.MockTransport(respond)


def _install(monkeypatch, api: FakeApi):
    real = academic_client.fetch_evaluation

    async def with_transport(account_number, *, transport=None):
        return await real(account_number, transport=api.transport())

    monkeypatch.setattr(academic_client, "fetch_evaluation", with_transport)


def _student(monkeypatch, account_number="318232148", telegram_id=555):
    lookup = AsyncMock(
        return_value={"id": 1, "telegram_id": telegram_id, "account_number": account_number}
    )
    monkeypatch.setattr(db, "get_student_by_telegram_id", lookup)
    return lookup


def _unregistered(monkeypatch):
    lookup = AsyncMock(return_value=None)
    monkeypatch.setattr(db, "get_student_by_telegram_id", lookup)
    return lookup


def _update(telegram_id=555, chat_type="private", text="/calif"):
    message = SimpleNamespace(text=text, reply_text=AsyncMock())
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=telegram_id),
        effective_chat=SimpleNamespace(type=chat_type),
        message=message,
    )


def _run_calif(update, args=()):
    context = SimpleNamespace(args=list(args))
    asyncio.run(grades.grades(update, context))
    return [call.args[0] for call in update.message.reply_text.call_args_list]


def _ok(body=None):
    return FakeApi(lambda request: httpx.Response(200, json=body or _evaluation()))


# --- registered student -----------------------------------------------------


def test_registered_student_gets_their_grade(monkeypatch):
    _student(monkeypatch)
    api = _ok()
    _install(monkeypatch, api)

    replies = _run_calif(_update())

    assert len(replies) == 1
    assert "Tu calificación actual" in replies[0]
    assert len(api.requests) == 1


def test_student_is_looked_up_by_telegram_id(monkeypatch):
    lookup = _student(monkeypatch, telegram_id=987)
    _install(monkeypatch, _ok())

    _run_calif(_update(telegram_id=987))

    lookup.assert_awaited_once_with(987)


def test_account_number_comes_from_the_database_not_the_command(monkeypatch):
    _student(monkeypatch, account_number="318232148")
    api = _ok()
    _install(monkeypatch, api)

    _run_calif(_update(text="/calif 999999999"), args=["999999999"])

    assert len(api.requests) == 1
    assert api.requests[0].url.path == "/bot/evaluation/318232148"
    assert "999999999" not in str(api.requests[0].url)


def test_calls_only_the_bot_endpoint_with_get_and_key_header(monkeypatch):
    _student(monkeypatch)
    api = _ok()
    _install(monkeypatch, api)

    _run_calif(_update())

    request = api.requests[0]
    assert request.method == "GET"
    assert str(request.url) == f"{BASE_URL}/bot/evaluation/318232148"
    assert request.headers["x-api-key"] == TEST_KEY
    assert TEST_KEY not in str(request.url)


def test_unregistered_user_is_told_to_register_and_api_is_not_called(monkeypatch):
    _unregistered(monkeypatch)
    api = _ok()
    _install(monkeypatch, api)

    replies = _run_calif(_update())

    assert replies == [grades.NOT_REGISTERED]
    assert api.requests == []


def test_group_chat_is_refused_without_any_lookup(monkeypatch):
    lookup = _student(monkeypatch)
    api = _ok()
    _install(monkeypatch, api)

    replies = _run_calif(_update(chat_type="supergroup"))

    assert replies == [grades.PRIVATE_ONLY]
    lookup.assert_not_awaited()
    assert api.requests == []


# --- presentation ----------------------------------------------------------


def _text(monkeypatch, body=None):
    _student(monkeypatch)
    _install(monkeypatch, _ok(body))
    return _run_calif(_update())[0]


def test_current_grade_10_is_displayed(monkeypatch):
    text = _text(monkeypatch)

    assert "6.21 / 10" in text
    assert "Calificación actual: 6.21 / 10" in text


def test_tasks_are_labelled_by_position(monkeypatch):
    text = _text(monkeypatch)

    assert "Tarea 1: 80 / 100" in text
    assert "Tarea 2: Pendiente" in text
    assert "Tarea 3: 0 / 100" in text


def test_exams_are_labelled_by_position(monkeypatch):
    body = _evaluation()
    body["categories"][1]["items"].append(_item(202, "Segundo", 70))

    text = _text(monkeypatch, body)

    assert "Examen 1: 90 / 100" in text
    assert "Examen 2: 70 / 100" in text


def test_participation_is_displayed_as_ap(monkeypatch):
    text = _text(monkeypatch)

    assert "A/P" in text
    ap = text.split("A/P", 1)[1]
    assert "Promedio: 50.62" in ap
    assert "Peso: 20%" in ap
    assert "Aportación: 10.12 / 20" in ap


def test_category_summary_lines(monkeypatch):
    text = _text(monkeypatch)

    assert "Promedio: 40.00" in text
    assert "Peso: 40%" in text
    assert "Aportación: 16.00 / 40" in text
    assert "Aportación: 36.00 / 40" in text


def test_original_moodle_names_and_internal_fields_are_not_displayed(monkeypatch):
    text = _text(monkeypatch)

    for name in SENSITIVE_NAMES + ("Otra Actividad",):
        assert name not in text
    for internal in ("grade_item_id", "activity_type", "counts_toward", "assign", "student_id"):
        assert internal not in text
    assert "Academic" not in text and "API" not in text


def test_null_grade_is_pending_not_zero(monkeypatch):
    body = _evaluation()
    body["categories"][0]["items"] = [_item(1, "x", None)]

    text = _text(monkeypatch, body)

    assert "Tarea 1: Pendiente" in text
    assert "Tarea 1: 0" not in text


def test_zero_grade_is_displayed_as_zero(monkeypatch):
    body = _evaluation()
    body["categories"][0]["items"] = [_item(1, "x", 0)]

    text = _text(monkeypatch, body)

    assert "Tarea 1: 0 / 100" in text
    assert "Tarea 1: Pendiente" not in text


def test_null_category_values_are_pending_not_zero(monkeypatch):
    body = _evaluation()
    body["categories"][1].update(category_score_100=None, contribution_points=None)
    body["categories"][1]["items"] = [_item(1, "x", None)]

    text = _text(monkeypatch, body)

    exams = text.split("Exámenes", 1)[1].split("A/P", 1)[0]
    assert "Promedio: Pendiente" in exams
    assert "Aportación: Pendiente" in exams
    assert "Promedio: 0" not in exams


def test_null_current_grade_is_pending_not_zero(monkeypatch):
    body = _evaluation(current_grade_10=None, current_score_100=None, evaluated_weight_percent=0.0)

    text = _text(monkeypatch, body)

    assert "Pendiente" in text
    assert "0.00 / 10" not in text


def test_real_zero_current_grade_is_displayed(monkeypatch):
    body = _evaluation(current_grade_10=0.0, current_score_100=0.0)

    text = _text(monkeypatch, body)

    assert "0.00 / 10" in text


def test_partial_evaluation_says_it_is_not_final(monkeypatch):
    body = _evaluation(evaluated_weight_percent=60.0)

    text = _text(monkeypatch, body)

    assert "Peso evaluado: 60%" in text
    assert "no es tu calificación final" in text


def test_items_that_do_not_count_are_not_shown_or_numbered(monkeypatch):
    body = _evaluation()
    body["categories"][0]["items"] = [
        _item(1, "a", 50, counts=False),
        _item(2, "b", 80),
        _item(3, "c", 60),
    ]

    text = _text(monkeypatch, body)

    assert "Tarea 1: 80 / 100" in text
    assert "Tarea 2: 60 / 100" in text
    assert "Tarea 3" not in text


# --- API failures -----------------------------------------------------------


def _failing(handler_or_status):
    if isinstance(handler_or_status, int):
        return FakeApi(lambda request: httpx.Response(handler_or_status, json={"detail": "SECRETO-INTERNO"}))
    return FakeApi(handler_or_status)


@pytest.mark.parametrize("status", [401, 403, 429, 500, 502, 503])
def test_api_errors_show_a_friendly_message(monkeypatch, status):
    _student(monkeypatch)
    _install(monkeypatch, _failing(status))

    replies = _run_calif(_update())

    assert replies == [grades.UNAVAILABLE]
    assert "SECRETO-INTERNO" not in replies[0]
    assert str(status) not in replies[0]


def test_404_shows_the_not_found_message(monkeypatch):
    _student(monkeypatch)
    _install(monkeypatch, _failing(404))

    replies = _run_calif(_update())

    assert replies == [grades.NOT_FOUND]
    assert "SECRETO-INTERNO" not in replies[0]


def test_timeout_shows_a_friendly_message(monkeypatch):
    def boom(request):
        raise httpx.ReadTimeout("timed out", request=request)

    _student(monkeypatch)
    _install(monkeypatch, _failing(boom))

    assert _run_calif(_update()) == [grades.UNAVAILABLE]


def test_connection_failure_shows_a_friendly_message(monkeypatch):
    def boom(request):
        raise httpx.ConnectError("no route to host https://academic.test", request=request)

    _student(monkeypatch)
    _install(monkeypatch, _failing(boom))

    replies = _run_calif(_update())

    assert replies == [grades.UNAVAILABLE]
    assert "academic.test" not in replies[0]


def test_malformed_responses_show_a_friendly_message(monkeypatch):
    _student(monkeypatch)
    for response in (
        httpx.Response(200, text="<html>not json</html>"),
        httpx.Response(200, json=["a", "list"]),
        httpx.Response(200, json={"categories": "nope"}),
        httpx.Response(200, json={"current_grade_10": "7", "categories": []}),
    ):
        _install(monkeypatch, FakeApi(lambda request, r=response: r))
        assert _run_calif(_update()) == [grades.UNAVAILABLE]


def test_missing_configuration_degrades_without_calling_anything(monkeypatch):
    monkeypatch.setattr(config, "ACADEMIC_API_KEY", "")
    _student(monkeypatch)
    api = _ok()
    _install(monkeypatch, api)

    assert _run_calif(_update()) == [grades.UNAVAILABLE]
    assert api.requests == []


def test_redirects_are_not_followed(monkeypatch):
    def redirect(request):
        if request.url.host == "academic.test":
            return httpx.Response(302, headers={"location": "https://evil.test/steal"})
        raise AssertionError("redirect was followed")

    _student(monkeypatch)
    _install(monkeypatch, _failing(redirect))

    assert _run_calif(_update()) == [grades.UNAVAILABLE]


# --- secrets ----------------------------------------------------------------


def test_api_key_never_reaches_logs_or_replies(monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    _student(monkeypatch)
    all_replies: list[str] = []

    def boom(request):
        raise httpx.ConnectError("connection refused", request=request)

    for api in (_ok(), _failing(401), _failing(500), _failing(404), _failing(boom)):
        _install(monkeypatch, api)
        all_replies += _run_calif(_update())

    assert all_replies
    assert TEST_KEY not in "".join(all_replies)
    assert TEST_KEY not in caplog.text
    assert "x-api-key" not in caplog.text.lower()
    assert "318232148" not in caplog.text  # tampoco el numero de cuenta


def test_client_never_puts_the_key_in_the_url_or_exception(monkeypatch):
    api = _failing(403)
    with pytest.raises(academic_client.AcademicApiError) as excinfo:
        asyncio.run(academic_client.fetch_evaluation("318232148", transport=api.transport()))

    assert TEST_KEY not in str(excinfo.value)
    assert TEST_KEY not in str(api.requests[0].url)


def test_account_number_is_url_encoded_in_the_path(monkeypatch):
    api = _ok()
    asyncio.run(academic_client.fetch_evaluation("a/b?c#d", transport=api.transport()))

    assert api.requests[0].url.raw_path == b"/bot/evaluation/a%2Fb%3Fc%23d"


# --- existing behaviour is untouched --------------------------------------


def test_existing_commands_and_handlers_are_still_registered():
    from bot.main import build_application

    application = build_application()
    handlers = application.handlers[0]

    commands = {c for h in handlers if isinstance(h, CommandHandler) for c in h.commands}
    assert commands == {"pase", "cerrar", "estado", "calif"}

    conversations = [h for h in handlers if isinstance(h, ConversationHandler)]
    assert len(conversations) == 1
    assert [c for e in conversations[0].entry_points for c in e.commands] == ["start"]
    assert [c for e in conversations[0].fallbacks for c in e.commands] == ["cancel"]

    from telegram.ext import filters

    assert any(
        isinstance(h, MessageHandler) and h.filters is filters.LOCATION for h in handlers
    )
    assert len(handlers) == 6  # 5 existentes (start, pase, cerrar, estado, ubicacion) + /calif
