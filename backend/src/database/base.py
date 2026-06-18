"""
Base SQLAlchemy declarative base for all database models.

This module provides the declarative base class that all ORM models inherit from.
It uses SQLAlchemy 2.0 style mapping with the declarative_base pattern.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy ORM models.

    All database models should inherit from this class to ensure consistency
    and proper metadata tracking across the application.

    Example:
        class Robot(Base):
            __tablename__ = "robots"
            ...
    """

    pass
