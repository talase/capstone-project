from fastapi import FastAPI

from app.config import load_env_file
from app.routes.calendar import router as calendar_router
from app.routes.style import router as style_router

load_env_file()

app = FastAPI()

app.include_router(calendar_router)
app.include_router(style_router)


@app.get("/")
def root():

    return {"message": "Backend is running"}


@app.get("/health")
def health_check():

    return {"status": "ok"}