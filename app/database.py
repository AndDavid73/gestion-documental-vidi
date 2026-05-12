from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings


# SQLite necesita este argumento cuando FastAPI atiende varias peticiones.
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


SQLITE_COLUMN_MIGRATIONS = {
    "usuario_id": "INTEGER",
    "codigo_seguimiento": "VARCHAR(80)",
    "requisito_codigo": "VARCHAR(120)",
    "cargo_responsable": "VARCHAR(180)",
    "telefono": "VARCHAR(80)",
    "identificacion": "VARCHAR(80)",
    "proceso_institucional": "VARCHAR(180)",
    "programa_proyecto": "VARCHAR(180)",
    "linea_investigacion": "VARCHAR(180)",
    "numero_documento": "VARCHAR(120)",
    "fecha_documento": "DATE",
    "descripcion": "TEXT",
    "palabras_clave": "TEXT",
    "nivel_confidencialidad": "VARCHAR(80)",
    "prioridad": "VARCHAR(80)",
    "requiere_respuesta": "BOOLEAN DEFAULT 0",
    "canal_origen": "VARCHAR(80)",
    "onedrive_item_id": "VARCHAR(255)",
    "onedrive_drive_id": "VARCHAR(255)",
    "onedrive_web_url": "VARCHAR(1000)",
    "onedrive_path": "VARCHAR(1000)",
    "sync_status": "VARCHAR(80) DEFAULT 'local'",
    "sync_error": "TEXT",
    "fecha_sync": "DATETIME",
    "observacion_usuario": "TEXT",
    "observacion_validacion": "TEXT",
    "fecha_actualizacion": "DATETIME",
}


DEFAULT_USERS = [
    {
        "nombre": "Usuario Docente Demo",
        "username": "docente",
        "correo": "docente@vidi.local",
        "password": "Docente123",
        "rol": "cargador",
        "dependencia": "Facultad de Ciencias",
    },
    {
        "nombre": "Administrador VIDI",
        "username": "admin",
        "correo": "admin@vidi.local",
        "password": "Admin123",
        "rol": "admin",
        "dependencia": "Direccion de Investigacion",
    },
]


def get_db():
    """Entrega una sesion de base de datos por peticion."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def migrate_sqlite_documentos() -> None:
    """Agrega columnas nuevas al prototipo SQLite sin borrar datos existentes."""

    if not settings.DATABASE_URL.startswith("sqlite"):
        return

    with engine.begin() as connection:
        tablas = connection.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='documentos'")
        ).fetchall()
        if not tablas:
            return

        columnas_existentes = {
            fila[1] for fila in connection.execute(text("PRAGMA table_info(documentos)"))
        }
        for nombre_columna, definicion in SQLITE_COLUMN_MIGRATIONS.items():
            if nombre_columna not in columnas_existentes:
                connection.execute(
                    text(f"ALTER TABLE documentos ADD COLUMN {nombre_columna} {definicion}")
                )

        connection.execute(
            text(
                """
                UPDATE documentos
                SET codigo_seguimiento = printf('VIDI-%d-%05d', anio, id)
                WHERE codigo_seguimiento IS NULL OR codigo_seguimiento = ''
                """
            )
        )
        connection.execute(
            text(
                """
                UPDATE documentos
                SET prioridad = 'Normal'
                WHERE prioridad IS NULL OR prioridad = ''
                """
            )
        )
        connection.execute(
            text(
                """
                UPDATE documentos
                SET canal_origen = 'Portal de carga'
                WHERE canal_origen IS NULL OR canal_origen = ''
                """
            )
        )
        connection.execute(
            text(
                """
                UPDATE documentos
                SET sync_status = 'local'
                WHERE sync_status IS NULL OR sync_status = ''
                """
            )
        )


def seed_default_users() -> None:
    """Crea usuarios iniciales para probar el prototipo local."""

    from app.models import Documento, Usuario
    from app.security import hash_password

    db = SessionLocal()
    try:
        for user_data in DEFAULT_USERS:
            usuario = (
                db.query(Usuario)
                .filter(Usuario.username == user_data["username"])
                .first()
            )
            if not usuario:
                usuario = Usuario(
                    nombre=user_data["nombre"],
                    username=user_data["username"],
                    correo=user_data["correo"],
                    password_hash=hash_password(user_data["password"]),
                    rol=user_data["rol"],
                    dependencia=user_data["dependencia"],
                    activo=True,
                )
                db.add(usuario)
                db.flush()

            db.query(Documento).filter(
                Documento.usuario_id.is_(None),
                Documento.correo == usuario.correo,
            ).update({"usuario_id": usuario.id})
        db.commit()
    finally:
        db.close()


def init_db() -> None:
    """Inicializa carpetas y tablas del prototipo local."""

    settings.ensure_directories()

    # Importar modelos aqui asegura que SQLAlchemy conozca las tablas.
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    migrate_sqlite_documentos()
    seed_default_users()
