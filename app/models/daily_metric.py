from sqlalchemy import Column, String, Float, Date, Integer
from app.database import Base

class DailyMetric(Base):
    __tablename__ = "daily_metrics"
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String)
    date = Column(Date)
    close = Column(Float)
    pe_ratio = Column(Float)
    pb_ratio = Column(Float)
    roic = Column(Float)
    revenue_growth = Column(Float)
    net_margin = Column(Float)
    gross_margin = Column(Float)
    fcf = Column(Float)
    dcf_value = Column(Float)
    score_overall = Column(Float)
    score_moat = Column(Float)
