import os
from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import logging  

logger = logging.getLogger("pdf2md.db.base") 

STORAGE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "storage")
)
os.makedirs(STORAGE_DIR, exist_ok=True)

DATABASE_URL = f"sqlite:///{os.path.join(STORAGE_DIR, 'pdf2md.db')}"

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False} 
)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if "sqlite" in DATABASE_URL:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA busy_timeout = 5000;")
            cursor.execute("PRAGMA synchronous = NORMAL;")
        finally:
            cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def init_db():
    """Initializes the database and creates tables if they don't exist."""
    try:
        from . import models

        logger.info("Initializing database and creating tables...")
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully (if they didn't exist).")
    except Exception as e:
        logger.error(f"Error during database initialization: {e}", exc_info=True)
        raise


def get_db():
    """Dependency for database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
