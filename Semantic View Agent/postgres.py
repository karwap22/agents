"""PostgreSQL metadata and guarded read-only query tools."""

import os
import re
import psycopg
from psycopg.rows import dict_row
from functools import lru_cache
from psycopg_pool import ConnectionPool, PoolTimeout

from dotenv import load_dotenv
from tracing import trace


MAX_ROWS = 200
MAX_SQL_LENGTH = 20_000
QUERY_TIMEOUT_SECONDS = 10
FORBIDDEN_KEYWORDS = {
    "alter", "analyze", "begin", "call", "cluster", "commit", "copy", "create",
    "deallocate", "delete", "discard", "do", "drop", "execute", "grant", "insert",
    "listen", "load", "lock", "merge", "notify", "prepare", "refresh", "reindex",
    "reset", "revoke", "rollback", "savepoint", "set", "show", "truncate", "unlisten",
    "update", "vacuum",
}


def database_url():
    load_dotenv()
    url = os.getenv("DATABASE_URL")
    if not url:
        raise ValueError("Set DATABASE_URL in .env to a PostgreSQL connection URL.")
    return url

@lru_cache(maxsize=1)
def get_pool():
    return ConnectionPool(
        conninfo=database_url(),
        min_size=1,
        max_size=10,
        timeout=5,
        open=True,
        kwargs={
            "autocommit": True,
            "row_factory": dict_row,
            "options": "-c default_transaction_read_only=on",
        },
    )

def pool_stats():
    return get_pool().get_stats()

def database_query(sql, timeout=30):
    trace(
        "postgres_query_started",
        sql_length=len(sql),
        timeout_seconds=timeout,
    )

    try:
        with get_pool().connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('statement_timeout', %s, false)",
                    (str(timeout * 1000),),
                )
                cursor.execute(sql)

                columns = (
                    [column.name for column in cursor.description]
                    if cursor.description
                    else []
                )
                rows = cursor.fetchall() if cursor.description else []
    except PoolTimeout as error:
        raise ValueError("Database connection pool is busy.") from error
    except psycopg.errors.QueryCanceled as error:
        raise ValueError("PostgreSQL query timed out.") from error
    except psycopg.Error as error:
        raise ValueError(str(error).strip() or "PostgreSQL query failed.") from error

    trace("postgres_query_completed", rows=len(rows))
    return columns, rows

def query(sql):
    return database_query(sql)[1]


def literal(value):
    return "'" + value.replace("'", "''") + "'"


def sql_tokens(sql):
    """Return tokens outside comments and string literals."""
    clean, index, quote = [], 0, None
    while index < len(sql):
        pair = sql[index:index + 2]
        if quote:
            if quote == "'" and sql[index] == "'" and sql[index + 1:index + 2] == "'":
                clean.append("  ")
                index += 2
            elif sql[index] == quote:
                quote = None
                clean.append(" ")
                index += 1
            else:
                clean.append(" ")
                index += 1
        elif pair == "--":
            end = sql.find("\n", index)
            end = len(sql) if end == -1 else end
            clean.append(" " * (end - index))
            index = end
        elif pair == "/*":
            end = sql.find("*/", index + 2)
            if end == -1:
                raise ValueError("SQL contains an unclosed block comment.")
            clean.append(" " * (end + 2 - index))
            index = end + 2
        elif sql[index] in {"'", '"'}:
            quote = sql[index]
            clean.append(" ")
            index += 1
        else:
            clean.append(sql[index])
            index += 1
    if quote:
        raise ValueError("SQL contains an unclosed quoted value.")
    return re.findall(r"[A-Za-z_][A-Za-z0-9_$]*|;", "".join(clean).lower())


def validate_read_only_sql(sql):
    sql = sql.strip()
    if not sql or len(sql) > MAX_SQL_LENGTH:
        raise ValueError(f"SQL must be between 1 and {MAX_SQL_LENGTH} characters.")
    tokens = sql_tokens(sql)
    if tokens and tokens[-1] == ";":
        tokens.pop()
    if not tokens or ";" in tokens:
        raise ValueError("Only one SQL statement is allowed.")
    if tokens[0] not in {"select", "with"}:
        raise ValueError("Only SELECT or WITH queries are allowed.")
    blocked = sorted(set(tokens) & FORBIDDEN_KEYWORDS)
    if blocked:
        raise ValueError(f"Blocked SQL keyword(s): {', '.join(blocked)}.")
    if "into" in tokens or "for" in tokens and any(token in {"update", "share"} for token in tokens):
        raise ValueError("SELECT INTO and row-locking queries are not allowed.")
    return sql.rstrip(";")


def run_read_only_query(sql):
    sql = validate_read_only_sql(sql)
    trace("read_only_query_validated", sql_length=len(sql), max_rows=MAX_ROWS)
    columns, rows = database_query(f"SELECT * FROM ({sql}) AS agent_result LIMIT {MAX_ROWS + 1}", QUERY_TIMEOUT_SECONDS)
    truncated = len(rows) > MAX_ROWS
    return {"columns": columns, "rows": rows[:MAX_ROWS], "row_count": min(len(rows), MAX_ROWS), "truncated": truncated, "max_rows": MAX_ROWS}


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
