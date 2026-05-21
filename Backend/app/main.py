from fastapi import FastAPI

from app.config import load_env_file


#NOTE: comment the parts you are not working on (model, calender, style)
from app.routes.calendar import router as calendar_router
app.include_router(calendar_router)

from app.routes.style import router as style_router
app.include_router(style_router)

# from app.model_pred.model import router as model_pred_router
# app.include_router(model_pred_router)


load_env_file()

app = FastAPI()




@app.get("/")
def root():

    return {"message": "Backend is running"}


@app.get("/health")
def health_check():

    return {"status": "ok"}