from abc import ABC, abstractmethod
from typing import Dict, List

class DataClient(ABC):
    @abstractmethod
    def get_stock_info(self, symbol: str) -> Dict:
        pass

    @abstractmethod
    def get_financials(self, symbol: str) -> Dict:
        pass

    @abstractmethod
    def get_daily_price(self, symbol: str, days: int = 365) -> List[Dict]:
        pass
