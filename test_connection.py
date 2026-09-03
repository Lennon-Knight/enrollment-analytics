import os
from sqlalchemy import create_engine, text

DB_URL = f"postgresql+psycopg://seu_analytics:{os.environ['PGPASSWORD']}@localhost:5432/seu_enrollment"
engine = create_engine(DB_URL)

with engine.connect() as conn:
    version = conn.execute(text("SELECT version();")).scalar()
    print(version)

