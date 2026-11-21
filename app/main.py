from fastapi import FastAPI
from app.api.v1.routes_cv import router as cv_router

app = FastAPI(title="CV Coach API")
app.include_router(cv_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}