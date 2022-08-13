"""sqlalchemy mapping for recordings"""

from sqlalchemy import Column, Integer, String, Sequence, DateTime, Float
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class Recording(Base):
    """Recording Mapping"""
    __tablename__ = 'recordings'

    id = Column(Integer, Sequence("user_id_seq"), primary_key=True)
    path = Column(String)
    length = Column(Float)
    size = Column(Integer)
    timestamp = Column(DateTime(timezone=False), server_default=func.now())
    name = Column(String)
