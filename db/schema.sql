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

CREATE TABLE IF NOT EXISTS attendance_attempts (
    id                  SERIAL PRIMARY KEY,
    telegram_id         BIGINT NOT NULL,
    student_id          INTEGER REFERENCES students(id),
    session_id          INTEGER REFERENCES attendance_sessions(id),
    result              TEXT NOT NULL CHECK (result IN (
                            'SUCCESS',
                            'NOT_REGISTERED',
                            'NO_OPEN_SESSION',
                            'SESSION_EXPIRED',
                            'ALREADY_ATTENDED',
                            'OUT_OF_RANGE'
                        )),
    latitude            DOUBLE PRECISION,
    longitude           DOUBLE PRECISION,
    horizontal_accuracy DOUBLE PRECISION,
    distance_meters     DOUBLE PRECISION,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_attendance_attempts_student ON attendance_attempts(student_id);
CREATE INDEX IF NOT EXISTS idx_attendance_attempts_session ON attendance_attempts(session_id);
CREATE INDEX IF NOT EXISTS idx_attendance_attempts_created_at ON attendance_attempts(created_at);
