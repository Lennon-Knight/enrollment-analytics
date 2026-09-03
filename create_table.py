import os
from sqlalchemy import create_engine, text

DB_URL = f"postgresql+psycopg://seu_analytics:{os.environ['PGPASSWORD']}@localhost:5432/seu_enrollment"
engine = create_engine(DB_URL)

with engine.begin() as conn:
    conn.execute(text("DROP TABLE IF EXISTS connection_test;"))
    conn.execute(text("""
        CREATE TABLE connection_test (
            id SERIAL PRIMARY KEY,
            note TEXT
        );
    """))
    conn.execute(text("INSERT INTO connection_test (note) VALUES ('written from python');"))

print("table created")
