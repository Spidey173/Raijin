from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from app.routers import jobs_router, auth_router
from app.config import settings

app = FastAPI(
    title="Raijin — AI-Powered Transaction Processing Pipeline API",
    description="Raijin: Asynchronous CSV parser, transaction cleaner, anomaly detector, and multi-provider AI categorizer/summarizer.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Set up CORS securely
cors_origins = [orig.strip() for orig in settings.CORS_ORIGINS.split(",") if orig.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins if cors_origins else ["*"],
    allow_credentials=False if "*" in cors_origins else True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(jobs_router)

@app.get("/health", status_code=status.HTTP_200_OK, tags=["Health"])
def health_check():
    """
    Health check endpoint for container environments and status monitors.
    """
    return {
        "status": "healthy",
        "service": "raijin-api"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
