from fastapi import FastAPI

from app.config import load_env_file

app = FastAPI()

#NOTE: comment the parts you are not working on (model, calender, style)
from app.personal_context_routes import router as personal_context_router
from app.model_pred.model import router as model_pred_router
from app.routes.calendar import router as calendar_router
from app.routes.style import router as style_router


load_env_file()

app = FastAPI()
app.include_router(calendar_router)
app.include_router(style_router)
app.include_router(personal_context_router)
app.include_router(model_pred_router)




@app.get("/")
def root():

    return {"message": "Backend is running"}


@app.get("/health")
def health_check():

    return {"status": "ok"}
