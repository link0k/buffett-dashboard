from sqlalchemy import Column, String, DateTime
from app.database import Base

class Stock(Base):
    __tablename__ = "stocks"
    symbol = Column(String, primary_key=True)
    market = Column(String)
    name = Column(String)
    sector = Column(String)
    last_updated = Column(DateTime)
