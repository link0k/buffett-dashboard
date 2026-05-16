from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.stock import Stock
from app.models.daily_metric import DailyMetric
from app.data.yfinance_client import YFinanceClient
from app.data.akshare_client import AkshareClient
from app.services.dcf_engine import calculate_dcf, get_dcf_margin
from app.services.scoring import score_moat_rules, calculate_overall_score
from typing import Optional
from datetime import date

router = APIRouter()
yfc = YFinanceClient()
akc = AkshareClient()

@router.get("/api/stocks")
def list_stocks(market: Optional[str] = None, limit: int = Query(50, le=200), db: Session = Depends(get_db)):
    query = db.query(Stock, DailyMetric).join(DailyMetric, Stock.symbol == DailyMetric.symbol)
    if market:
        query = query.filter(Stock.market == market)
    results = query.order_by(DailyMetric.score_overall.desc()).limit(limit).all()
    return [{"symbol": s.symbol, "name": s.name, "market": s.market, "close": m.close,
             "pe_ratio": m.pe_ratio, "roic": m.roic, "score_overall": m.score_overall}
            for s, m in results]

@router.get("/api/stock/{symbol}")
def get_stock(symbol: str, db: Session = Depends(get_db)):
    stock = db.query(Stock).filter(Stock.symbol == symbol).first()
    if not stock:
        return {"error": "Stock not found"}
    m = db.query(DailyMetric).filter(DailyMetric.symbol == symbol).order_by(DailyMetric.date.desc()).first()
    if not m:
        return {"error": "No metrics found"}
    return {"symbol": stock.symbol, "name": stock.name, "market": stock.market, "sector": stock.sector,
            "close": m.close, "pe_ratio": m.pe_ratio, "roic": m.roic, "score_overall": m.score_overall,
            "score_moat": m.score_moat, "dcf_value": m.dcf_value}

@router.post("/api/stocks/{symbol}/refresh")
def refresh_stock(symbol: str, db: Session = Depends(get_db)):
    client = akc if (symbol.endswith(".SH") or symbol.endswith(".SZ")) else yfc
    info = client.get_stock_info(symbol)
    financials = client.get_financials(symbol)
    prices = client.get_daily_price(symbol, 365)
    current_price = prices[-1]["close"] if prices else 0
    fcf_history = [financials.get("fcf", 0)] if financials else [0]
    dcf_value = calculate_dcf(fcf_history) if fcf_history[0] else 0
    dcf_margin = get_dcf_margin(current_price, dcf_value)
    revenue = financials.get("revenue", 1) or 1
    net_income = financials.get("net_income", 0) or 0
    metrics_dict = {
        "gross_margin": (revenue - net_income) / revenue if revenue else 0,
        "net_margin": net_income / revenue if revenue else 0,
        "roic": financials.get("roic", 0),
        "revenue_growth": 0.08,
    }
    moat_score = score_moat_rules(metrics_dict)
    overall = calculate_overall_score(dcf_margin, metrics_dict["roic"], moat_score, metrics_dict["revenue_growth"])
    stock = db.query(Stock).filter(Stock.symbol == symbol).first()
    if not stock:
        stock = Stock(symbol=symbol, market=info.get("market",""), name=info.get("name",""), sector=info.get("sector",""))
        db.add(stock)
    m = DailyMetric(symbol=symbol, date=date.today(), close=current_price, pe_ratio=0, roic=metrics_dict["roic"],
                    fcf=fcf_history[0], dcf_value=dcf_value, score_overall=overall["overall"], score_moat=moat_score)
    db.add(m)
    db.commit()
    return {"status": "ok", "score_overall": overall["overall"]}
