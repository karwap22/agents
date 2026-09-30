"""Read PostgreSQL catalog metadata with psql."""

import csv
import io
import os
import shutil
import subprocess

from dotenv import load_dotenv
from tracing import trace


def query(sql):
    trace("postgres_query_started")
    load_dotenv()
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("Set DATABASE_URL in .env to a PostgreSQL connection URL.")
    if not shutil.which("psql"):
        raise ValueError("psql is required but was not found on PATH.")
    try:
        result = subprocess.run(
            ["psql", database_url, "--csv", "-v", "ON_ERROR_STOP=1", "-c", sql],
            check=True, capture_output=True, text=True, timeout=30,
        )
    except subprocess.CalledProcessError as error:
        raise ValueError(error.stderr.strip() or "PostgreSQL query failed.") from error
    except subprocess.TimeoutExpired as error:
        raise ValueError("PostgreSQL query timed out after 30 seconds.") from error
    rows = list(csv.DictReader(io.StringIO(result.stdout)))
    trace("postgres_query_completed", rows=len(rows))
    return rows


def literal(value):
    return "'" + value.replace("'", "''") + "'"


def list_schemas():
    return query("""
        SELECT schema_name
        FROM information_schema.schemata
        WHERE schema_name NOT LIKE 'pg_%' AND schema_name <> 'information_schema'
        ORDER BY schema_name
    """)


def list_tables(schema):
    return query(f"""
        SELECT table_name, COALESCE(obj_description((quote_ident(table_schema) || '.' || quote_ident(table_name))::regclass), '') AS description
        FROM information_schema.tables
        WHERE table_schema = {literal(schema)} AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)


def describe_table(schema, table):
    columns = query(f"""
        SELECT column_name AS name, data_type AS type, is_nullable = 'YES' AS nullable,
               column_default AS default, COALESCE(col_description((quote_ident(table_schema) || '.' || quote_ident(table_name))::regclass, ordinal_position), '') AS description
        FROM information_schema.columns
        WHERE table_schema = {literal(schema)} AND table_name = {literal(table)}
        ORDER BY ordinal_position
    """)
    if not columns:
        raise ValueError(f"Table {schema}.{table} was not found.")
    primary_key = query(f"""
        SELECT kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
        WHERE tc.table_schema = {literal(schema)} AND tc.table_name = {literal(table)} AND tc.constraint_type = 'PRIMARY KEY'
        ORDER BY kcu.ordinal_position
    """)
    foreign_keys = query(f"""
        SELECT kcu.column_name, ccu.table_schema || '.' || ccu.table_name || '.' || ccu.column_name AS references
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu ON ccu.constraint_name = tc.constraint_name AND ccu.table_schema = tc.table_schema
        WHERE tc.table_schema = {literal(schema)} AND tc.table_name = {literal(table)} AND tc.constraint_type = 'FOREIGN KEY'
        ORDER BY kcu.ordinal_position
    """)
    return {"name": f"{schema}.{table}", "columns": columns, "primary_key": [key["column_name"] for key in primary_key], "foreign_keys": foreign_keys}
