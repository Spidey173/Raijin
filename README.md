# Raijin: Transaction Processing Pipeline

Asynchronous, production-grade transaction processing pipeline with FastAPI, Celery, PostgreSQL, Redis, and multi-provider LLM categorization.

## Architecture Overview
```
Client -> FastAPI -> Celery Worker (Background Job) -> PostgreSQL
                          |
             [Clean -> Anomaly -> LLM Categorization -> Summary]
```

## Quickstart
1. Clone the repository
2. Run `docker compose up --build`
3. Access API docs at `http://localhost:8000/docs`
