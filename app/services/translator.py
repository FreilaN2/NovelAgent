from google import genai
from sqlalchemy.orm import Session
from app.db.models import Capitulo, TraduccionCapitulo
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# Configuración con el nuevo SDK de Google GenAI
# Asegúrate de que en tu .env la variable sea GEMINI_API_KEY
client = genai.Client(api_key=settings.GEMINI_API_KEY)

async def translate_text_gemini(text: str, context_title: str):
    """
    Envía el texto al modelo Gemini 2.0 para su traducción al español.
    """
    try:
        prompt = (
            f"Actúa como un traductor experto en novelas ligeras de China. "
            f"Traduce el siguiente texto al español, manteniendo el tono épico y la terminología de cultivo. "
            f"Novela: {context_title}\n\n"
            f"Texto a traducir:\n{text}"
        )
        
        # Usamos gemini-2.0-flash para mayor velocidad y menor latencia
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt
        )
        
        # El nuevo SDK usa .text directamente en la respuesta
        return response.text
    except Exception as e:
        logger.error(f"Error en la API de Gemini (SDK Nuevo): {e}")
        return None

async def process_pending_translations(db: Session):
    """
    Busca capítulos con contenido original pero sin traducción al español.
    """
    # Buscamos capítulos que tengan contenido pero no tengan entrada en traducciones_capitulo
    pendientes = db.query(Capitulo).outerjoin(
        TraduccionCapitulo, Capitulo.id_capitulo == TraduccionCapitulo.id_capitulo
    ).filter(
        Capitulo.contenido_original != None,
        TraduccionCapitulo.id_traduccion_capitulo == None
    ).limit(3).all()

    if not pendientes:
        logger.info("No hay capítulos pendientes de traducción.")
        return

    for cap in pendientes:
        logger.info(f"Traduciendo con Gemini 2.0: Cap {cap.numero_capitulo} - ID: {cap.id_capitulo}")
        
        texto_traducido = await translate_text_gemini(cap.contenido_original, "Novela en Proceso")
        
        if texto_traducido:
            try:
                nueva_traduccion = TraduccionCapitulo(
                    id_capitulo=cap.id_capitulo,
                    idioma='es',
                    contenido_traducido=texto_traducido,
                    estado_traduccion='completado',
                    traductor_ia='Gemini-2.0-Flash'
                )
                db.add(nueva_traduccion)
                # Opcional: Marcar en la tabla capitulos que ya fue procesado
                cap.enviado_traduccion = True
                
                db.commit()
                logger.info(f"✅ Traducción guardada exitosamente para ID {cap.id_capitulo}")
            except Exception as e:
                db.rollback()
                logger.error(f"Error guardando traducción en MySQL: {e}")