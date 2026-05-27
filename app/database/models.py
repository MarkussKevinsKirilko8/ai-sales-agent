from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class SeenUser(Base):
    __tablename__ = "seen_users"

    chat_id = Column(BigInteger, primary_key=True)


class ScrapedPage(Base):
    __tablename__ = "scraped_pages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(50), nullable=False)  # "hilmabiocare" or "hilmabiocareshop"
    url = Column(String(500), unique=True, nullable=False)
    title = Column(String(500))
    content = Column(Text)
    image_url = Column(String(500))
    page_type = Column(String(50))  # "product", "category", "info", etc.
    scraped_at = Column(DateTime, default=datetime.utcnow)
