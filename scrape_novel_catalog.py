import asyncio
import logging
from playwright.async_api import async_playwright
from urllib.parse import urljoin
from app.db.database import SessionLocal
from app.db.models import Novela

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("CatalogScraper")

async def scrape_novel_catalog(catalog_url: str = "https://twkan.com/novels/hot", max_pages: int = 5):
    """
    Scrapea el catálogo de novelas de twkan.com y guarda las URLs en la base de datos.
    
    Args:
        catalog_url: URL del catálogo (por defecto: novelas populares)
        max_pages: Número máximo de páginas a scrapear
    """
    db = SessionLocal()
    
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
        
        novelas_encontradas = []
        urls_ya_en_db = {n.fuente_scraping for n in db.query(Novela.fuente_scraping).all() if n.fuente_scraping}
        
        try:
            for page_num in range(1, max_pages + 1):
                # Construir URL de la página según el patrón de twkan.com
                # Formato: https://twkan.com/novels/newhot_0_0_1.html
                if page_num == 1:
                    url = catalog_url
                else:
                    # Extraer la categoría de la URL base
                    # Ej: https://twkan.com/novels/hot → hot
                    # Ej: https://twkan.com/novels/newhot_0_0_1.html → newhot
                    if '_0_0_' in catalog_url:
                        # Ya tiene el formato completo, solo cambiar el número
                        base = catalog_url.rsplit('_', 1)[0]  # Quita el último número
                        url = f"{base}_{page_num}.html"
                    else:
                        # Formato simple, construir el patrón completo
                        base = catalog_url.rstrip('/').replace('.html', '')
                        category = base.split('/')[-1]  # Extraer 'hot', 'new', etc.
                        url = f"https://twkan.com/novels/{category}_0_0_{page_num}.html"
                
                logger.info(f"\n{'='*80}")
                logger.info(f"📖 Scrapeando página {page_num}/{max_pages}: {url}")
                logger.info(f"{'='*80}")
                
                try:
                    await page.goto(url, timeout=60000, wait_until="domcontentloaded")
                    await asyncio.sleep(2)
                except Exception as e:
                    logger.warning(f"⚠️ Error al cargar página {page_num}: {e}")
                    continue
                
                # Buscar todos los enlaces a novelas
                # En twkan, los enlaces a novelas suelen estar en formato /book/XXXXX.html
                enlaces = await page.query_selector_all("a[href*='/book/']")
                
                logger.info(f"🔍 Encontrados {len(enlaces)} enlaces en la página {page_num}")
                
                for enlace in enlaces:
                    try:
                        href = await enlace.get_attribute('href')
                        if not href:
                            continue
                        
                        # Construir URL completa
                        full_url = urljoin(url, href)
                        
                        # Filtrar solo URLs de libros (formato: /book/XXXXX.html)
                        if '/book/' in full_url and full_url.endswith('.html'):
                            # Evitar duplicados en esta sesión
                            if full_url not in [n['url'] for n in novelas_encontradas]:
                                # Intentar extraer el título del enlace
                                titulo = await enlace.inner_text()
                                titulo = titulo.strip() if titulo else "Título pendiente"
                                
                                novelas_encontradas.append({
                                    'url': full_url,
                                    'titulo': titulo
                                })
                    except Exception as e:
                        logger.debug(f"Error procesando enlace: {e}")
                        continue
                
                logger.info(f"✅ Página {page_num} procesada. Total acumulado: {len(novelas_encontradas)} novelas")
                
                # Pequeña pausa entre páginas
                await asyncio.sleep(1)
            
            await browser.close()
            
            # Guardar en base de datos
            logger.info(f"\n{'='*80}")
            logger.info(f"💾 Guardando novelas en la base de datos...")
            logger.info(f"{'='*80}")
            
            nuevas = 0
            duplicadas = 0
            
            for novela_data in novelas_encontradas:
                url = novela_data['url']
                titulo = novela_data['titulo']
                
                # Verificar si ya existe
                if url in urls_ya_en_db:
                    duplicadas += 1
                    logger.debug(f"⏭️ Ya existe: {titulo}")
                    continue
                
                # Crear nueva novela
                nueva_novela = Novela(
                    titulo_original=titulo,
                    fuente_scraping=url,
                    estado_original='en_progreso',
                    es_verificado=False
                )
                
                db.add(nueva_novela)
                nuevas += 1
                logger.info(f"➕ Nueva: {titulo} → {url}")
            
            db.commit()
            
            logger.info(f"\n{'='*80}")
            logger.info(f"📊 RESUMEN")
            logger.info(f"{'='*80}")
            logger.info(f"Total encontradas: {len(novelas_encontradas)}")
            logger.info(f"Nuevas guardadas: {nuevas}")
            logger.info(f"Ya existían: {duplicadas}")
            logger.info(f"{'='*80}")
            
        except Exception as e:
            logger.error(f"❌ Error crítico: {e}")
            db.rollback()
        finally:
            db.close()

if __name__ == "__main__":
    # Configuración
    # Ejemplos de URLs válidas:
    # - https://twkan.com/novels/newhot_0_0_1.html (Nuevas populares)
    # - https://twkan.com/novels/hot (Populares - se convertirá a hot_0_0_N.html)
    # - https://twkan.com/novels/new (Nuevas - se convertirá a new_0_0_N.html)
    CATALOG_URL = "https://twkan.com/novels/newhot_0_0_1.html"
    MAX_PAGES = 10  # Número de páginas a scrapear (ajusta según necesites)
    
    logger.info(f"🚀 Iniciando scraper de catálogo de novelas")
    logger.info(f"📍 URL: {CATALOG_URL}")
    logger.info(f"📄 Páginas a scrapear: {MAX_PAGES}")
    logger.info(f"{'='*80}\n")
    
    asyncio.run(scrape_novel_catalog(CATALOG_URL, MAX_PAGES))
