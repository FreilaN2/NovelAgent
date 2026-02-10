from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# Construimos la URL de conexión para MySQL
# Usamos pymysql como driver para la compatibilidad con XAMPP
SQLALCHEMY_DATABASE_URL = (
    f"mysql+pymysql://{settings.DB_USER}:{settings.DB_PASSWORD}@"
    f"{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
)

# El motor de la base de datos
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    # pool_pre_ping ayuda a reconectar si XAMPP cierra la conexión por inactividad
    pool_pre_ping=True 
)

# Sesión local para interactuar con la DB
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Clase base para nuestros modelos
Base = declarative_base()

# Dependencia para obtener la sesión en las rutas de FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()