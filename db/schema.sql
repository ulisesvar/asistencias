CREATE TABLE IF NOT EXISTS students (
    id              SERIAL PRIMARY KEY,
    telegram_id     BIGINT UNIQUE NOT NULL,
    telegram_username TEXT,
    account_number  TEXT UNIQUE NOT NULL,
    registered_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS attendance_sessions (
    id          SERIAL PRIMARY KEY,
    opened_by   BIGINT NOT NULL,
    opened_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    closes_at   TIMESTAMPTZ NOT NULL,
    status      TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'CLOSED')),
    closed_at   TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS attendances (
    id              SERIAL PRIMARY KEY,
    session_id      INTEGER NOT NULL REFERENCES attendance_sessions(id),
    student_id      INTEGER NOT NULL REFERENCES students(id),
    latitude        DOUBLE PRECISION NOT NULL,
    longitude       DOUBLE PRECISION NOT NULL,
    distance_meters DOUBLE PRECISION NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (session_id, student_id)
);

CREATE INDEX IF NOT EXISTS idx_attendances_session ON attendances(session_id);
