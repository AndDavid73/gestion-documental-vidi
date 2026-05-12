from pathlib import Path
import os

from dotenv import load_dotenv


load_dotenv()


class Settings:
    """Configuracion central del proyecto.

    Mantener rutas y proveedores aqui evita quemar rutas de almacenamiento
    dentro de los controladores o plantillas.
    """

    def __init__(self) -> None:
        self.PROJECT_NAME = "Sistema de Gestion Documental VIDI"
        self.BASE_DIR = Path(__file__).resolve().parent.parent

        self.STORAGE_PROVIDER = os.getenv("STORAGE_PROVIDER", "local").lower()
        self.LOCAL_STORAGE_ENABLED = os.getenv("LOCAL_STORAGE_ENABLED", "true").lower() == "true"
        self.STORAGE_DIR = Path(
            os.getenv("STORAGE_DIR", str(self.BASE_DIR / "storage"))
        ).resolve()

        self.DATABASE_DIR = Path(
            os.getenv("DATABASE_DIR", str(self.BASE_DIR / "database"))
        ).resolve()
        database_url = os.getenv(
            "DATABASE_URL",
            f"sqlite:///{self.DATABASE_DIR / 'documentos.db'}",
        )
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
        elif database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        self.DATABASE_URL = database_url

        self.TEMPLATES_DIR = str(self.BASE_DIR / "app" / "templates")
        self.STATIC_DIR = str(self.BASE_DIR / "app" / "static")
        self.DEFAULT_ESTADO = "Pendiente de revision"
        self.SECRET_KEY = os.getenv(
            "SECRET_KEY",
            "cambiar-esta-clave-en-produccion-vidi-prototipo-local",
        )
        self.APP_BASE_URL = os.getenv("APP_BASE_URL", "http://127.0.0.1:8000")
        self.ENVIRONMENT = os.getenv("ENVIRONMENT", "local")

        self.MICROSOFT_TENANT_ID = os.getenv("MICROSOFT_TENANT_ID", "")
        self.MICROSOFT_CLIENT_ID = os.getenv("MICROSOFT_CLIENT_ID", "")
        self.MICROSOFT_CLIENT_SECRET = os.getenv("MICROSOFT_CLIENT_SECRET", "")
        self.ONEDRIVE_DRIVE_ID = os.getenv("ONEDRIVE_DRIVE_ID", "")
        self.ONEDRIVE_BASE_FOLDER = os.getenv("ONEDRIVE_BASE_FOLDER", "VIDI_DOCUMENTOS")
        self.ONEDRIVE_UPLOAD_CHUNK_SIZE = int(
            os.getenv("ONEDRIVE_UPLOAD_CHUNK_SIZE", str(5 * 1024 * 1024))
        )

    def ensure_directories(self) -> None:
        """Crea carpetas locales necesarias para ejecutar el prototipo."""

        self.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        self.DATABASE_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()
