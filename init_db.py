"""
init_db.py — Initializes the MySQL database schema on application startup.

Reads schema.sql and executes each statement against the MySQL server.
Connects without a target database first so it can run the
CREATE DATABASE statement, then switches to the correct database before
creating tables.  The database name is taken from the MYSQLDATABASE
environment variable (falling back to the name hard-coded in schema.sql).
"""

import os
import re
import logging

import mysql.connector
from mysql.connector import Error

logger = logging.getLogger(__name__)


def _get_connection_params(with_database: bool = False) -> dict:
    """Build mysql.connector connection kwargs from environment variables."""
    params = {
        "host":     os.getenv("DB_HOST")  or os.getenv("MYSQLHOST")     or "localhost",
        "user":     os.getenv("DB_USER")  or os.getenv("MYSQLUSER")     or "root",
        "password": os.getenv("DB_PASS")  or os.getenv("MYSQLPASSWORD") or os.getenv("MYSQL_ROOT_PASSWORD") or "",
        "port": int(os.getenv("DB_PORT")  or os.getenv("MYSQLPORT")     or 3306),
    }
    if with_database:
        db = (
            os.getenv("DB_NAME")
            or os.getenv("MYSQLDATABASE")
            or os.getenv("MYSQL_DATABASE")
            or "agenda_inteligente"
        )
        params["database"] = db
    return params


def _resolve_db_name() -> str:
    """
    Return the target database name.

    Prefers the MYSQLDATABASE / DB_NAME environment variable so that
    Railway-provisioned databases (which may use a different name) work
    correctly.  Falls back to 'agenda_inteligente' (the name in schema.sql).
    """
    return (
        os.getenv("DB_NAME")
        or os.getenv("MYSQLDATABASE")
        or os.getenv("MYSQL_DATABASE")
        or "agenda_inteligente"
    )


def _split_statements(sql: str) -> list[str]:
    """
    Split a SQL script into individual statements, stripping comments and
    blank lines.  Handles the USE statement specially so we can replace the
    hard-coded database name with the one from the environment.
    """
    # Remove single-line comments (-- ...) and block comments (/* ... */)
    sql = re.sub(r"--[^\n]*", "", sql)
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)

    statements = []
    for raw in sql.split(";"):
        stmt = raw.strip()
        if stmt:
            statements.append(stmt)
    return statements


def init_db() -> None:
    """
    Create the database (if it does not exist) and run all CREATE TABLE
    statements from schema.sql.

    Strategy:
      1. Connect to MySQL *without* selecting a database so we can issue
         CREATE DATABASE IF NOT EXISTS safely.
      2. Rewrite any USE / CREATE DATABASE statements in the script to use
         the environment-configured database name instead of the hard-coded
         one from schema.sql.
      3. Execute each statement; log but do not raise on non-fatal errors
         (e.g. table already exists) so repeated startups are safe.
    """
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")

    if not os.path.exists(schema_path):
        logger.warning("init_db: schema.sql not found at %s — skipping", schema_path)
        return

    target_db = _resolve_db_name()
    logger.info("init_db: initializing database '%s'", target_db)

    try:
        with open(schema_path, "r", encoding="utf-8") as fh:
            raw_sql = fh.read()
    except OSError as exc:
        logger.error("init_db: could not read schema.sql: %s", exc)
        return

    # Replace the hard-coded database name in CREATE DATABASE / USE statements
    # with the environment-configured name so Railway deployments work correctly.
    raw_sql = re.sub(
        r"CREATE\s+DATABASE\s+IF\s+NOT\s+EXISTS\s+`?\w+`?",
        f"CREATE DATABASE IF NOT EXISTS `{target_db}`",
        raw_sql,
        flags=re.IGNORECASE,
    )
    raw_sql = re.sub(
        r"\bUSE\s+`?\w+`?",
        f"USE `{target_db}`",
        raw_sql,
        flags=re.IGNORECASE,
    )

    statements = _split_statements(raw_sql)

    # Phase 1: connect without a database to run CREATE DATABASE + USE
    try:
        conn = mysql.connector.connect(**_get_connection_params(with_database=False))
    except Error as exc:
        logger.error("init_db: could not connect to MySQL: %s", exc)
        return

    try:
        cursor = conn.cursor()
        for stmt in statements:
            try:
                cursor.execute(stmt)
                # Consume any results so the connection stays clean
                try:
                    cursor.fetchall()
                except Exception:
                    pass
            except Error as exc:
                # 1050 = table already exists, 1007 = database already exists —
                # both are harmless on repeated startups.
                if exc.errno in (1050, 1007):
                    logger.debug("init_db: skipping (already exists): %s", exc.msg)
                else:
                    logger.warning("init_db: statement error (continuing): %s", exc)
        conn.commit()
        logger.info("init_db: schema initialization complete for database '%s'", target_db)
    except Error as exc:
        logger.error("init_db: unexpected error during schema execution: %s", exc)
    finally:
        try:
            cursor.close()
        except Exception:
            pass
        conn.close()
