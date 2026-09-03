import os
from sqlalchemy import create_engine, text

DB_URL = f"postgresql+psycopg://seu_analytics:{os.environ['PGPASSWORD']}@localhost:5432/seu_enrollment"
engine = create_engine(DB_URL)

SCHEMA = """
DROP TABLE IF EXISTS course_enrollments;
DROP TABLE IF EXISTS financial_aid;
DROP TABLE IF EXISTS enrollments;
DROP TABLE IF EXISTS courses;
DROP TABLE IF EXISTS students;
DROP TABLE IF EXISTS terms;

CREATE TABLE terms (
    term_id       INTEGER PRIMARY KEY,
    academic_year INTEGER NOT NULL,
    season        TEXT    NOT NULL CHECK (season IN ('Fall','Spring','Summer')),
    label         TEXT    NOT NULL,
    census_date   DATE    NOT NULL
);

CREATE TABLE students (
    student_id      SERIAL PRIMARY KEY,
    entry_term_id   INTEGER NOT NULL REFERENCES terms(term_id),
    entry_type      TEXT    NOT NULL CHECK (entry_type IN ('first-time','transfer')),
    entry_major     TEXT    NOT NULL,
    residency       TEXT    NOT NULL CHECK (residency IN ('on-campus','commuter')),
    hs_gpa          NUMERIC(3,2),
    first_gen       BOOLEAN NOT NULL
);

CREATE TABLE enrollments (
    student_id    INTEGER NOT NULL REFERENCES students(student_id),
    term_id       INTEGER NOT NULL REFERENCES terms(term_id),
    credit_hours  INTEGER NOT NULL,
    major         TEXT    NOT NULL,
    class_level   TEXT    NOT NULL CHECK (class_level IN
                    ('Freshman','Sophomore','Junior','Senior')),
    term_gpa      NUMERIC(3,2),
    graduated     BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (student_id, term_id)
);

CREATE TABLE courses (
    course_id     SERIAL PRIMARY KEY,
    subject_code  TEXT    NOT NULL,
    course_number TEXT    NOT NULL,
    title         TEXT    NOT NULL,
    credit_hours  INTEGER NOT NULL,
    is_gateway    BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE course_enrollments (
    student_id INTEGER NOT NULL REFERENCES students(student_id),
    term_id    INTEGER NOT NULL REFERENCES terms(term_id),
    course_id  INTEGER NOT NULL REFERENCES courses(course_id),
    grade      TEXT    NOT NULL,
    PRIMARY KEY (student_id, term_id, course_id)
);

CREATE TABLE financial_aid (
    student_id  INTEGER NOT NULL REFERENCES students(student_id),
    term_id     INTEGER NOT NULL REFERENCES terms(term_id),
    aid_type    TEXT    NOT NULL,
    amount      NUMERIC(8,2) NOT NULL,
    PRIMARY KEY (student_id, term_id, aid_type)
);

CREATE INDEX idx_enroll_term    ON enrollments(term_id);
CREATE INDEX idx_enroll_student ON enrollments(student_id);
CREATE INDEX idx_ce_course      ON course_enrollments(course_id);
"""

with engine.begin() as conn:
    for statement in SCHEMA.strip().split(";"):
        if statement.strip():
            conn.execute(text(statement))

print("schema created")
