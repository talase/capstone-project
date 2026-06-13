from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import load_env_file

#NOTE: comment the parts you are not working on (model, calender, style)
from app.approval_routes import router as approval_router
from app.personal_context_routes import router as personal_context_router
from app.model_pred.model import router as model_pred_router
#from app.routes.calendar import router as calendar_router
from app.routes.reports import router as reports_router
from app.routes.style import router as style_router
from app.routes.scheduler import router as scheduler_router
#from app.routes.files import router as files_router
#from app.routes.contacts import router as contacts_router
from app.supabase_client import log_supabase_startup_config


load_env_file()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    log_supabase_startup_config()
    yield


app = FastAPI(lifespan=lifespan)
#app.include_router(calendar_router)
app.include_router(style_router)
app.include_router(reports_router)
app.include_router(personal_context_router)
app.include_router(approval_router)
app.include_router(model_pred_router)
app.include_router(scheduler_router)
#app.include_router(files_router)
#app.include_router(contacts_router)



@app.get("/")
def root():

    return {"message": "Backend is running"}


@app.get("/health")
def health_check():

    return {"status": "ok"}
