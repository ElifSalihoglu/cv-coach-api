from fastapi import FastAPI
from .scraper import scrape_indeed_jobs 

app = FastAPI()

@app.get("/search")
def search_jobs(query: str, city: str = "Berlin", country: str = "Germany"):
    results = scrape_indeed_jobs(query, city, country)
    return {"results": results}
