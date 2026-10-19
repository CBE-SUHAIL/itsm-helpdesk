"""Run pytest in a fresh temporary PostgreSQL database, preserving demo data.

From backend/: python run_tests.py -q
The configured POSTGRES_USER must be able to CREATE DATABASE (the local Docker
Compose role can). The generated database name is random and never reused.
"""

import os
import subprocess
import sys
from uuid import uuid4

import psycopg
from psycopg import sql

from app.core.config import get_settings


def main() -> int:
    settings = get_settings()
    temporary_db = f"itsm_test_{uuid4().hex[:12]}"
    connection = psycopg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        dbname="postgres",
        autocommit=True,
    )
    created = False
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(temporary_db)))
        created = True
        print(f"Running tests in isolated database {temporary_db}", flush=True)
        environment = {**os.environ, "POSTGRES_DB": temporary_db}
        return subprocess.run(
            [sys.executable, "-m", "pytest", *sys.argv[1:]],
            env=environment,
            check=False,
        ).returncode
    finally:
        try:
            if created:
                with connection.cursor() as cursor:
                    cursor.execute(
                        sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                            sql.Identifier(temporary_db)
                        )
                    )
                print(f"Removed isolated database {temporary_db}", flush=True)
        finally:
            connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
