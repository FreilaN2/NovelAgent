from fastapi import FastAPI
from app.core.config import settings

app = FastAPI(
    title="Agente de Novelas IA",
    description="Servicio de scraping y traducción para la plataforma Laravel"
)

@app.get("/")
async def health_check():
    return {
        "status": "online",
        "agent": "NovelAgent-V1",
        "db_connected": f"Host: {settings.DB_HOST}"
    }