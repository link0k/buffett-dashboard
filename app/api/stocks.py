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
import akshare as ak

router = APIRouter()
yfc = YFinanceClient()
akc = AkshareClient()

def _generate_moat_tags(metrics: dict) -> list:
    tags = []
    gm = metrics.get("gross_margin", 0)
    if gm >= 0.50: tags.append("高毛利率")
    elif gm >= 0.30: tags.append("毛利率较好")
    nm = metrics.get("net_margin", 0)
    if nm >= 0.20: tags.append("高净利率")
    elif nm >= 0.10: tags.append("净利率较好")
    roic = metrics.get("roic", 0)
    if roic >= 0.15: tags.append("高ROIC")
    elif roic >= 0.08: tags.append("ROIC较好")
    rg = metrics.get("revenue_growth", 0)
    if rg >= 0.10: tags.append("高成长")
    elif rg >= 0.05: tags.append("稳定成长")
    if not tags: tags.append("数据不足")
    return tags

def _generate_ai_report(metrics: dict, moat_score: float, overall_score: float, dcf_value: float, current_price: float) -> str:
    parts = []
    if overall_score >= 80: parts.append("综合评分优秀，公司具有强大竞争力，长期投资价值显著。")
    elif overall_score >= 65: parts.append("综合评分良好，公司基本面稳健，具备一定投资价值。")
    elif overall_score >= 50: parts.append("综合评分一般，公司竞争力有待提升，建议持续跟踪。")
    else: parts.append("综合评分较低，需谨慎评估公司基本面风险。")
    if moat_score >= 80: parts.append("护城河评级高，竞争优势明显，盈利能力可持续性强。")
    elif moat_score >= 50: parts.append("护城河中等级别，具有一定竞争优势，但需关注竞争格局变化。")
    else: parts.append("护城河评级一般，竞争优势不够突出，需密切关注行业变化。")
    if dcf_value > 0 and current_price > 0:
        margin = (dcf_value - current_price) / current_price * 100
        if margin > 20: parts.append(f"DCF估值显示当前股价显著低于内在价值（折价{margin:.0f}%），安全边际充足。")
        elif margin > 10: parts.append(f"DCF估值显示股价低于内在价值约{margin:.0f}%，估值具有吸引力。")
        elif margin > 0: parts.append("DCF估值显示股价略低于内在价值，估值合理偏低。")
        elif margin > -10: parts.append("DCF估值显示股价接近内在价值，估值基本合理。")
        else: parts.append(f"DCF估值显示股价高于内在价值（溢价{abs(margin):.0f}%），估值偏贵。")
    roic = metrics.get("roic", 0)
    if roic >= 0.15: parts.append(f"ROIC达{roic*100:.1f}%，资本回报效率优秀，表明公司具备较强的定价权和资产运用能力。")
    elif roic >= 0.08: parts.append(f"ROIC为{roic*100:.1f}%，资本回报处于中等水平。")
    return "".join(parts)

_a_share_cache = None
_a_share_cache_time = 0

def _get_a_share_list():
    global _a_share_cache, _a_share_cache_time
    import time
    if _a_share_cache is None or (time.time() - _a_share_cache_time) > 3600:
        try:
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

@router.get("/api/search")
def search_stocks(q: str = Query(...), market: str = Query("CN"), db: Session = Depends(get_db)):
    if not q or len(q.strip()) < 1:
        return {"query": q, "market": market, "results": []}
    q_lower = q.strip().lower()
    if market == "CN":
        all_stocks = _get_a_share_list()
        matched = [s for s in all_stocks if q_lower in s["name"].lower() or q_lower in s["symbol"].lower()][:20]
        return {"query": q, "market": market, "results": matched}
    else:
        db_stocks = db.query(Stock).filter(
            (Stock.name.ilike(f"%{q}%")) | (Stock.symbol.ilike(f"%{q}%")),
            Stock.market.in_(["US", "HK"])
        ).limit(20).all()
        return {"query": q, "market": market, "results": [
            {"symbol": s.symbol, "name": s.name, "market": s.market}
            for s in db_stocks
        ]}


@router.get("/api/stocks")
def list_stocks(market: Optional[str] = None, limit: int = Query(50, le=200), db: Session = Depends(get_db)):
    from sqlalchemy import func
    latest = db.query(DailyMetric.symbol, func.max(DailyMetric.id).label('max_id')).group_by(DailyMetric.symbol).subquery()
    query = db.query(Stock, DailyMetric).join(DailyMetric, Stock.symbol == DailyMetric.symbol).join(
        latest, (DailyMetric.symbol == latest.c.symbol) & (DailyMetric.id == latest.c.max_id))
    if market:
        query = query.filter(Stock.market == market)
    results = query.order_by(DailyMetric.score_overall.desc()).limit(limit).all()
    out = []
    for s, m in results:
        close = akc.get_daily_price(s.symbol, 5)[-1]["close"] if (s.symbol.endswith(".SH") or s.symbol.endswith(".SZ")) and m.close > 0 else m.close
        metrics = {"gross_margin": m.gross_margin or 0, "net_margin": m.net_margin or 0,
                   "revenue_growth": m.revenue_growth or 0, "pb": m.pb_ratio or 0}
        notes = {}
        if not m.pe_ratio: notes["pe_ratio"] = "EPS数据缺失"
        if not m.pb_ratio: notes["pb_ratio"] = "净资产数据缺失"
        if not m.roic: notes["roic"] = "资本回报数据缺失"
        if not m.dcf_value: notes["dcf_value"] = "FCF数据缺失，无法估值"
        if not m.gross_margin: notes["gross_margin"] = "毛利率数据缺失"
        if not m.net_margin: notes["net_margin"] = "净利率数据缺失"
        if not m.revenue_growth: notes["revenue_growth"] = "营收增长数据缺失"
        out.append({"symbol": s.symbol, "name": s.name, "market": s.market,
                    "close": close, "pe_ratio": m.pe_ratio, "roic": m.roic,
                    "score_overall": m.score_overall, "score_moat": m.score_moat,
                    "dcf_value": m.dcf_value, "metrics": metrics,
                    "moat_tags": _generate_moat_tags(metrics), "metric_notes": notes})
    return out

