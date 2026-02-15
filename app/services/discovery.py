import asyncio
import logging
import re
from urllib.parse import urljoin
from playwright.async_api import async_playwright
from sqlalchemy.orm import Session
from app.db.models import Novela, Capitulo

logger = logging.getLogger(__name__)

async def discover_new_chapters(db: Session):
    novelas = db.query(Novela).filter(Novela.fuente_scraping != None).all()
    if not novelas: return

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False, 
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        )
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = await context.new_page()

        for novela in novelas:
            url = novela.fuente_scraping
            if "twkan.com" in url and "index.html" not in url:
                url = url.replace(".html", "/index.html")
            
            logger.info(f"🔍 Patrullando: {novela.titulo_original}")
            
            try:
                await page.goto(url, timeout=60000, wait_until="networkidle")
                await asyncio.sleep(2)

                # --- PASO 1: EXPANDIR TODO (Igual que antes) ---
                boton = page.locator("#loadmore, .more-btn, a:has-text('點擊展開')")
                if await boton.count() > 0:
                    logger.info("🖱️ Cargando capítulos ocultos...")
                    await boton.first.click(force=True)
                    
                    links_cuenta = 0
                    for _ in range(15):
                        await asyncio.sleep(1)
                        nueva_cuenta = await page.locator("a").count()
                        if nueva_cuenta > links_cuenta:
                            links_cuenta = nueva_cuenta
                        else:
                            break 
                
                # --- PASO 2: LEER EN ORDEN VISUAL (Cambio clave aquí) ---
                logger.info("📡 Analizando lista por orden de aparición...")
                enlaces_raw = await page.query_selector_all("a")
                
                match_id = re.search(r'/(\d+)', url)
                novel_id = match_id.group(1) if match_id else None
                
                lista_final = []
                urls_vistas = set() # Para no duplicar si un link sale dos veces

                for el in enlaces_raw:
                    href = await el.get_attribute("href")
                    text = await el.inner_text()
                    if not href or not text: continue
                    
                    full_url = urljoin(url, href)
                    
                    # Filtro de seguridad
                    if "/txt/" in full_url and (novel_id in full_url if novel_id else True):
                        if full_url not in urls_vistas:
                            # Guardamos tal cual aparece en el HTML
                            lista_final.append({
                                "titulo": text.strip(),
                                "url": full_url
                            })
                            urls_vistas.add(full_url)

                total_detectados = len(lista_final)
                logger.info(f"🎯 Escaneo finalizado. Se encontraron {total_detectados} capítulos en orden visual.")

                # --- PASO 3: SINCRONIZAR ---
                nuevos_en_db = 0
                urls_en_db = {c.fuente_url for c in db.query(Capitulo.fuente_url).filter(Capitulo.id_novela == novela.id_novela).all()}

                for i, cap in enumerate(lista_final):
                    if cap["url"] not in urls_en_db:
                        nuevo_cap = Capitulo(
                            id_novela=novela.id_novela,
                            numero_capitulo=i + 1, # El orden lo define la posición en la página
                            titulo_original=cap["titulo"],
                            fuente_url=cap["url"],
                            contenido_original=None
                        )
                        db.add(nuevo_cap)
                        nuevos_en_db += 1

                db.commit()
                logger.info(f"✅ Proceso terminado: {nuevos_en_db} capítulos nuevos añadidos.")

            except Exception as e:
                logger.error(f"❌ Error: {e}")
                db.rollback()

        await browser.close()