import asyncio
import logging
import json
import os
from pathlib import Path
from playwright.async_api import async_playwright
from app.db.database import SessionLocal
from app.db.models import Novela

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("SequentialScraper")

# Archivo para guardar el progreso
CHECKPOINT_FILE = "scraper_checkpoint.json"

def load_checkpoint():
    """Carga el último ID procesado desde el archivo de checkpoint"""
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE, 'r') as f:
                data = json.load(f)
                logger.info(f"📂 Checkpoint cargado: Último ID procesado = {data.get('last_id', 0)}")
                return data.get('last_id', 0)
        except Exception as e:
            logger.warning(f"⚠️ Error al cargar checkpoint: {e}")
    return 0

def save_checkpoint(last_id, total_found, total_skipped):
    """Guarda el progreso actual en el archivo de checkpoint"""
    try:
        with open(CHECKPOINT_FILE, 'w') as f:
            json.dump({
                'last_id': last_id,
                'total_found': total_found,
                'total_skipped': total_skipped
            }, f, indent=2)
        logger.debug(f"💾 Checkpoint guardado: ID {last_id}")
    except Exception as e:
        logger.error(f"❌ Error al guardar checkpoint: {e}")

async def check_novel_exists(page, novel_id):
    """
    Verifica si una novela existe y tiene contenido.
    
    Returns:
        tuple: (exists: bool, url: str or None, title: str or None)
    """
    url = f"https://twkan.com/book/{novel_id}.html"
    
    try:
        response = await page.goto(url, timeout=30000, wait_until="domcontentloaded")
        
        # Verificar si la página existe (no es 404)
        if response.status == 404:
            return False, None, None
        
        await asyncio.sleep(0.5)
        
        # Verificar si hay contenido real (buscar el título)
        title_element = await page.query_selector("div.booknav2 h1 a")
        if not title_element:
            # Intentar selector alternativo
            title_element = await page.query_selector("h1")
        
        if title_element:
            title = await title_element.inner_text()
            title = title.strip()
            
            # Verificar que no sea una página de error
            if title and len(title) > 0 and "404" not in title.lower() and "not found" not in title.lower():
                logger.info(f"✅ ID {novel_id}: {title}")
                return True, url, title
        
        return False, None, None
        
    except Exception as e:
        logger.debug(f"⚠️ Error al verificar ID {novel_id}: {e}")
        return False, None, None

async def scrape_all_novels_sequential(start_id=None, batch_size=100, max_consecutive_failures=50):
    """
    Scrapea todas las novelas secuencialmente desde un ID inicial.
    
    Args:
        start_id: ID inicial (si es None, usa el checkpoint)
        batch_size: Número de IDs a procesar antes de guardar checkpoint
        max_consecutive_failures: Número de fallos consecutivos antes de detener
    """
    db = SessionLocal()
    
    # Cargar checkpoint o usar start_id
    current_id = start_id if start_id is not None else load_checkpoint()
    if current_id == 0:
        current_id = 1  # Empezar desde 1 si no hay checkpoint
    
    logger.info(f"🚀 Iniciando scraper secuencial desde ID: {current_id}")
    logger.info(f"📦 Tamaño de lote: {batch_size}")
    logger.info(f"⚠️ Máximo de fallos consecutivos: {max_consecutive_failures}")
    logger.info(f"{'='*80}\n")
    
    # Obtener URLs ya existentes en la BD
    existing_urls = {n.fuente_scraping for n in db.query(Novela.fuente_scraping).all() if n.fuente_scraping}
    
    total_found = 0
    total_skipped = 0
    total_duplicates = 0
    consecutive_failures = 0
    batch_count = 0
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = await context.new_page()
        
        try:
            while consecutive_failures < max_consecutive_failures:
                exists, url, title = await check_novel_exists(page, current_id)
                
                if exists:
                    consecutive_failures = 0  # Resetear contador
                    
                    # Verificar si ya existe en la BD
                    if url in existing_urls:
                        logger.info(f"⏭️ ID {current_id}: Ya existe en BD")
                        total_duplicates += 1
                    else:
                        # Guardar en base de datos
                        nueva_novela = Novela(
                            titulo_original=title,
                            fuente_scraping=url,
                            estado_original='en_progreso',
                            es_verificado=False
                        )
                        db.add(nueva_novela)
                        existing_urls.add(url)  # Agregar a la lista local
                        total_found += 1
                        logger.info(f"➕ ID {current_id}: Guardada")
                else:
                    consecutive_failures += 1
                    total_skipped += 1
                    logger.debug(f"❌ ID {current_id}: No existe ({consecutive_failures}/{max_consecutive_failures})")
                
                current_id += 1
                batch_count += 1
                
                # Guardar checkpoint cada batch_size IDs
                if batch_count >= batch_size:
                    db.commit()
                    save_checkpoint(current_id - 1, total_found, total_skipped)
                    batch_count = 0
                    
                    logger.info(f"\n{'='*80}")
                    logger.info(f"📊 CHECKPOINT - ID actual: {current_id - 1}")
                    logger.info(f"✅ Encontradas: {total_found} | ⏭️ Duplicadas: {total_duplicates} | ❌ Saltadas: {total_skipped}")
                    logger.info(f"{'='*80}\n")
                
                # Pequeña pausa para no sobrecargar el servidor
                await asyncio.sleep(0.3)
            
            # Guardar checkpoint final
            db.commit()
            save_checkpoint(current_id - 1, total_found, total_skipped)
            
            logger.info(f"\n{'='*80}")
            logger.info(f"🏁 SCRAPING COMPLETADO")
            logger.info(f"{'='*80}")
            logger.info(f"Último ID procesado: {current_id - 1}")
            logger.info(f"✅ Novelas encontradas: {total_found}")
            logger.info(f"⏭️ Duplicadas (ya en BD): {total_duplicates}")
            logger.info(f"❌ IDs saltados: {total_skipped}")
            logger.info(f"Razón de detención: {max_consecutive_failures} fallos consecutivos")
            logger.info(f"{'='*80}")
            
        except KeyboardInterrupt:
            logger.info(f"\n⚠️ Scraping interrumpido por el usuario")
            db.commit()
            save_checkpoint(current_id - 1, total_found, total_skipped)
            logger.info(f"💾 Progreso guardado. Último ID: {current_id - 1}")
        except Exception as e:
            logger.error(f"❌ Error crítico: {e}")
            db.commit()
            save_checkpoint(current_id - 1, total_found, total_skipped)
        finally:
            await browser.close()
            db.close()

if __name__ == "__main__":
    # Configuración
    START_ID = None  # None = usar checkpoint, o especificar un número para empezar desde ahí
    BATCH_SIZE = 100  # Guardar progreso cada 100 IDs
    MAX_CONSECUTIVE_FAILURES = 50  # Detener después de 50 IDs consecutivos sin contenido
    
    logger.info(f"🔧 Configuración:")
    logger.info(f"   - ID inicial: {'Desde checkpoint' if START_ID is None else START_ID}")
    logger.info(f"   - Tamaño de lote: {BATCH_SIZE}")
    logger.info(f"   - Máx. fallos consecutivos: {MAX_CONSECUTIVE_FAILURES}")
    logger.info(f"   - Archivo de checkpoint: {CHECKPOINT_FILE}\n")
    
    asyncio.run(scrape_all_novels_sequential(
        start_id=START_ID,
        batch_size=BATCH_SIZE,
        max_consecutive_failures=MAX_CONSECUTIVE_FAILURES
    ))
