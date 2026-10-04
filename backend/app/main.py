from fastapi import FastAPI

from app.api.jobs import router as jobs_router
from app.api.projects import router as projects_router

app = FastAPI()
app.include_router(projects_router)
app.include_router(jobs_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
