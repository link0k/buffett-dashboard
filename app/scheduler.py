import threading
import time
from datetime import datetime, timedelta
from app.database import SessionLocal
from app.models.stock import Stock

def should_refresh(stock: Stock) -> bool:
    if not stock.last_updated:
        return True
    return datetime.now() - stock.last_updated > timedelta(hours=4)

def run_refresh():
    from app.api.stocks import refresh_stock
    db = SessionLocal()
    try:
        stocks = db.query(Stock).all()
        for stock in stocks:
            if should_refresh(stock):
                try:
                    refresh_stock(stock.symbol, db)
                except Exception as e:
                    print(f"Failed: {stock.symbol}: {e}")
    finally:
        db.close()

def start_scheduler():
    def job():
        while True:
            time.sleep(4 * 3600)
            run_refresh()
    t = threading.Thread(target=job, daemon=True)
    t.start()
    return t
