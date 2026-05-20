from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.watchlist import Watchlist
from app.models.stock import Stock
from app.models.daily_metric import DailyMetric
from app.data.akshare_client import AkshareClient
from app.services.dcf_engine import calculate_dcf, get_dcf_margin
from app.services.scoring import score_moat_rules, calculate_overall_score
from datetime import date, datetime
import time

router = APIRouter()
akc = AkshareClient()
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

@router.get("/api/watchlist")
def get_watchlist(db: Session = Depends(get_db)):
    items = db.query(Watchlist).order_by(Watchlist.added_at.desc()).all()
    symbols = [r.symbol for r in items]

    results = []
    for sym in symbols:
        stock = db.query(Stock).filter(Stock.symbol == sym).first()
        metric = db.query(DailyMetric).filter(DailyMetric.symbol == sym).order_by(DailyMetric.date.desc()).first()
        name = stock.name if stock and stock.name else _get_stock_name(sym)

        current_price = 0
        if stock and metric and metric.close and metric.close > 0:
            prices = akc.get_daily_price(sym, 5)
            if prices:
                current_price = prices[-1]["close"]
            else:
                current_price = metric.close
        elif stock and metric:
            current_price = metric.close

        if stock and metric:
            results.append({
                "symbol": sym, "name": name, "market": stock.market or "CN",
                "close": current_price, "pe_ratio": metric.pe_ratio, "roic": metric.roic or 0,
                "score_overall": metric.score_overall, "score_moat": metric.score_moat or 0,
                "dcf_value": metric.dcf_value or 0
            })
        elif stock:
            results.append({"symbol": sym, "name": name, "market": stock.market or "CN", "close": 0, "pe_ratio": 0, "roic": 0, "score_overall": 0, "score_moat": 0, "dcf_value": 0})
        else:
            results.append({"symbol": sym, "name": name, "market": "CN", "close": 0, "pe_ratio": 0, "roic": 0, "score_overall": 0, "score_moat": 0, "dcf_value": 0})
    return results

@router.post("/api/watchlist/{symbol}")
def add_to_watchlist(symbol: str, db: Session = Depends(get_db)):
    existing = db.query(Watchlist).filter(Watchlist.symbol == symbol).first()
    name = _get_stock_name(symbol)
    if not existing:
        item = Watchlist(symbol=symbol, added_at=int(time.time()))
        db.add(item)

        stock = db.query(Stock).filter(Stock.symbol == symbol).first()
        if not stock:
            stock = Stock(symbol=symbol, market="CN", name=name, sector="")
            db.add(stock)
        elif not stock.name:
            stock.name = name

        db.commit()
    return {"status": "ok", "name": name}

@router.delete("/api/watchlist/{symbol}")
def remove_from_watchlist(symbol: str, db: Session = Depends(get_db)):
    item = db.query(Watchlist).filter(Watchlist.symbol == symbol).first()
    if item:
        db.delete(item)
        db.commit()
    return {"status": "ok"}

@router.post("/api/watchlist/{symbol}/refresh")
def refresh_watchlist_stock(symbol: str, db: Session = Depends(get_db)):
    try:
        info = akc.get_stock_info(symbol)
        financials = akc.get_financials(symbol)
        prices = akc.get_daily_price(symbol, 365)
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
            stock = Stock(symbol=symbol, market=info.get("market","CN"), name=_get_stock_name(symbol), sector=info.get("sector",""))
            db.add(stock)
        elif not stock.name:
            stock.name = _get_stock_name(symbol)
        db.commit()

        m = db.query(DailyMetric).filter(DailyMetric.symbol == symbol).order_by(DailyMetric.date.desc()).first()
        if m:
            m.close = current_price
            m.dcf_value = dcf_value
            m.score_overall = overall["overall"]
            m.score_moat = moat_score
            m.roic = metrics_dict["roic"]
            db.commit()
        else:
            m = DailyMetric(symbol=symbol, date=date.today(), close=current_price, pe_ratio=0, roic=metrics_dict["roic"],
                            fcf=fcf_history[0], dcf_value=dcf_value, score_overall=overall["overall"], score_moat=moat_score)
            db.add(m)
            db.commit()

        return {"status": "ok", "score_overall": overall["overall"]}
    except Exception as e:
        return {"status": "error", "message": str(e)}