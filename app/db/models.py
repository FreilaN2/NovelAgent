from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, TIMESTAMP, Enum, JSON, DECIMAL, Date, BIGINT
from sqlalchemy.sql import func
from app.db.database import Base

class Novela(Base):
    __tablename__ = "novelas"

    id_novela = Column(Integer, primary_key=True, index=True)
    titulo_original = Column(String(200), nullable=False)
    id_autor = Column(Integer, ForeignKey("autores_novelas.id_autor"), nullable=True)
    autor_original = Column(String(100))
    descripcion_original = Column(Text)
    url_original_qidian = Column(String(255))
    estado_original = Column(Enum('en_progreso', 'completado', 'pausado', 'cancelado'), default='en_progreso')
    fecha_publicacion_original = Column(Date)
    portada_url = Column(String(255))
    total_capitulos_originales = Column(Integer, default=0)
    fuente_scraping = Column(String(100))
    ultimo_scraping = Column(TIMESTAMP, nullable=True)
    es_verificado = Column(Boolean, default=False)
    hash_metadata = Column(String(64))
    promedio_calificacion = Column(DECIMAL(3,2), default=0)
    total_calificaciones = Column(Integer, default=0)
    total_vistas = Column(BIGINT, default=0)
    total_favoritos = Column(Integer, default=0)
    total_comentarios = Column(Integer, default=0)
    fecha_creacion = Column(TIMESTAMP, server_default=func.now())
    fecha_actualizacion = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

class Capitulo(Base):
    __tablename__ = "capitulos"

    id_capitulo = Column(Integer, primary_key=True, index=True)
    id_novela = Column(Integer, ForeignKey("novelas.id_novela"), nullable=False)
    numero_capitulo = Column(Integer, nullable=False)
    orden_capitulo = Column(Integer, nullable=False)
    titulo_original = Column(String(200))
    contenido_original = Column(Text)
    fecha_publicacion_original = Column(TIMESTAMP, nullable=True)
    fuente_url = Column(String(255))
    palabras_original = Column(Integer)
    estado_capitulo = Column(Enum('disponible', 'borrador', 'oculto', 'en_revision'), default='disponible')
    enviado_traduccion = Column(Boolean, default=False)
    prioridad_traduccion = Column(Integer, default=1)
    hash_contenido = Column(String(64))
    scrapeado_en = Column(TIMESTAMP, nullable=True)
    intentos_scraping = Column(Integer, default=0)
    fecha_creacion = Column(TIMESTAMP, server_default=func.now())
    fecha_actualizacion = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

class TraduccionCapitulo(Base):
    __tablename__ = "capitulos_traduccion_espanol"

    id_traduccion_capitulo_es = Column(Integer, primary_key=True, index=True)
    id_capitulo = Column(Integer, ForeignKey("capitulos.id_capitulo"), nullable=False)
    id_traduccion_novela_es = Column(Integer, nullable=False)
    titulo_traducido = Column(String(200))
    contenido_traducido = Column(Text)
    estado_traduccion = Column(Enum('pendiente', 'en_progreso', 'completado', 'pausado', 'error'), default='pendiente')
    fecha_traduccion = Column(TIMESTAMP, server_default=func.now())
    traductor_ia = Column(String(50))
    version_traduccion = Column(Integer, default=1)
    calidad_estimada = Column(Enum('baja', 'media', 'alta', 'excelente'), default='media')
    palabras_traducidas = Column(Integer)
    contenido_comprimido = Column(Text)
    hash_traduccion = Column(String(64))
    tiempo_traduccion_segundos = Column(Integer)
    costo_traduccion = Column(DECIMAL(10,4), default=0)
    revisado_manualmente = Column(Boolean, default=False)
    errores_reportados = Column(Integer, default=0)

class FuenteScraping(Base):
    __tablename__ = "fuentes_scraping"

    id_fuente = Column(Integer, primary_key=True)
    nombre_fuente = Column(String(100), nullable=False)
    url_base = Column(String(255), nullable=False)
    tipo_fuente = Column(Enum('qidian', 'webnovel', 'ranobes', 'otro'), default='otro')
    pais_origen = Column(String(50), default='China')
    idioma_contenido = Column(String(10), default='zh')
    estado = Column(Enum('activa', 'inactiva', 'bloqueada', 'en_prueba'), default='activa')
    intervalo_scraping_min = Column(Integer, default=1440)
    ultimo_check = Column(TIMESTAMP, nullable=True)
    configuracion_scraper = Column(JSON)
    tasa_exito = Column(DECIMAL(5,2), default=100)
    prioridad = Column(Integer, default=1)
    limite_requests_hora = Column(Integer, default=60)
    requiere_vpn = Column(Boolean, default=False)
    requiere_login = Column(Boolean, default=False)
    credenciales_json = Column(JSON)