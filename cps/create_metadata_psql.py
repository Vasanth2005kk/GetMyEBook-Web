import os
import subprocess
import urllib.parse
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError
from dotenv import load_dotenv

from . import logger

log = logger.create()

# ---------------------------
# Load environment variables
# ---------------------------
load_dotenv('/home/vasanth/GetMyEBook-Web/.env')

DB_USER     = os.getenv("DB_USERNAME")
DB_PASSWORD = os.getenv("DB_PASSWORD")  # RAW PASSWORD HERE
DB_HOST     = os.getenv("DB_HOST")
DB_PORT     = os.getenv("DB_PORT")
DB_NAME     = os.getenv("DATABASENAME_CALIBRE", "metadatadb")

# SQLITE_PATH = "/home/vasanth/metadata.db"


# ---------------------------
# Auto install pgloader (Linux only)
# ---------------------------
def ensure_pgloader_installed():
    try:
        subprocess.run(["pgloader", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        log.info(f"✔ pgloader already installed.")
    except FileNotFoundError:
        log.info(f"⚠ pgloader not found. Installing...")
        subprocess.run(["sudo", "apt-get", "update", "-y"])
        subprocess.run(["sudo", "apt-get", "install", "-y", "pgloader"])
        log.info(f"✔ pgloader installed successfully.")


# ---------------------------
# Complete migration workflow
# ---------------------------
def migrate_sqlite_to_postgres(SQLITE_PATH):

    # Check if database exists and if tables are empty
    encoded_pw = urllib.parse.quote_plus(DB_PASSWORD)
    POSTGRES_DB_URL = f"postgresql+psycopg2://{DB_USER}:{encoded_pw}@{DB_HOST}:{DB_PORT}/{DB_NAME.lower()}"

    db_engine = create_engine(POSTGRES_DB_URL)
    with db_engine.connect() as conn:
        tables = conn.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema='public';")
        ).fetchall()
        if tables:
            # Check if all tables are empty
            non_empty = False
            for (table_name,) in tables:
                count = conn.execute(text(f"SELECT COUNT(*) FROM \"{table_name}\";")).scalar()
                if count > 0:
                    non_empty = True
                    break
            if non_empty:
                log.info(f"✔ Database '{DB_NAME}' already has data. Migration will not run.")
                return
            else:
                log.info(f"✔ Database '{DB_NAME}' tables are empty. Proceeding with migration.")
        else:
            log.info(f"✔ Database '{DB_NAME}' has no tables. Proceeding with migration.")
    ensure_pgloader_installed()

    # Password encoding for URL
    encoded_pw = urllib.parse.quote_plus(DB_PASSWORD)

    POSTGRES_ADMIN_URL = f"postgresql+psycopg2://{DB_USER}:{encoded_pw}@{DB_HOST}:{DB_PORT}/postgres"
    TARGET_PGLOADER_URL = f"postgresql://{DB_USER}:{encoded_pw}@{DB_HOST}:{DB_PORT}/{DB_NAME.lower()}"

    log.info(f"PostgreSQL Admin URL = { POSTGRES_ADMIN_URL}")
    log.info(f"pgloader Target URL   = { TARGET_PGLOADER_URL}")

    # Create database
    engine = create_engine(POSTGRES_ADMIN_URL, isolation_level="AUTOCOMMIT")

    try:
        with engine.connect() as conn:
            conn.execute(text(f"CREATE DATABASE {DB_NAME};"))
            log.info(f"✔ Database '{DB_NAME}' created.")
    except ProgrammingError as e:
        if 'already exists' in str(e):
            log.info(f"✔ Database '{DB_NAME}' already exists. Proceeding with migration.")
        else:
            log.error(f"⚠ Error creating database: {e}")
            return

    # Run pgloader
    log.info(f"\nRunning migration using pgloader...\n")

    command = [
        "pgloader",
        f"sqlite:///{SQLITE_PATH}",
        TARGET_PGLOADER_URL
    ]

    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    log.info(f"=========== PGLOADER OUTPUT ===========")
    log.info(f"{result.stdout}")
    log.info(f"=========== PGLOADER ERRORS ===========")
    log.info(f"{result.stderr}")
    if result.returncode != 0:
        log.error(f"⚠ pgloader failed with return code {result.returncode}.")
        return

    log.info(f"✔ Migration completed successfully.")


# ---------------------------
# Main
# ---------------------------
if __name__ == "__main__":
    migrate_sqlite_to_postgres()
