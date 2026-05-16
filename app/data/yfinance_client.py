import yfinance as yf
from typing import Dict, List
from .base_client import DataClient

class YFinanceClient(DataClient):
    def get_stock_info(self, symbol: str) -> Dict:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        return {
            "symbol": symbol,
            "name": info.get("shortName", ""),
            "sector": info.get("sector", ""),
            "market": "US",
        }

    def get_financials(self, symbol: str) -> Dict:
        ticker = yf.Ticker(symbol)
        financials = ticker.financials
        if financials.empty:
            return {}
        latest = financials.iloc[:, 0]
        return {
            "revenue": float(latest.get("Total Revenue", 0)),
            "net_income": float(latest.get("Net Income", 0)),
            "fcf": float(latest.get("Free Cash Flow", 0)),
        }

    def get_daily_price(self, symbol: str, days: int = 365) -> List[Dict]:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=f"{days}d")
        return [
            {"date": str(idx.date()), "close": row["Close"]}
            for idx, row in hist.iterrows()
        ]
