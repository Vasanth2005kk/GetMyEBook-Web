import os
import subprocess
import urllib.parse
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError
from dotenv import load_dotenv
from .utils import get_env_path, get_project_root

from . import logger , auto_create_threads

log = logger.create()

# ---------------------------
# Load environment variables
# ---------------------------
load_dotenv(get_env_path())

DB_USER     = os.getenv("DB_USERNAME")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST     = os.getenv("DB_HOST")
DB_PORT     = os.getenv("DB_PORT")
DB_NAME     = os.getenv("DATABASENAME_APP")


# ---------------------------
# Auto install pgloader
# ---------------------------
def ensure_pgloader_installed():
    try:
        subprocess.run(["pgloader", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        log.info("✔ pgloader already installed.")
    except FileNotFoundError:
        log.info("⚠ pgloader not found. Installing...")
        subprocess.run(["sudo", "apt-get", "update", "-y"])
        subprocess.run(["sudo", "apt-get", "install", "-y", "pgloader"])
        log.info("✔ pgloader installed successfully.")


# -------------------------------------
# Helper: Create DB
# -------------------------------------
def create_database_if_not_exists():
    # Encode password safely
    encoded_pw = urllib.parse.quote_plus(DB_PASSWORD)

    # Admin DB connection for creating DB
    POSTGRES_ADMIN_URL = (
        f"postgresql+psycopg2://{DB_USER}:{encoded_pw}@{DB_HOST}:{DB_PORT}/postgres"
    )
    
    engine = create_engine(POSTGRES_ADMIN_URL, isolation_level="AUTOCOMMIT")

    try:
        with engine.connect() as conn:
            conn.execute(text(f"CREATE DATABASE {DB_NAME};"))
            log.info(f"✔ Database '{DB_NAME}' created.")
    except ProgrammingError as e:
        if "already exists" in str(e):
            log.info(f"✔ Database '{DB_NAME}' already exists.")
        else:
            log.error(f"⚠ Error creating database: {e}")
            raise


# ---------------------------
# Migration workflow
# ---------------------------
def migrate_sqlite_to_postgres(SQLITE_PATH):
    if not SQLITE_PATH.endswith('.db'):
        SQLITE_PATH = os.path.join(SQLITE_PATH, 'metadata.db')
    log.info(f"SQLite DB Path: {SQLITE_PATH}")
    # Encode password safely
    encoded_pw = urllib.parse.quote_plus(DB_PASSWORD)

    # Admin DB connection for creating DB
    # (We still define this for logging purposes, though creation is handled by helper)
    POSTGRES_ADMIN_URL = (
        f"postgresql+psycopg2://{DB_USER}:{encoded_pw}@{DB_HOST}:{DB_PORT}/postgres"
    )

    # Pgloader target URL (MUST be plain postgresql://)
    TARGET_PGLOADER_URL = (
        f"postgresql://{DB_USER}:{encoded_pw}@{DB_HOST}:{DB_PORT}/{DB_NAME.lower()}"
    )

    log.info(f"PostgreSQL Admin URL = {POSTGRES_ADMIN_URL}")
    log.info(f"pgloader Target URL  = {TARGET_PGLOADER_URL}")

    # Ensure pgloader installed
    ensure_pgloader_installed()

    # -------------------------------------
    # Create database if not exists
    # -------------------------------------
    create_database_if_not_exists()

    # -------------------------------------
    # Run pgloader migration
    # -------------------------------------
    log.info("\nRunning migration using pgloader...\n")

    command = [
        "pgloader",
        f"sqlite:///{SQLITE_PATH}",
        TARGET_PGLOADER_URL
    ]

    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    log.info("=========== PGLOADER OUTPUT ===========")
    log.info(result.stdout)
    log.info("=========== PGLOADER ERRORS ===========")
    log.info(result.stderr)

    if result.returncode != 0:
        error_msg = f"pgloader failed with return code {result.returncode}. Stderr: {result.stderr}"
        log.error(f"⚠ {error_msg}")
        raise Exception(error_msg)

    log.info("✔ Migration completed successfully.")
    auto_create_threads.create_threads()

# ---------------------------
# Main entry
# ---------------------------
# default path
SQLITE_PATH = os.path.join(get_project_root(), 'library/metadata.db')

if __name__ == "__main__":
    migrate_sqlite_to_postgres(SQLITE_PATH)
