import asyncio
import logging
from playwright.async_api import async_playwright
from sqlalchemy.orm import Session
from app.db.models import Novela, Capitulo, FuenteScraping

logger = logging.getLogger(__name__)

async def scrape_chapter_content(url: str, selector_texto: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        try:
            # Abortamos recursos pesados
            await page.route("**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf}", lambda route: route.abort())

            # Navegación
            await page.goto(url, timeout=45000, wait_until="domcontentloaded")
            await asyncio.sleep(6) # Tiempo extra para que el JS inyecte el texto

            # ESTRATEGIA: Buscar el contenedor con más texto
            # Ejecutamos un script en el navegador para encontrar el "body" real de la novela
            mejor_texto = await page.evaluate("""() => {
                const divs = Array.from(document.querySelectorAll('div, article, section'));
                let maxLen = 0;
                let content = "";
                
                divs.forEach(div => {
                    // Filtramos por divs que tengan mucho texto pero pocos enlaces (típico de un capítulo)
                    const text = div.innerText || "";
                    const linkCount = div.querySelectorAll('a').length;
                    
                    if (text.length > maxLen && linkCount < 5) {
                        maxLen = text.length;
                        content = text;
                    }
                });
                return content;
            }""")

            if mejor_texto and len(mejor_texto.strip()) > 800:
                logger.info(f"✅ Texto extraído exitosamente ({len(mejor_texto)} caracteres)")
                return mejor_texto.strip()
            
            # Si falla, el screenshot nos dirá la verdad
            await page.screenshot(path=f"fail_scraping_{url.split('/')[-1]}.png")
            return None

        except Exception as e:
            logger.error(f"Error en scraping: {e}")
            return None
        finally:
            await browser.close()

async def process_pending_scrapes(db: Session):
    # Buscamos capítulos que tengan URL pero no contenido
    pendientes = db.query(Capitulo).filter(
        Capitulo.contenido_original == None
    ).limit(5).all()

    if not pendientes:
        logger.info("Base de datos al día: No hay capítulos pendientes.")
        return

    for cap in pendientes:
        # Obtenemos la configuración de la novela para saber qué selector usar
        novela = db.query(Novela).filter(Novela.id_novela == cap.id_novela).first()
        fuente = db.query(FuenteScraping).filter(FuenteScraping.url_base.contains("skynovels.net")).first()
        
        selector = fuente.configuracion_scraper.get("selector_texto", ".elementor-widget-container")
        
        logger.info(f"📄 Scrapeando: {novela.titulo_original} | Cap {cap.numero_capitulo}")
        
        contenido = await scrape_chapter_content(cap.fuente_url, selector)
        
        if contenido:
            cap.contenido_original = contenido
            db.commit()
            logger.info(f"✅ Contenido guardado para el capítulo {cap.id_capitulo}")
        else:
            logger.warning(f"❌ Falló la extracción para {cap.fuente_url}")