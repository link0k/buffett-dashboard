import yfinance as yf
from typing import Dict, List
from .base_client import DataClient
import time

class YFinanceClient(DataClient):
    def get_stock_info(self, symbol: str) -> Dict:
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            return {
                "symbol": symbol,
                "name": info.get("shortName", ""),
                "sector": info.get("sector", ""),
                "market": "US",
                "pe_ratio": info.get("trailingPE", 0) or 0,
                "pb": info.get("priceToBook", 0) or 0,
            }
        except Exception:
            return {"symbol": symbol, "name": "", "sector": "", "market": "US"}

    def get_financials(self, symbol: str) -> Dict:
        try:
            ticker = yf.Ticker(symbol)
            financials = ticker.financials
            if financials.empty:
                return {}
            latest = financials.iloc[:, 0]
            return {
                "revenue": float(latest.get("Total Revenue", 0)),
                "net_income": float(latest.get("Net Income", 0)),
                "fcf": float(latest.get("Free Cash Flow", 0)),
                "eps": float(latest.get("Diluted EPS", 0) or 0),
            }
        except Exception:
            return {}

    def get_daily_price(self, symbol: str, days: int = 3650) -> List[Dict]:
        for attempt in range(3):
            try:
                ticker = yf.Ticker(symbol)
                period = "10y" if days > 365 * 5 else f"{days}d"
                hist = ticker.history(period=period)
                if hist.empty:
                    return []
                return [
                    {"date": str(idx.date()), "open": float(row["Open"]), "high": float(row["High"]),
                     "low": float(row["Low"]), "close": float(row["Close"]), "volume": float(row["Volume"])}
                    for idx, row in hist.iterrows()
                ]
            except Exception as e:
                if "RateLimit" in str(type(e).__name__) or attempt == 2:
                    return []
                time.sleep(2 ** attempt)
        return []
