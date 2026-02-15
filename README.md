# 📖 NovelAgent - AI Driven Novel Translation Agent

**NovelAgent** es un agente inteligente diseñado para automatizar el ciclo de vida de traducción de novelas ligeras. Utiliza **Playwright** para el descubrimiento y extracción de contenido (scraping) y la API de **Gemini** para traducciones épicas con terminología de cultivo.

## 🛠️ Requisitos Previos

Antes de comenzar, asegúrate de tener instalado:

* **Python 3.10+**
* **XAMPP** (con MySQL activo)
* **Node.js** (necesario para las dependencias de Playwright)

---

## 🚀 Instalación y Configuración

### 1. Clonar y Preparar el Entorno

Desde tu terminal en `C:\xampp\htdocs\NovelAgent`:

# Crear el entorno virtual
python -m venv venv

# Activar el entorno virtual
.\venv\Scripts\activate

# Instalar dependencias base
pip install sqlalchemy mysql-connector-python playwright google-genai python-dotenv fastapi uvicorn

### 2. Instalar Navegadores de Playwright

Es crucial para que el **Discovery** y el **Scraper** puedan navegar por SkyNovels:

playwright install chromium

pip install pydantic-settings

### 3. Configuración de Variables de Entorno

Crea un archivo `.env` en la raíz del proyecto:

```env
# Database
DATABASE_URL=mysql+mysqlconnector://root@localhost/tu_base_de_datos

# AI Settings
GEMINI_API_KEY=tu_api_key_de_google_ai_studio

# Agent Settings
AGENT_POLLING_INTERVAL=60
```

### 4. Ejecutar el Agente

```powershell
.\venv\Scripts\Activate.ps1
python worker.py
```

### Verificar que está funcionando:

Abre tu navegador en `http://localhost:8000` y deberías ver:

```json
{
  "status": "online",
  "agent": "NovelAgent-V1",
  "db_connected": "Host: 127.0.0.1"
}
```

### Flujo del Proceso:

1. **Fase 0 (Discovery):** Navega a la pestaña "Contenido" de la novela, expande los volúmenes y detecta nuevos enlaces de capítulos.
2. **Fase 1 (Scraper):** Extrae el texto plano del capítulo usando algoritmos de densidad de texto para evitar publicidad.
3. **Fase 2 (Translator):** Envía el texto a **Gemini 2.0 Flash** para su traducción al español.


NOTA: El FastAPI ahora mismo no está haciendo ninguna función, pero podría servir a futuro para:

Monitoreo: Ver estado del agente, últimos capítulos procesados, estadísticas
Control manual: Forzar scraping de una novela específica, pausar/reanudar el agente
Webhooks: Recibir notificaciones cuando hay nuevos capítulos
API para el frontend Laravel: Consultar capítulos traducidos, progreso, etc.