@router.get("/api/stock/{symbol}")
def get_stock(symbol: str, db: Session = Depends(get_db)):
    stock = db.query(Stock).filter(Stock.symbol == symbol).first()
    if not stock:
        return {"error": "Stock not found"}
    m = db.query(DailyMetric).filter(DailyMetric.symbol == symbol).order_by(DailyMetric.date.desc(), DailyMetric.id.desc()).first()
    prices = akc.get_daily_price(symbol, 5) if (symbol.endswith(".SH") or symbol.endswith(".SZ")) else []
    current_price = prices[-1]["close"] if prices else (m.close if m else 0)
    notes = {}
    if not m:
        metrics = {"gross_margin": 0, "net_margin": 0, "revenue_growth": 0, "pb": 0}
        return {"symbol": stock.symbol, "name": stock.name, "market": stock.market, "sector": stock.sector,
                "close": current_price, "pe_ratio": 0, "roic": 0, "score_overall": 0,
                "score_moat": 0, "dcf_value": 0, "metrics": metrics,
                "moat_tags": _generate_moat_tags(metrics), "ai_report": "暂无数据", "metric_notes": {}}
    metrics = {"gross_margin": m.gross_margin or 0, "net_margin": m.net_margin or 0,
               "revenue_growth": m.revenue_growth or 0, "pb": m.pb_ratio or 0}
    if not m.pe_ratio: notes["pe_ratio"] = "EPS数据缺失"
    if not m.pb_ratio: notes["pb_ratio"] = "净资产数据缺失"
    if not m.roic: notes["roic"] = "资本回报数据缺失"
    if not m.dcf_value: notes["dcf_value"] = "FCF数据缺失，无法估值"
    if not m.gross_margin: notes["gross_margin"] = "毛利率数据缺失"
    if not m.net_margin: notes["net_margin"] = "净利率数据缺失"
    if not m.revenue_growth: notes["revenue_growth"] = "营收增长数据缺失"
    return {"symbol": stock.symbol, "name": stock.name, "market": stock.market, "sector": stock.sector,
            "close": current_price, "pe_ratio": m.pe_ratio, "roic": m.roic, "score_overall": m.score_overall,
            "score_moat": m.score_moat, "dcf_value": m.dcf_value, "metrics": metrics,
            "moat_tags": _generate_moat_tags(metrics),
            "ai_report": _generate_ai_report(metrics, m.score_moat or 0, m.score_overall or 0, m.dcf_value or 0, current_price),
            "metric_notes": notes}

@router.get("/api/stock/{symbol}/history")
def get_stock_history(symbol: str):
    import akshare as ak
    is_cn = symbol.endswith(".SH") or symbol.endswith(".SZ")
    if is_cn:
        data = akc.get_daily_price(symbol)
    else:
        data = yfc.get_daily_price(symbol)
        if not data:
            try:
                code = symbol[:-3] if symbol.endswith(".HK") else symbol
                if symbol.endswith(".HK"):
                    df = ak.stock_hk_daily(symbol=code)
                else:
                    df = ak.stock_us_daily(symbol=code)
                data = [
                    {"date": str(row["date"]), "open": float(row["open"]), "high": float(row["high"]),
                     "low": float(row["low"]), "close": float(row["close"]), "volume": float(row["volume"])}
                    for _, row in df.iterrows()
                ]
            except Exception:
                data = []
    return {"history": data}

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
    gross_margin = financials.get("gross_margin", 0) or 0
    net_margin = net_income / revenue if revenue else 0
    roic = financials.get("roic", 0)
    revenue_growth = 0.08
    eps = financials.get("eps", 0) or 0
    net_asset_per_share = financials.get("net_asset_per_share", 0) or 0
    pe_ratio = info.get("pe_ratio", 0) or (current_price / eps if eps > 0 else 0)
    pb_ratio = info.get("pb", 0) or (current_price / net_asset_per_share if net_asset_per_share > 0 else 0)
    metrics_dict = {"gross_margin": gross_margin, "net_margin": net_margin, "roic": roic, "revenue_growth": revenue_growth}
    moat_score = score_moat_rules(metrics_dict)
    overall = calculate_overall_score(dcf_margin, roic, moat_score, revenue_growth)
    stock = db.query(Stock).filter(Stock.symbol == symbol).first()
    if not stock:
        stock = Stock(symbol=symbol, market=info.get("market",""), name=info.get("name",""), sector=info.get("sector",""))
        db.add(stock)
    m = DailyMetric(symbol=symbol, date=date.today(), close=current_price, pe_ratio=pe_ratio,
                    pb_ratio=pb_ratio, roic=roic, revenue_growth=revenue_growth, net_margin=net_margin,
                    gross_margin=gross_margin, fcf=fcf_history[0], dcf_value=dcf_value,
                    score_overall=overall["overall"], score_moat=moat_score)
    db.add(m)
    db.commit()
    return {"status": "ok", "score_overall": overall["overall"]}
