from fastapi import FastAPI
from fastapi.responses import FileResponse
from app.database import engine, Base
from app.api.stocks import router as stocks_router
import os

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Buffett Stock Dashboard API")
app.include_router(stocks_router)

frontend_dir = "D:/buffett-dashboard/frontend"

@app.get("/")
def root():
    return FileResponse(os.path.join(frontend_dir, "index.html"))

@app.get("/index.html")
def index_html():
    return FileResponse(os.path.join(frontend_dir, "index.html"))
