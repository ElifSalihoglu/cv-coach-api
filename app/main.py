from fastapi import FastAPI

app = FastAPI(title="CV Coach API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}