import asyncio
import logging
import re
from urllib.parse import urljoin
from datetime import datetime
from playwright.async_api import async_playwright
from sqlalchemy.orm import Session
from app.db.models import Novela, Capitulo, AutoresNovelas

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

            # --- VISITAR LA PORTADA PRIMERO: extraer metadata útil ---
            try:
                if "index.html" in url:
                    portada_url = url.replace('/index.html', '.html')
                else:
                    portada_url = url

                # Sólo intentamos si cover distinto o faltan datos
                await page.goto(portada_url, timeout=60000, wait_until="domcontentloaded")
                await asyncio.sleep(1)

                # Intento específico para twkan.com (más fiable para portada)
                titulo = autor = descripcion = portada_img = genero = fecha_text = None
                if "twkan.com" in portada_url:
                    try:
                        # título
                        t_el = await page.query_selector("div.booknav2 h1 a")
                        if t_el:
                            titulo = (await t_el.inner_text()).strip()

                        # autor
                        a_el = await page.query_selector("div.booknav2 p:has-text('作者') a")
                        if a_el:
                            autor = (await a_el.inner_text()).strip()

                        # categoría
                        c_el = await page.query_selector("div.booknav2 p:has-text('分類') a")
                        categoria = (await c_el.inner_text()).strip() if c_el else None

                        # fecha (línea que contiene '更新')
                        f_el = await page.query_selector("div.booknav2 p:has-text('更新')")
                        if f_el:
                            fecha_text = (await f_el.inner_text()).strip()

                        # Extraer el ID de la novela de la URL
                        novel_id_match = re.search(r'/book/(\d+)', portada_url)
                        portada_img = None
                        if novel_id_match:
                            novel_id = novel_id_match.group(1)
                            # Buscar imagen cuyo src contenga el ID de la novela
                            img_el = await page.query_selector(f'img[src*="{novel_id}"]')
                            if img_el:
                                portada_img = await img_el.get_attribute('src')
                        
                        # Fallback: buscar por alt con el título
                        if not portada_img and titulo:
                            img_el = await page.query_selector(f'img[alt="{titulo}"]')
                            if img_el:
                                portada_img = await img_el.get_attribute('src')

                        # descripción: se muestra al clicar '#li_info' (twkan)
                        descripcion = None
                        try:
                            info_btn = await page.query_selector('#li_info')
                            if info_btn:
                                try:
                                    await info_btn.click()
                                    await asyncio.sleep(0.4)
                                except Exception:
                                    pass

                            # buscar párrafo principal dentro de .navtxt (evita el <font> de palabras clave)
                            nav_p = await page.query_selector('div.navtxt p')
                            if nav_p:
                                descripcion = (await nav_p.inner_text()).strip()
                            else:
                                # fallback a selectores generales
                                desc_candidates = ["#intro", ".intro", ".book-intro", ".description", ".summary"]
                                for s in desc_candidates:
                                    d_el = await page.query_selector(s)
                                    if d_el:
                                        descripcion = (await d_el.inner_text()).strip()
                                        break
                        except Exception:
                            descripcion = None

                        # Normalizar campos y forzar actualización para reflejar la portada
                        dirty = False
                        if titulo and novela.titulo_original != titulo:
                            novela.titulo_original = titulo
                            dirty = True
                        if autor and novela.autor_original != autor:
                            novela.autor_original = autor
                            dirty = True
                        if descripcion is not None and novela.descripcion_original != descripcion:
                            novela.descripcion_original = descripcion
                            dirty = True
                        if portada_img:
                            full_cover = urljoin(portada_url, portada_img)
                            if novela.portada_url != full_cover:
                                novela.portada_url = full_cover
                                dirty = True

                        # fecha: extraer YYYY-MM-DD desde el texto (ej: '更新：2026-02-16')
                        if fecha_text:
                            m = re.search(r'(\d{4}-\d{2}-\d{2})', fecha_text)
                            if m:
                                try:
                                    fecha_dt = datetime.strptime(m.group(1), '%Y-%m-%d').date()
                                    if novela.fecha_publicacion_original != fecha_dt:
                                        novela.fecha_publicacion_original = fecha_dt
                                        dirty = True
                                except Exception:
                                    pass

                        # Si tenemos autor, buscar/crear en tabla de autores y asignar id_autor
                        if autor:
                            try:
                                nombre_aut = autor.strip()
                                existente = db.query(AutoresNovelas).filter(AutoresNovelas.nombre_autor == nombre_aut).first()
                                if existente:
                                    if novela.id_autor != existente.id_autor:
                                        novela.id_autor = existente.id_autor
                                        dirty = True
                                else:
                                    nuevo_aut = AutoresNovelas(nombre_autor=nombre_aut)
                                    db.add(nuevo_aut)
                                    db.commit()
                                    db.refresh(nuevo_aut)
                                    novela.id_autor = nuevo_aut.id_autor
                                    dirty = True
                            except Exception as e:
                                logger.debug(f"Error al buscar/crear autor: {e}")
                                try:
                                    db.rollback()
                                except Exception:
                                    pass

                        if dirty:
                            try:
                                db.add(novela)
                                db.commit()
                            except Exception as e:
                                logger.warning(f"No se pudo guardar metadata de portada: {e}")
                                db.rollback()
                    except Exception as e:
                        logger.debug(f"Error extrayendo metadata de twkan: {e}")
                else:
                    # Fallback genérico previo (sin sobrescribir campos existentes)
                    title_selectors = ["h1", "h1.book-name", "#info h1", ".book-title", ".novel-title"]
                    author_selectors = [".author a", "#info .writer", ".book-author a", ".author", "a.writer"]
                    genre_selectors = [".tags a", ".tag", ".category a", ".book-tags a", ".genre a"]
                    desc_selectors = [".intro", "#intro", ".book-intro", ".description", ".summary"]
                    cover_selectors = ["img#cover", ".book-cover img", ".novel-cover img", ".cover img"]

                    async def extract_first(selectors, attr=None):
                        for s in selectors:
                            try:
                                el = await page.query_selector(s)
                                if not el: continue
                                if attr:
                                    val = await el.get_attribute(attr)
                                else:
                                    val = (await el.inner_text()) if hasattr(el, 'inner_text') else None
                                if val:
                                    return val.strip()
                            except Exception:
                                continue
                        return None
                    titulo = await extract_first(title_selectors)
                    autor = await extract_first(author_selectors)

                    # Intentar mostrar descripción clicando '#li_info' antes de fallback
                    descripcion = None
                    try:
                        info_btn = await page.query_selector('#li_info')
                        if info_btn:
                            try:
                                await info_btn.click()
                                await asyncio.sleep(0.4)
                            except Exception:
                                pass

                        nav_p = await page.query_selector('div.navtxt p')
                        if nav_p:
                            descripcion = (await nav_p.inner_text()).strip()
                        else:
                            descripcion = await extract_first(desc_selectors)
                    except Exception:
                        descripcion = await extract_first(desc_selectors)
                    portada_img = await extract_first(cover_selectors, attr="src")

                    # género: recoger varios tags si existen
                    genero = None
                    try:
                        tags = await page.query_selector_all(','.join(genre_selectors))
                        if tags and len(tags) > 0:
                            nombres = []
                            for t in tags:
                                try:
                                    tx = (await t.inner_text()).strip()
                                    if tx:
                                        nombres.append(tx)
                                except Exception:
                                    continue
                            if nombres:
                                genero = ', '.join(dict.fromkeys(nombres))
                    except Exception:
                        genero = None

                    # Normalizar y guardar sólo si faltan en DB
                    dirty = False
                    if titulo and (not getattr(novela, 'titulo_original', None)):
                        novela.titulo_original = titulo
                        dirty = True
                    if autor and (not getattr(novela, 'autor_original', None)):
                        novela.autor_original = autor
                        dirty = True
                    if descripcion and (not getattr(novela, 'descripcion_original', None)):
                        novela.descripcion_original = descripcion
                        dirty = True
                    if portada_img and (not getattr(novela, 'portada_url', None)):
                        novela.portada_url = urljoin(portada_url, portada_img)
                        dirty = True

                    # Si hay género y no existe campo específico, añadimos al principio de la descripción si está vacía
                    if genero and (not getattr(novela, 'descripcion_original', None)):
                        novela.descripcion_original = f"Género: {genero}\n" + (novela.descripcion_original or "")
                        dirty = True

                    # Si tenemos autor, buscar/crear en tabla de autores y asignar id_autor
                    if autor:
                        try:
                            nombre_aut = autor.strip()
                            existente = db.query(AutoresNovelas).filter(AutoresNovelas.nombre_autor == nombre_aut).first()
                            if existente:
                                if novela.id_autor != existente.id_autor:
                                    novela.id_autor = existente.id_autor
                                    dirty = True
                            else:
                                nuevo_aut = AutoresNovelas(nombre_autor=nombre_aut)
                                db.add(nuevo_aut)
                                db.commit()
                                db.refresh(nuevo_aut)
                                novela.id_autor = nuevo_aut.id_autor
                                dirty = True
                        except Exception as e:
                            logger.debug(f"Error al buscar/crear autor: {e}")
                            try:
                                db.rollback()
                            except Exception:
                                pass

                    if dirty:
                        try:
                            db.add(novela)
                            db.commit()
                        except Exception as e:
                            logger.warning(f"No se pudo guardar metadata de portada: {e}")
                            db.rollback()
            except Exception as e:
                logger.debug(f"No se pudo acceder a la portada ({url}): {e}")

            # Asegurarnos de que usamos la URL de índice para el scraping de capítulos
            if "twkan.com" in url and "index.html" not in url:
                url = url.replace(".html", "/index.html")

            logger.info(f"🔍 Patrullando: {novela.titulo_original}")
            
            try:
                await page.goto(url, timeout=60000, wait_until="domcontentloaded")
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
                
                # Actualizar el total de capítulos en la novela
                if total_detectados > 0:
                    novela.total_capitulos_originales = total_detectados
                    db.add(novela)
                    db.commit()
                    logger.info(f"📊 Total de capítulos actualizado: {total_detectados}")
                
                logger.info(f"✅ Proceso terminado: {nuevos_en_db} capítulos nuevos añadidos.")

            except Exception as e:
                logger.error(f"❌ Error: {e}")
                db.rollback()

        await browser.close()