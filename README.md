<<<<<<< HEAD
# Higher-Ed Enrollment Analytics

A PostgreSQL database modeling eight cohorts of student enrollment,
with SQL analyses of retention, graduation rates, and course DFW rates
following IPEDS definitions.

## Stack
PostgreSQL 16, Python 3.12, SQLAlchemy, psycopg, pandas

## Setup
1. Create a database and role
2. `python seu_schema.py` — builds the tables
3. `python seu_data.py` — generates synthetic data
4. Queries live in `queries/`

Data is synthetic. Patterns built into the generator are documented
in `assumptions.md`, which serves as ground truth for validating
the analytical queries.

## Status
In progress — schema and generation complete, queries underway.
=======
# enrollment-analytics
>>>>>>> 5a912d5165e0892bb137adc40465145f9625a3c1
