from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from app.database import engine, Base
from app.api.stocks import router as stocks_router
from app.api.watchlist import router as watchlist_router
from app.api.portfolio import router as portfolio_router
import os

Base.metadata.create_all(bind=engine)

# migrate: add gross_margin column if missing
from sqlalchemy import text
with engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE daily_metrics ADD COLUMN gross_margin Float"))
        conn.commit()
    except Exception:
        pass  # column already exists

frontend_dir = "D:/buffett-dashboard/frontend"

app = FastAPI(title="Buffett Stock Dashboard API")
app.include_router(stocks_router)
app.include_router(watchlist_router)
app.include_router(portfolio_router)


@app.get("/", include_in_schema=False)
def root():
    with open(os.path.join(frontend_dir, "index.html"), encoding="utf-8") as f:
        return HTMLResponse(content=f.read())
