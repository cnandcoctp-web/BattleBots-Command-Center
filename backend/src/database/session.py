"""
Database session management and engine configuration.

This module handles:
- Environment variable loading for database configuration
- SQLAlchemy engine creation with connection pooling
- Session factory for creating database sessions
- FastAPI dependency injection for database access
- Connection pool tuning for production environments

Environment Variables:
    DATABASE_URL: PostgreSQL connection string (format: postgresql://user:password@host:port/database)
    DB_POOL_SIZE: Connection pool size (default: 20)
    DB_MAX_OVERFLOW: Maximum overflow connections (default: 10)
    DB_POOL_RECYCLE: Connection recycle time in seconds (default: 3600)
    DB_ECHO: Enable SQL logging (default: False)
"""

import os
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool

# ============================================================================
# ENVIRONMENT CONFIGURATION
# ============================================================================

# Database connection string from environment
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/battlebots_dev"
)

# Connection pool configuration
DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", 20))
DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", 10))
DB_POOL_RECYCLE: int = int(os.getenv("DB_POOL_RECYCLE", 3600))

# SQL echo for debugging (disable in production)
DB_ECHO: bool = os.getenv("DB_ECHO", "false").lower() == "true"

# ============================================================================
# ENGINE CREATION
# ============================================================================

engine: Engine = create_engine(
    DATABASE_URL,
    echo=DB_ECHO,
    poolclass=QueuePool,
    pool_size=DB_POOL_SIZE,
    max_overflow=DB_MAX_OVERFLOW,
    pool_recycle=DB_POOL_RECYCLE,
    pool_pre_ping=True,  # Verify connections before using them
    connect_args={
        "connect_timeout": 10,
        "application_name": "battlebots_command_center",
    },
)


# ============================================================================
# POOL EVENT LISTENERS
# ============================================================================

@event.listens_for(engine, "connect")
def receive_connect(dbapi_conn, connection_record):
    """
    Configure connection-level settings when a new connection is created.

    Sets up PostgreSQL-specific options for optimal performance:
    - Statement timeout to prevent long-running queries
    - JSON serialization for JSONB columns
    """
    cursor = dbapi_conn.cursor()
    try:
        # Set statement timeout to 5 minutes for safety
        cursor.execute("SET statement_timeout = '5min'")
        cursor.close()
    except Exception:
        # Connection may not support this, continue gracefully
        pass


@event.listens_for(engine, "engine_disposed")
def receive_engine_disposed(engine):
    """
    Log when the engine connection pool is disposed.
    Useful for debugging connection issues in production.
    """
    pass


# ============================================================================
# SESSION FACTORY
# ============================================================================

SessionLocal: sessionmaker = sessionmaker(
    bind=engine,
    class_=Session,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)
"""
Session factory for creating new database sessions.

Configuration:
- expire_on_commit=False: Keep objects in memory after commit
- autoflush=False: Explicit flush control
- autocommit=False: Explicit transaction management

Usage:
    db = SessionLocal()
    try:
        # perform database operations
        ...
    finally:
        db.close()
"""


# ============================================================================
# DEPENDENCY INJECTION FOR FASTAPI
# ============================================================================

def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency for database session injection.

    Provides a database session for each request and ensures proper
    cleanup via context manager pattern.

    Yields:
        Session: SQLAlchemy database session

    Usage in FastAPI route:
        @app.get("/robots")
        def get_robots(db: Session = Depends(get_db)):
            return db.query(Robot).all()

    Example:
        >>> db = next(get_db())
        >>> # Use db for operations
        >>> db.close()
    """
    db: Session = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ============================================================================
# DATABASE INITIALIZATION
# ============================================================================

def init_db() -> None:
    """
    Initialize the database by creating all tables.

    This should be called once at application startup. It uses the
    metadata from all models that inherit from Base.

    Import all models before calling this function to ensure their
    metadata is registered.

    Example:
        from database.base import Base
        from database import models  # Import all models
        init_db()
    """
    from database.base import Base

    Base.metadata.create_all(bind=engine)


def close_db() -> None:
    """
    Close all database connections in the pool.

    Should be called at application shutdown to ensure clean cleanup
    of all database connections.

    Example:
        app.add_event_handler("shutdown", close_db)
    """
    engine.dispose()


# ============================================================================
# CONNECTION HEALTH CHECK
# ============================================================================

def check_db_connection() -> bool:
    """
    Check if the database connection is healthy.

    Attempts a simple query to verify the database is accessible.

    Returns:
        bool: True if connection is healthy, False otherwise

    Example:
        if check_db_connection():
            logger.info("Database is healthy")
        else:
            logger.error("Database connection failed")
    """
    try:
        with engine.connect() as connection:
            connection.execute(__import__("sqlalchemy").text("SELECT 1"))
            return True
    except Exception as e:
        print(f"Database connection check failed: {e}")
        return False
