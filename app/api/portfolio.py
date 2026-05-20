from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.portfolio import Portfolio
from app.models.stock import Stock
from app.models.watchlist import Watchlist
from app.data.akshare_client import AkshareClient
from app.data.yfinance_client import YFinanceClient
import time

router = APIRouter()
akc = AkshareClient()
yfc = YFinanceClient()
_a_share_cache = None
_a_share_cache_time = 0

def _get_a_share_list():
    global _a_share_cache, _a_share_cache_time
    if _a_share_cache is None or (time.time() - _a_share_cache_time) > 3600:
        try:
            import akshare as ak
            df = ak.stock_info_a_code_name()
            _a_share_cache = [
                {"symbol": r["code"] + ".SH" if r["code"].startswith(("6","9")) else r["code"] + ".SZ",
                 "name": r["name"], "market": "CN"}
                for _, r in df.iterrows()
            ]
        except Exception:
            _a_share_cache = []
        _a_share_cache_time = time.time()
    return _a_share_cache

def _get_stock_name(symbol):
    all_stocks = _get_a_share_list()
    for s in all_stocks:
        if s["symbol"] == symbol:
            return s["name"]
    return symbol

@router.get("/api/portfolio")
def get_portfolio(db: Session = Depends(get_db)):
    items = db.query(Portfolio).order_by(Portfolio.added_at.desc()).all()
    results = []
    total_cost = 0
    total_value = 0
    for item in items:
        stock = db.query(Stock).filter(Stock.symbol == item.symbol).first()
        name = stock.name if stock and stock.name else _get_stock_name(item.symbol)
        shares = item.shares
        cost_price = item.cost_price
        cost_total = shares * cost_price

        prices = akc.get_daily_price(item.symbol, 5) if (item.symbol.endswith(".SH") or item.symbol.endswith(".SZ")) else []
        if prices:
            current_price = prices[-1]["close"]
        else:
            current_price = 0

        current_value = shares * current_price
        gain = current_value - cost_total
        gain_pct = (gain / cost_total * 100) if cost_total > 0 else 0

        total_cost += cost_total
        total_value += current_value

        results.append({
            "symbol": item.symbol, "name": name, "shares": shares,
            "cost_price": cost_price, "cost_total": cost_total,
            "current_price": current_price, "current_value": current_value,
            "gain": gain, "gain_pct": gain_pct
        })

    total_gain = total_value - total_cost
    total_gain_pct = (total_gain / total_cost * 100) if total_cost > 0 else 0
    return {
        "items": results,
        "summary": {
            "total_cost": total_cost,
            "total_value": total_value,
            "total_gain": total_gain,
            "total_gain_pct": total_gain_pct
        }
    }

@router.post("/api/portfolio")
def add_portfolio(symbol: str = Query(...), shares: float = Query(...), cost_price: float = Query(...), db: Session = Depends(get_db)):
    existing = db.query(Portfolio).filter(Portfolio.symbol == symbol).first()
    if existing:
        existing.shares = shares
        existing.cost_price = cost_price
        db.commit()
        return {"status": "ok", "symbol": symbol}
    item = Portfolio(symbol=symbol, shares=shares, cost_price=cost_price, added_at=int(time.time()))
    db.add(item)

    stock = db.query(Stock).filter(Stock.symbol == symbol).first()
    if not stock:
        stock = Stock(symbol=symbol, market="CN", name=_get_stock_name(symbol), sector="")
        db.add(stock)
    elif not stock.name:
        stock.name = _get_stock_name(symbol)
    db.commit()
    return {"status": "ok", "symbol": symbol}

@router.put("/api/portfolio/{symbol}")
def update_portfolio(symbol: str, shares: float, cost_price: float, db: Session = Depends(get_db)):
    item = db.query(Portfolio).filter(Portfolio.symbol == symbol).first()
    if not item:
        return {"status": "error", "message": "not found"}
    item.shares = shares
    item.cost_price = cost_price
    db.commit()
    return {"status": "ok"}

@router.delete("/api/portfolio/{symbol}")
def delete_portfolio(symbol: str, db: Session = Depends(get_db)):
    item = db.query(Portfolio).filter(Portfolio.symbol == symbol).first()
    if item:
        db.delete(item)
        db.commit()
    return {"status": "ok"}