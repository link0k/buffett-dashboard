from sqlalchemy import Column, String, Integer, Float
from app.database import Base

class Portfolio(Base):
    __tablename__ = "portfolio"
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String, unique=True)
    shares = Column(Float)
    cost_price = Column(Float)
    added_at = Column(Integer)