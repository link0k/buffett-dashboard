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
            # use stock_financial_abstract which reliably has 营业总收入 and 净利润
            df = ak.stock_financial_abstract(symbol=code)
            if df.empty:
                return {}
            indicators = {}
            for _, row in df.iterrows():
                name = row["指标"]
                # find the latest non-nan value (skip first two meta columns)
                vals = [v for v in row.iloc[2:] if v is not None and not (isinstance(v, float) and v != v)]
                indicators[name] = float(vals[0]) if vals else 0
            revenue = indicators.get("营业总收入", 0)
            net_income = indicators.get("净利润", 0)
            fcf = indicators.get("经营现金流量净额", 0) or 0
            roic = indicators.get("投入资本回报率", 0) / 100 if indicators.get("投入资本回报率", 0) else 0
            eps = indicators.get("基本每股收益", 0) or indicators.get("稀释每股收益", 0) or 0
            net_asset_per_share = indicators.get("每股净资产", 0) or indicators.get("每股净资产_最新", 0) or 0
            gross_margin = indicators.get("毛利率", 0) / 100 if indicators.get("毛利率", 0) else 0
            # also try financial_analysis_indicator for roic and eps
            try:
                df2 = ak.stock_financial_analysis_indicator(symbol=code, start_year='2024')
                if not df2.empty:
                    r2 = df2.iloc[0]
                    if roic == 0 and "投入资本回报率" in df2.columns:
                        roic = float(r2.get("投入资本回报率", 0) or 0) / 100
            except Exception:
                pass
            return {
                "revenue": revenue,
                "net_income": net_income,
                "fcf": fcf,
                "roic": roic,
                "eps": eps,
                "net_asset_per_share": net_asset_per_share,
                "gross_margin": gross_margin,
            }
        except Exception as e:
            return {}

    def get_daily_price(self, symbol: str, days: int = 3650) -> List[Dict]:
        try:
            code = symbol.split('.')[0]
            prefix = "sh" if code.startswith(("6", "9")) else "sz"
            df = ak.stock_zh_a_daily(symbol=prefix + code, adjust="qfq")
            return [
                {"date": str(row["date"]), "open": float(row["open"]), "high": float(row["high"]),
                 "low": float(row["low"]), "close": float(row["close"]), "volume": float(row["volume"])}
                for _, row in df.iterrows()
            ]
        except Exception:
            return []
