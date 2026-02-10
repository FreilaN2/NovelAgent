import asyncio
import logging
from app.db.database import SessionLocal
from app.core.config import settings
from app.services.discovery import discover_new_chapters
from app.services.scraper import process_pending_scrapes
from app.services.translator import process_pending_translations

# Configuración de logs para el worker
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("Worker")

async def main_worker():
    logger.info("🚀 Agente de Novelas iniciado (Modo: Worker)")
    
    while True:
        # 1. Creamos una nueva sesión de base de datos para este ciclo
        db = SessionLocal()
        try:
            # FASE 0: Descubrir nuevos capítulos en las fuentes (SkyNovels, etc.)
            logger.info("🔍 Fase 0: Buscando actualizaciones en la web...")
            await discover_new_chapters(db)
            
            # FASE 1: Extraer contenido original de los capítulos detectados
            logger.info("🔍 Fase 1: Extrayendo contenido de capítulos pendientes...")
            await process_pending_scrapes(db)
            
            # FASE 2: Traducir con Gemini el contenido extraído
            logger.info("🔍 Fase 2: Procesando traducciones con Gemini...")
            await process_pending_translations(db)
            
        except Exception as e:
            logger.error(f"❌ Error crítico en el ciclo del worker: {e}")
        finally:
            # IMPORTANTE: Siempre cerrar la conexión con XAMPP para evitar saturar MySQL
            db.close()
        
        logger.info(f"😴 Ciclo completado. Esperando {settings.AGENT_POLLING_INTERVAL} segundos...")
        await asyncio.sleep(settings.AGENT_POLLING_INTERVAL)

if __name__ == "__main__":
    try:
        asyncio.run(main_worker())
    except KeyboardInterrupt:
        logger.info("🛑 Worker detenido manualmente por el usuario.")