from datetime import datetime

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.config import settings
from app.database import Base


ESTADOS_DOCUMENTO = [
    "Pendiente de revision",
    "En revision",
    "Aprobado",
    "Observado",
    "Rechazado",
    "Requiere correccion",
    "Validado para repositorio",
]

DEPENDENCIAS = [
    "Facultad de Ciencias",
    "Direccion de Investigacion",
    "Instituto de Investigacion",
    "Centro de Investigacion",
    "Otra dependencia",
]

TIPOS_DOCUMENTO = [
    "Articulo",
    "Informe",
    "PAP",
    "PAC",
    "Evidencia",
    "Reporte de gestion",
    "Acta",
    "Resolucion",
    "Otro",
]

PROCESOS_INSTITUCIONALES = [
    "Produccion cientifica",
    "Planificacion institucional",
    "Evaluacion y acreditacion",
    "Seguimiento PAP/PAC",
    "Gestion de proyectos",
    "Evidencias de investigacion",
    "Comites y resoluciones",
    "Otro",
]

NIVELES_CONFIDENCIALIDAD = [
    "Publico institucional",
    "Uso interno",
    "Reservado",
]

PRIORIDADES = [
    "Normal",
    "Alta",
    "Urgente",
]

DOCUMENTOS_REQUERIDOS = [
    {
        "codigo": "ARTICULO_PUBLICADO",
        "nombre": "Articulo cientifico publicado o aceptado",
        "tipo_documento": "Articulo",
        "proceso": "Produccion cientifica",
        "periodicidad": "Anual",
        "descripcion": "PDF del articulo, carta de aceptacion o evidencia editorial.",
    },
    {
        "codigo": "INFORME_AVANCE_PROYECTO",
        "nombre": "Informe de avance de proyecto de investigacion",
        "tipo_documento": "Informe",
        "proceso": "Gestion de proyectos",
        "periodicidad": "Semestral",
        "descripcion": "Informe tecnico con avance, productos, cronograma y evidencias.",
    },
    {
        "codigo": "EVIDENCIA_PAP_PAC",
        "nombre": "Evidencia PAP/PAC",
        "tipo_documento": "Evidencia",
        "proceso": "Seguimiento PAP/PAC",
        "periodicidad": "Semestral",
        "descripcion": "Respaldo documental para planificacion, seguimiento o cierre PAP/PAC.",
    },
    {
        "codigo": "REPORTE_GESTION",
        "nombre": "Reporte de gestion de investigacion",
        "tipo_documento": "Reporte de gestion",
        "proceso": "Planificacion institucional",
        "periodicidad": "Anual",
        "descripcion": "Resumen de actividades, resultados, indicadores y acciones ejecutadas.",
    },
    {
        "codigo": "ACTA_COMITE",
        "nombre": "Acta o resolucion de comite",
        "tipo_documento": "Acta",
        "proceso": "Comites y resoluciones",
        "periodicidad": "Cuando aplique",
        "descripcion": "Acta, resolucion o certificacion relacionada con investigacion.",
    },
    {
        "codigo": "EVIDENCIA_EVALUACION",
        "nombre": "Evidencia para evaluacion o acreditacion",
        "tipo_documento": "Evidencia",
        "proceso": "Evaluacion y acreditacion",
        "periodicidad": "Cuando aplique",
        "descripcion": "Soporte documental requerido para auditoria, evaluacion o acreditacion.",
    },
]


class Usuario(Base):
    """Usuario local del prototipo.

    En una fase posterior esto puede conectarse a LDAP, Microsoft Entra ID,
    Google Workspace u otro sistema institucional de identidad.
    """

    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(180), nullable=False)
    username = Column(String(80), nullable=False, unique=True, index=True)
    correo = Column(String(180), nullable=False, unique=True, index=True)
    password_hash = Column(String(500), nullable=False)
    rol = Column(String(40), nullable=False, index=True, default="cargador")
    dependencia = Column(String(180), nullable=True)
    activo = Column(Boolean, nullable=False, default=True)
    fecha_creacion = Column(DateTime, default=datetime.utcnow, nullable=False)

    documentos = relationship("Documento", back_populates="usuario")


class Documento(Base):
    """Metadatos del documento.

    El archivo fisico no vive en la base de datos. Solo se guarda la ruta
    local o la referencia del proveedor de almacenamiento.
    """

    __tablename__ = "documentos"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True, index=True)
    codigo_seguimiento = Column(String(80), nullable=True, index=True)
    requisito_codigo = Column(String(120), nullable=True, index=True)

    nombre_original = Column(String(255), nullable=False)
    nombre_guardado = Column(String(255), nullable=False, default="")

    docente = Column(String(180), nullable=False, index=True)
    correo = Column(String(180), nullable=False, index=True)
    cargo_responsable = Column(String(180), nullable=True)
    telefono = Column(String(80), nullable=True)
    identificacion = Column(String(80), nullable=True)

    dependencia = Column(String(180), nullable=False, index=True)
    tipo_documento = Column(String(120), nullable=False, index=True)
    proceso_institucional = Column(String(180), nullable=True, index=True)
    programa_proyecto = Column(String(180), nullable=True)
    linea_investigacion = Column(String(180), nullable=True)
    numero_documento = Column(String(120), nullable=True)
    fecha_documento = Column(Date, nullable=True)

    anio = Column(Integer, nullable=False, index=True)
    periodo = Column(String(80), nullable=False, index=True)
    descripcion = Column(Text, nullable=True)
    palabras_clave = Column(Text, nullable=True)
    nivel_confidencialidad = Column(String(80), nullable=True, index=True)
    prioridad = Column(String(80), nullable=True, index=True, default="Normal")
    requiere_respuesta = Column(Boolean, nullable=False, default=False)
    canal_origen = Column(String(80), nullable=True, default="Portal de carga")

    ruta_archivo = Column(String(500), nullable=False, default="")
    storage_provider = Column(String(80), nullable=False, default=settings.STORAGE_PROVIDER)
    storage_path = Column(String(500), nullable=True)
    storage_url = Column(String(1000), nullable=True)
    onedrive_item_id = Column(String(255), nullable=True, index=True)
    onedrive_drive_id = Column(String(255), nullable=True)
    onedrive_web_url = Column(String(1000), nullable=True)
    onedrive_path = Column(String(1000), nullable=True)
    sync_status = Column(String(80), nullable=False, default="local", index=True)
    sync_error = Column(Text, nullable=True)
    fecha_sync = Column(DateTime, nullable=True)

    estado = Column(String(80), nullable=False, default=settings.DEFAULT_ESTADO, index=True)
    observacion = Column(Text, nullable=True)
    observacion_usuario = Column(Text, nullable=True)
    observacion_validacion = Column(Text, nullable=True)

    fecha_subida = Column(DateTime, default=datetime.utcnow, nullable=False)
    fecha_validacion = Column(DateTime, nullable=True)
    fecha_actualizacion = Column(DateTime, nullable=True)
    usuario_validador = Column(String(180), nullable=True)

    usuario = relationship("Usuario", back_populates="documentos")

    def __repr__(self) -> str:
        return f"<Documento id={self.id} nombre={self.nombre_original!r}>"
