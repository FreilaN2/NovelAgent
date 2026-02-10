import asyncio
from playwright.async_api import async_playwright
from sqlalchemy.orm import Session
from app.db.models import Novela, Capitulo, FuenteScraping
from urllib.parse import urlparse
import logging

logger = logging.getLogger(__name__)

async def discover_new_chapters(db: Session):
    # 1. Obtener las novelas configuradas
    novelas = db.query(Novela).filter(Novela.fuente_scraping != None).all()

    if not novelas:
        logger.info("No hay novelas configuradas para patrullar.")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080}
        )
        page = await context.new_page()

        for novela in novelas:
            domain = urlparse(novela.fuente_scraping).netloc
            fuente = db.query(FuenteScraping).filter(FuenteScraping.url_base.contains(domain)).first()

            if not fuente:
                logger.warning(f"No hay configuración para el dominio: {domain}")
                continue

            logger.info(f"🔍 Patrullando: {novela.titulo_original}")
            
            try:
                # OPTIMIZACIÓN: Bloqueo de imágenes y fuentes
                await page.route("**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf}", lambda route: route.abort())

                # 2. Navegar a la novela
                try:
                    await page.goto(novela.fuente_scraping, timeout=45000, wait_until="domcontentloaded")
                except Exception as e:
                    logger.warning(f"⚠️ La página tardó en cargar, intentando procesar lo que hay: {e}")

                await asyncio.sleep(3)

                # 3. Clic en la pestaña "Contenido"
                tab_contenido = page.locator("button:has-text('Contenido'), li:has-text('Contenido'), a:has-text('Contenido')")
                if await tab_contenido.count() > 0:
                    logger.info("🖱️ Haciendo clic en la pestaña 'Contenido'...")
                    await tab_contenido.first.click(force=True)
                    await asyncio.sleep(3) 
                
                # 4. Expandir Volúmenes
                headers_volumen = page.locator("div:has-text('Volumen'), .volume-header, [class*='volume']")
                count_vols = await headers_volumen.count()
                logger.info(f"📦 Se encontraron {count_vols} posibles volúmenes. Expandiendo...")

                for i in range(count_vols):
                    try:
                        vol = headers_volumen.nth(i)
                        if await vol.is_visible():
                            await vol.click()
                            await asyncio.sleep(0.5) 
                    except:
                        continue

                # 5. Extraer enlaces
                enlaces_loc = page.locator("a[href*='/capitulo'], .chapter-item a, .v-list-item a")
                total_loc = await enlaces_loc.count()
                
                enlaces_finales = []
                if total_loc > 0:
                    for i in range(total_loc):
                        enlaces_finales.append(enlaces_loc.nth(i))
                else:
                    todos = await page.query_selector_all("a")
                    for link in todos:
                        href = await link.get_attribute("href")
                        text = await link.inner_text()
                        if href and ("/capitulo" in href.lower() or "capítulo" in text.lower()):
                            enlaces_finales.append(link)

                logger.info(f"🔗 Capítulos detectados: {len(enlaces_finales)}. Procesando primeros 10 para prueba.")
                
                # 6. Procesar e insertar en DB
                capitulos_procesados = 0
                for index, el in enumerate(enlaces_finales):
                    if capitulos_procesados >= 10:
                        break

                    url_cap = await el.get_attribute("href")
                    titulo_cap = await el.inner_text()
                    
                    if not url_cap: continue
                    if url_cap.startswith('/'):
                        url_cap = f"https://{domain}{url_cap}"

                    existe = db.query(Capitulo).filter(Capitulo.fuente_url == url_cap).first()
                    
                    if not existe:
                        titulo_limpio = titulo_cap.replace("SS - ", "").strip()
                        
                        logger.info(f"✨ Insertando ({capitulos_procesados + 1}/10): {titulo_limpio}")
                        nuevo_cap = Capitulo(
                            id_novela=novela.id_novela,
                            numero_capitulo=index + 1, 
                            titulo_original=titulo_limpio,
                            fuente_url=url_cap,
                            contenido_original=None 
                        )
                        db.add(nuevo_cap)
                        capitulos_procesados += 1
                
                db.commit()
                logger.info(f"✅ Descubrimiento finalizado con éxito para {novela.titulo_original}")

            except Exception as e:
                logger.error(f"❌ Error crítico en el proceso: {e}")
                db.rollback()

        await browser.close()