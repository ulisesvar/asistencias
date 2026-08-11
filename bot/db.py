import logging
from datetime import datetime, timedelta, timezone

import asyncpg

from . import config

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None


async def init_pool() -> None:
    global _pool
    _pool = await asyncpg.create_pool(config.DATABASE_URL, min_size=1, max_size=5)
    logger.info("Pool de conexiones a PostgreSQL creado")


async def close_pool() -> None:
    if _pool is not None:
        await _pool.close()


def pool() -> asyncpg.Pool:
    assert _pool is not None, "El pool de base de datos no ha sido inicializado"
    return _pool


async def get_student_by_telegram_id(telegram_id: int) -> asyncpg.Record | None:
    return await pool().fetchrow(
        "SELECT * FROM students WHERE telegram_id = $1", telegram_id
    )


async def get_student_by_account_number(account_number: str) -> asyncpg.Record | None:
    return await pool().fetchrow(
        "SELECT * FROM students WHERE account_number = $1", account_number
    )


async def register_student(
    telegram_id: int, telegram_username: str | None, account_number: str
) -> asyncpg.Record:
    return await pool().fetchrow(
        """
        INSERT INTO students (telegram_id, telegram_username, account_number)
        VALUES ($1, $2, $3)
        RETURNING *
        """,
        telegram_id,
        telegram_username,
        account_number,
    )


async def list_registered_students() -> list[asyncpg.Record]:
    return await pool().fetch("SELECT * FROM students ORDER BY registered_at")


async def get_open_session() -> asyncpg.Record | None:
    return await pool().fetchrow(
        "SELECT * FROM attendance_sessions WHERE status = 'OPEN' ORDER BY opened_at DESC LIMIT 1"
    )


async def open_session(opened_by: int, duration_minutes: int) -> asyncpg.Record:
    async with pool().acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "UPDATE attendance_sessions SET status = 'CLOSED', closed_at = now() WHERE status = 'OPEN'"
            )
            closes_at = datetime.now(timezone.utc) + timedelta(minutes=duration_minutes)
            return await conn.fetchrow(
                """
                INSERT INTO attendance_sessions (opened_by, closes_at)
                VALUES ($1, $2)
                RETURNING *
                """,
                opened_by,
                closes_at,
            )


async def close_session(session_id: int) -> None:
    await pool().execute(
        "UPDATE attendance_sessions SET status = 'CLOSED', closed_at = now() WHERE id = $1",
        session_id,
    )


async def has_attended(session_id: int, student_id: int) -> bool:
    row = await pool().fetchrow(
        "SELECT 1 FROM attendances WHERE session_id = $1 AND student_id = $2",
        session_id,
        student_id,
    )
    return row is not None


async def record_attendance(
    session_id: int,
    student_id: int,
    latitude: float,
    longitude: float,
    distance_meters: float,
) -> asyncpg.Record:
    return await pool().fetchrow(
        """
        INSERT INTO attendances (session_id, student_id, latitude, longitude, distance_meters)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING *
        """,
        session_id,
        student_id,
        latitude,
        longitude,
        distance_meters,
    )


async def count_attendances(session_id: int) -> int:
    return await pool().fetchval(
        "SELECT count(*) FROM attendances WHERE session_id = $1", session_id
    )
