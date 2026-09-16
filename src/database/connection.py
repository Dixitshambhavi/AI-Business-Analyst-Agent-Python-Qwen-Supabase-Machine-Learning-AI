import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv(override=True)

# ============================================================
# DATABASE CONFIGURATION
# ============================================================

DB_HOST = os.getenv("SUPABASE_DB_HOST")
DB_PORT = os.getenv("SUPABASE_DB_PORT", "5432")
DB_NAME = os.getenv("SUPABASE_DB_NAME", "postgres")
DB_USER = os.getenv("SUPABASE_DB_USER", "postgres")
DB_PASSWORD = os.getenv("SUPABASE_DB_PASSWORD")


# ============================================================
# VALIDATE ENVIRONMENT VARIABLES
# ============================================================

required_variables = {
    "SUPABASE_DB_HOST": DB_HOST,
    "SUPABASE_DB_PORT": DB_PORT,
    "SUPABASE_DB_NAME": DB_NAME,
    "SUPABASE_DB_USER": DB_USER,
    "SUPABASE_DB_PASSWORD": DB_PASSWORD,
}

missing_variables = [
    name
    for name, value in required_variables.items()
    if not value
]

if missing_variables:
    raise ValueError(
        f"Missing environment variables: {missing_variables}"
    )


# ============================================================
# CREATE DATABASE URL
# ============================================================

DATABASE_URL = URL.create(
    drivername="postgresql+psycopg2",
    username=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=int(DB_PORT),
    database=DB_NAME,
)


# ============================================================
# CREATE SQLALCHEMY ENGINE
# ============================================================

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=1800,
)


# ============================================================
# TEST DATABASE CONNECTION
# ============================================================

def test_connection():

    try:

        with engine.connect() as connection:

            result = connection.execute(
                text("SELECT version();")
            )

            version = result.scalar()

            print()
            print("=" * 70)
            print("SUPABASE DATABASE CONNECTION")
            print("=" * 70)

            print("✓ Connection successful")
            print(f"PostgreSQL version: {version}")

            print("=" * 70)
            print()

            return True

    except Exception as error:

        print()
        print("=" * 70)
        print("SUPABASE DATABASE CONNECTION FAILED")
        print("=" * 70)

        print(f"Error: {error}")

        print("=" * 70)
        print()

        return False


# ============================================================
# RUN CONNECTION TEST
# ============================================================

if __name__ == "__main__":

    test_connection()