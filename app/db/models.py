from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, TIMESTAMP, Enum, JSON
from sqlalchemy.sql import func
from app.db.database import Base

class Novela(Base):
    __tablename__ = "novelas"

    id_novela = Column(Integer, primary_key=True, index=True)
    titulo_original = Column(String(200), nullable=False)
    titulo_ingles = Column(String(200))
    autor_original = Column(String(100))
    descripcion_original = Column(Text)
    # Este campo debe coincidir con la URL en la tabla novelas para el discovery
    fuente_scraping = Column(String(255)) 
    portada_url = Column(String(255))
    es_verificado = Column(Boolean, default=False)
    fecha_creacion = Column(TIMESTAMP, server_default=func.now())

class Capitulo(Base):
    __tablename__ = "capitulos"

    id_capitulo = Column(Integer, primary_key=True, index=True)
    id_novela = Column(Integer, ForeignKey("novelas.id_novela"))
    numero_capitulo = Column(Integer)
    titulo_original = Column(String(200))
    contenido_original = Column(Text) 
    fuente_url = Column(String(255))
    enviado_traduccion = Column(Boolean, default=False)

class TraduccionCapitulo(Base):
    __tablename__ = "traducciones_capitulo"

    id_traduccion_capitulo = Column(Integer, primary_key=True, index=True)
    id_capitulo = Column(Integer, ForeignKey("capitulos.id_capitulo"))
    idioma = Column(String(10), default="es")
    titulo_traducido = Column(String(200))
    contenido_traducido = Column(Text)
    estado_traduccion = Column(Enum('pendiente', 'en_progreso', 'completado', 'pausado'), default='pendiente')
    fecha_traduccion = Column(TIMESTAMP, server_default=func.now())

class FuenteScraping(Base):
    __tablename__ = "fuentes_scraping"

    id_fuente = Column(Integer, primary_key=True)
    nombre_fuente = Column(String(100))
    url_base = Column(String(255))
    configuracion_scraper = Column(JSON)
    estado = Column(Enum('activa', 'inactiva', 'bloqueada'), default='activa')