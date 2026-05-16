import akshare as ak
from typing import Dict, List
from .base_client import DataClient

class AkshareClient(DataClient):
    def get_stock_info(self, symbol: str) -> Dict:
        try:
            code = symbol.split('.')[0]
            df = ak.stock_individual_info_em(symbol=code)
            info_dict = dict(zip(df["item"], df["value"]))
            return {
                "symbol": symbol,
                "name": info_dict.get("股票简称", ""),
                "sector": info_dict.get("行业", ""),
                "market": "CN",
            }
        except Exception:
            return {"symbol": symbol, "name": "", "sector": "", "market": "CN"}

    def get_financials(self, symbol: str) -> Dict:
        try:
            code = symbol.split('.')[0]
            df = ak.stock_financial_analysis_indicator(symbol=code)
            if df.empty:
                return {}
            latest = df.iloc[0]
            return {
                "revenue": float(latest.get("营业总收入", 0) or 0),
                "net_income": float(latest.get("净利润", 0) or 0),
                "fcf": float(latest.get("经营活动产生的现金流量净额", 0) or 0),
                "roic": float(latest.get("投入资本回报率", 0) or 0) / 100,
            }
        except Exception:
            return {}

    def get_daily_price(self, symbol: str, days: int = 365) -> List[Dict]:
        try:
            code = symbol.split('.')[0]
            df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")
            df = df.tail(days)
            return [
                {"date": str(row["日期"]), "close": float(row["收盘"])}
                for _, row in df.iterrows()
            ]
        except Exception:
            return []
