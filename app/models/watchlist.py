from sqlalchemy import Column, String, Integer
from app.database import Base

class Watchlist(Base):
    __tablename__ = "watchlist"
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String, unique=True)
    added_at = Column(Integer)