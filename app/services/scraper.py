import asyncio
import logging
import json
from datetime import datetime
from playwright.async_api import async_playwright
from sqlalchemy.orm import Session

# Importamos tus modelos exactos de novelasia
from app.db.models import Novela, Capitulo, FuenteScraping

logger = logging.getLogger(__name__)

async def scrape_chapter_content(url: str, selector_css: str = None):
    """
    Usa el Chromium de Playwright para extraer el texto.
    """
    async with async_playwright() as p:
        # ---------------------------------------------------------
        # CONFIGURACIÓN ESTÁNDAR (CHROMIUM)
        # ---------------------------------------------------------
        # headless=False significa que VERÁS el navegador abrirse.
        # Cambialo a True cuando ya confíes en el script.
        browser = await p.chromium.launch(headless=False)
        
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        try:
            # Optimización: Bloquear imágenes, fuentes y CSS para ir rápido
            await page.route("**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf,css}", lambda route: route.abort())

            logger.info(f"🌐 Navegando a: {url}")
            try:
                await page.goto(url, timeout=60000, wait_until="domcontentloaded")
            except Exception as e:
                logger.warning(f"⚠️ Tiempo de espera agotado, intentando recuperar texto de todos modos... {e}")

            await asyncio.sleep(4) # Espera técnica para cargas dinámicas (JS)

            texto_final = ""

            # ESTRATEGIA SOLICITADA
            # 1. Intentar por ID específico (Visto en inspección: #txtcontent0)
            try:
                content_element = await page.query_selector("#txtcontent0")
                if content_element:
                    texto_final = await content_element.inner_text()
                    logger.info("✅ Texto extraído usando ID #txtcontent0")
            except:
                pass

            if not texto_final:
                texto_final = await page.evaluate("""() => {
                    const nav = document.querySelector('.txtnav');
                    if (nav) {
                        const contentDiv = nav.querySelector('div[id^="txtcontent"]');
                        if (contentDiv) return contentDiv.innerText;
                        
                        const children = Array.from(nav.children);
                        if (children.length >= 4) {
                            return children[3].innerText;
                        }
                    }
                    return "";
                }""")
                if texto_final:
                    logger.info("✅ Texto extraído usando estructura DOM (.txtnav hijo #4)")

            # Validación final
            if texto_final and len(texto_final.strip()) > 50:
                return texto_final.strip()
            else:
                logger.error("❌ No se pudo extraer texto válido (vacío o muy corto).")
                return None

        except Exception as e:
            logger.error(f"❌ Error en scraping: {e}")
            return None
        finally:
            await browser.close()

async def process_pending_scrapes(db: Session):
    """
    Busca capítulos sin contenido en la DB y los procesa.
    """
    # 1. Buscar capítulos pendientes (contenido_original IS NULL)
    pendientes = db.query(Capitulo).filter(
        Capitulo.contenido_original == None,
        Capitulo.fuente_url != None
    ).limit(3).all()

    if not pendientes:
        logger.info("💤 No hay capítulos pendientes de scraping.")
        return

    logger.info(f"🔄 Encontrados {len(pendientes)} capítulos para procesar.")

    for cap in pendientes:
        # 2. Intentar buscar configuración en la tabla fuentes_scraping
        selector = None
        
        # Traemos todas las fuentes activas
        fuentes = db.query(FuenteScraping).filter(FuenteScraping.estado == 'activa').all()
        
        for fuente in fuentes:
            if fuente.url_base and fuente.url_base in cap.fuente_url:
                if fuente.configuracion_scraper:
                    config = fuente.configuracion_scraper
                    # Manejo seguro del JSON
                    if isinstance(config, dict):
                        selector = config.get("selector_texto")
                    elif isinstance(config, str):
                        try:
                            config_dict = json.loads(config)
                            selector = config_dict.get("selector_texto")
                        except:
                            pass
                break 

        # 3. Ejecutar el scraping
        logger.info(f"📖 Procesando Cap {cap.numero_capitulo}...")
        contenido = await scrape_chapter_content(cap.fuente_url, selector)
        
        # 4. Guardar en la base de datos
        if contenido:
            cap.contenido_original = contenido
            cap.scrapeado_en = datetime.utcnow()
            
            # Si tu modelo tiene columna 'intentos_scraping', la actualizamos
            try:
                cap.intentos_scraping = (cap.intentos_scraping or 0) + 1
            except:
                pass # Si la columna no existe en el modelo, no fallamos
            
            db.commit()
            logger.info(f"💾 Guardado en DB: Capitulo {cap.numero_capitulo}")
        else:
            logger.warning(f"⚠️ Se salta el capítulo {cap.numero_capitulo} por fallo en lectura.")