from datetime import date, datetime
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import (
    DEPENDENCIAS,
    DOCUMENTOS_REQUERIDOS,
    ESTADOS_DOCUMENTO,
    NIVELES_CONFIDENCIALIDAD,
    PRIORIDADES,
    PROCESOS_INSTITUCIONALES,
    TIPOS_DOCUMENTO,
    Documento,
    Usuario,
)
from app.security import authenticate_user
from app.services.storage_service import StorageService
from app.storage_providers.onedrive_storage import OneDriveStorageProvider


router = APIRouter()
templates = Jinja2Templates(directory=settings.TEMPLATES_DIR)
storage_service = StorageService()

ROLES_PORTAL = {"cargador"}
ROLES_ADMIN = {"admin", "validador"}

ESTADOS_FINALES = {
    "Aprobado",
    "Rechazado",
    "Validado para repositorio",
}

CAMPOS_RECOMENDADOS = [
    ("proceso_institucional", "Proceso institucional"),
    ("programa_proyecto", "Programa, proyecto o actividad"),
    ("descripcion", "Descripcion del documento"),
    ("palabras_clave", "Palabras clave"),
    ("fecha_documento", "Fecha del documento"),
    ("nivel_confidencialidad", "Nivel de confidencialidad"),
]

ESTADOS_CARGA_VALIDA = {
    "Pendiente de revision",
    "En revision",
    "Aprobado",
    "Observado",
    "Requiere correccion",
    "Validado para repositorio",
}


def usuario_actual(request: Request, db: Session) -> Optional[Usuario]:
    usuario_id = request.session.get("usuario_id")
    if not usuario_id:
        return None
    return (
        db.query(Usuario)
        .filter(Usuario.id == usuario_id, Usuario.activo.is_(True))
        .first()
    )


def iniciar_sesion(request: Request, usuario: Usuario) -> None:
    request.session.clear()
    request.session["usuario_id"] = usuario.id
    request.session["rol"] = usuario.rol
    request.session["nombre"] = usuario.nombre


def siguiente_url_segura(next_url: Optional[str], fallback: str) -> str:
    if next_url and next_url.startswith("/") and not next_url.startswith("//"):
        return next_url
    return fallback


def redirect_login(request: Request, login_path: str) -> RedirectResponse:
    next_url = request.url.path
    if request.url.query:
        next_url = f"{next_url}?{request.url.query}"
    return RedirectResponse(
        url=f"{login_path}?next={quote(next_url)}",
        status_code=303,
    )


def requerir_roles(
    request: Request,
    db: Session,
    roles: set[str],
    login_path: str,
) -> tuple[Optional[Usuario], Optional[RedirectResponse]]:
    usuario = usuario_actual(request, db)
    if not usuario:
        return None, redirect_login(request, login_path)
    if usuario.rol not in roles:
        return None, RedirectResponse(url="/", status_code=303)
    return usuario, None


def render_template(
    request: Request,
    db: Session,
    name: str,
    context: Optional[dict] = None,
):
    return templates.TemplateResponse(
        request=request,
        name=name,
        context={
            "request": request,
            "current_user": usuario_actual(request, db),
            **(context or {}),
        },
    )


def obtener_documento_o_404(documento_id: int, db: Session) -> Documento:
    documento = db.query(Documento).filter(Documento.id == documento_id).first()
    if documento is None:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    return documento


def obtener_documento_del_usuario_o_404(
    documento_id: int,
    usuario: Usuario,
    db: Session,
) -> Documento:
    documento = obtener_documento_o_404(documento_id, db)
    if usuario.rol in ROLES_ADMIN:
        return documento
    if documento.usuario_id == usuario.id or documento.correo == usuario.correo:
        return documento
    raise HTTPException(status_code=404, detail="Documento no encontrado")


def limpiar_opcional(valor: Optional[str]) -> Optional[str]:
    if valor is None:
        return None
    valor = valor.strip()
    return valor or None


def convertir_fecha(valor: Optional[str]) -> Optional[date]:
    if not valor:
        return None
    try:
        return datetime.strptime(valor, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="La fecha del documento no es valida") from exc


def generar_codigo_seguimiento(anio: int, documento_id: int) -> str:
    return f"VIDI-{anio}-{documento_id:05d}"


def contexto_opciones() -> dict:
    return {
        "dependencias": DEPENDENCIAS,
        "tipos_documento": TIPOS_DOCUMENTO,
        "procesos_institucionales": PROCESOS_INSTITUCIONALES,
        "niveles_confidencialidad": NIVELES_CONFIDENCIALIDAD,
        "prioridades": PRIORIDADES,
        "estados": ESTADOS_DOCUMENTO,
        "documentos_requeridos": DOCUMENTOS_REQUERIDOS,
    }


def obtener_requisito(codigo: Optional[str]) -> Optional[dict]:
    if not codigo:
        return None
    return next(
        (requisito for requisito in DOCUMENTOS_REQUERIDOS if requisito["codigo"] == codigo),
        None,
    )


def campos_pendientes(documento: Documento) -> list[str]:
    faltantes = []
    for atributo, etiqueta in CAMPOS_RECOMENDADOS:
        if not getattr(documento, atributo):
            faltantes.append(etiqueta)
    return faltantes


def consulta_documentos_usuario(db: Session, usuario: Usuario):
    return db.query(Documento).filter(
        or_(
            Documento.usuario_id == usuario.id,
            Documento.correo == usuario.correo,
        )
    )


def construir_consulta_documentos(
    db: Session,
    *,
    anio: Optional[int] = None,
    dependencia: Optional[str] = None,
    tipo_documento: Optional[str] = None,
    estado: Optional[str] = None,
    periodo: Optional[str] = None,
    proceso_institucional: Optional[str] = None,
    prioridad: Optional[str] = None,
    nivel_confidencialidad: Optional[str] = None,
    q: Optional[str] = None,
):
    consulta = db.query(Documento)

    if anio:
        consulta = consulta.filter(Documento.anio == anio)
    if dependencia:
        consulta = consulta.filter(Documento.dependencia == dependencia)
    if tipo_documento:
        consulta = consulta.filter(Documento.tipo_documento == tipo_documento)
    if estado:
        consulta = consulta.filter(Documento.estado == estado)
    if periodo:
        consulta = consulta.filter(Documento.periodo.ilike(f"%{periodo.strip()}%"))
    if proceso_institucional:
        consulta = consulta.filter(Documento.proceso_institucional == proceso_institucional)
    if prioridad:
        consulta = consulta.filter(Documento.prioridad == prioridad)
    if nivel_confidencialidad:
        consulta = consulta.filter(Documento.nivel_confidencialidad == nivel_confidencialidad)
    if q:
        patron = f"%{q.strip()}%"
        consulta = consulta.filter(
            or_(
                Documento.docente.ilike(patron),
                Documento.correo.ilike(patron),
                Documento.nombre_original.ilike(patron),
                Documento.nombre_guardado.ilike(patron),
                Documento.codigo_seguimiento.ilike(patron),
                Documento.numero_documento.ilike(patron),
                Documento.programa_proyecto.ilike(patron),
                Documento.palabras_clave.ilike(patron),
            )
        )

    return consulta


def obtener_metricas(db: Session) -> dict:
    return {
        "total": db.query(Documento).count(),
        "pendientes": db.query(Documento).filter(Documento.estado == "Pendiente de revision").count(),
        "en_revision": db.query(Documento).filter(Documento.estado == "En revision").count(),
        "observados": db.query(Documento).filter(Documento.estado == "Observado").count(),
        "correccion": db.query(Documento).filter(Documento.estado == "Requiere correccion").count(),
        "aprobados": db.query(Documento).filter(Documento.estado == "Aprobado").count(),
        "validado_repositorio": db.query(Documento)
        .filter(Documento.estado == "Validado para repositorio")
        .count(),
        "urgentes": db.query(Documento).filter(Documento.prioridad == "Urgente").count(),
        "sync_local": db.query(Documento).filter(Documento.sync_status == "local").count(),
        "sync_synced": db.query(Documento).filter(Documento.sync_status == "synced").count(),
        "sync_error": db.query(Documento).filter(Documento.sync_status == "error").count(),
        "sync_pending": db.query(Documento).filter(Documento.sync_status == "pending").count(),
    }


def obtener_metricas_usuario(db: Session, usuario: Usuario) -> dict:
    consulta = consulta_documentos_usuario(db, usuario)
    documentos = consulta.all()
    progreso = obtener_progreso_requisitos_usuario(db, usuario)
    return {
        "total": len(documentos),
        "pendientes": sum(1 for doc in documentos if doc.estado == "Pendiente de revision"),
        "correccion": sum(1 for doc in documentos if doc.estado == "Requiere correccion"),
        "observados": sum(1 for doc in documentos if doc.estado == "Observado"),
        "finalizados": sum(1 for doc in documentos if doc.estado in ESTADOS_FINALES),
        "incompletos": sum(1 for doc in documentos if campos_pendientes(doc)),
        "requeridos_total": progreso["total"],
        "requeridos_cargados": progreso["cargados"],
        "requeridos_faltantes": progreso["faltantes"],
        "requeridos_validados": progreso["validados"],
        "porcentaje_carga": progreso["porcentaje_carga"],
        "porcentaje_validacion": progreso["porcentaje_validacion"],
    }


def obtener_progreso_requisitos_usuario(db: Session, usuario: Usuario) -> dict:
    documentos = (
        consulta_documentos_usuario(db, usuario)
        .filter(Documento.requisito_codigo.isnot(None))
        .order_by(Documento.fecha_subida.desc())
        .all()
    )
    por_requisito = {}
    for documento in documentos:
        if documento.requisito_codigo not in por_requisito:
            por_requisito[documento.requisito_codigo] = documento

    items = []
    cargados = 0
    validados = 0
    for requisito in DOCUMENTOS_REQUERIDOS:
        documento = por_requisito.get(requisito["codigo"])
        estado = "Falta cargar"
        necesita_atencion = False
        if documento:
            cargados += 1
            estado = documento.estado
            necesita_atencion = documento.estado in {"Observado", "Requiere correccion", "Rechazado"}
            if documento.estado in {"Aprobado", "Validado para repositorio"}:
                validados += 1

        items.append(
            {
                "requisito": requisito,
                "documento": documento,
                "estado": estado,
                "necesita_atencion": necesita_atencion,
            }
        )

    total = len(DOCUMENTOS_REQUERIDOS)
    faltantes = total - cargados
    return {
        "items": items,
        "total": total,
        "cargados": cargados,
        "faltantes": faltantes,
        "validados": validados,
        "porcentaje_carga": round((cargados / total) * 100) if total else 0,
        "porcentaje_validacion": round((validados / total) * 100) if total else 0,
    }


def obtener_cumplimiento_requisitos_admin(db: Session) -> list[dict]:
    total_cargadores = db.query(Usuario).filter(Usuario.rol == "cargador", Usuario.activo.is_(True)).count()
    total_cargadores = max(total_cargadores, 1)
    resultados = []
    for requisito in DOCUMENTOS_REQUERIDOS:
        usuarios_con_carga = (
            db.query(func.count(func.distinct(Documento.usuario_id)))
            .filter(
                Documento.requisito_codigo == requisito["codigo"],
                Documento.usuario_id.isnot(None),
                Documento.estado.in_(ESTADOS_CARGA_VALIDA),
            )
            .scalar()
            or 0
        )
        validados = (
            db.query(func.count(func.distinct(Documento.usuario_id)))
            .filter(
                Documento.requisito_codigo == requisito["codigo"],
                Documento.usuario_id.isnot(None),
                Documento.estado.in_(["Aprobado", "Validado para repositorio"]),
            )
            .scalar()
            or 0
        )
        resultados.append(
            {
                "requisito": requisito,
                "cargados": usuarios_con_carga,
                "validados": validados,
                "porcentaje_carga": round((usuarios_con_carga / total_cargadores) * 100),
                "porcentaje_validacion": round((validados / total_cargadores) * 100),
            }
        )
    return resultados


def serie_barras(items: list[tuple[str, int]], total: int | None = None) -> list[dict]:
    maximo = total or max((valor for _, valor in items), default=1) or 1
    return [
        {
            "label": label,
            "value": valor,
            "percent": round((valor / maximo) * 100) if maximo else 0,
        }
        for label, valor in items
    ]


def aplicar_resultado_storage(documento: Documento, resultado: dict) -> None:
    """Copia al modelo los metadatos devueltos por el proveedor de archivos."""

    documento.nombre_guardado = resultado["nombre_guardado"]
    documento.ruta_archivo = resultado["ruta_archivo"]
    documento.storage_provider = resultado["storage_provider"]
    documento.storage_path = resultado.get("storage_path")
    documento.storage_url = resultado.get("storage_url")
    documento.onedrive_item_id = resultado.get("onedrive_item_id")
    documento.onedrive_drive_id = resultado.get("onedrive_drive_id")
    documento.onedrive_web_url = resultado.get("onedrive_web_url")
    documento.onedrive_path = resultado.get("onedrive_path")
    documento.sync_status = resultado.get("sync_status") or "local"
    documento.sync_error = resultado.get("sync_error")
    documento.fecha_sync = resultado.get("fecha_sync")
    documento.fecha_actualizacion = datetime.utcnow()


def reintentar_sincronizacion_onedrive(documento: Documento) -> None:
    """Intenta subir a OneDrive un archivo que ya existe en almacenamiento local."""

    ruta = Path(documento.ruta_archivo)
    if not ruta.is_absolute():
        ruta = settings.BASE_DIR / ruta
    if not ruta.exists():
        raise HTTPException(status_code=404, detail="No existe el archivo local para sincronizar")

    provider = OneDriveStorageProvider()
    resultado = provider.upload_local_file(
        ruta,
        nombre_guardado=documento.nombre_guardado,
        dependencia=documento.dependencia,
        tipo_documento=documento.tipo_documento,
        anio=documento.anio,
    )
    documento.onedrive_item_id = resultado.get("onedrive_item_id")
    documento.onedrive_drive_id = resultado.get("onedrive_drive_id")
    documento.onedrive_web_url = resultado.get("onedrive_web_url")
    documento.onedrive_path = resultado.get("onedrive_path")
    documento.storage_url = resultado.get("storage_url")
    documento.sync_status = "synced"
    documento.sync_error = None
    documento.fecha_sync = resultado.get("fecha_sync")
    documento.fecha_actualizacion = datetime.utcnow()


@router.get("/")
def index(request: Request, db: Session = Depends(get_db)):
    return render_template(
        request,
        db,
        "index.html",
        {
            "metricas": obtener_metricas(db) if usuario_actual(request, db) else None,
        },
    )


@router.get("/login")
def login_general():
    return RedirectResponse(url="/portal/login", status_code=303)


@router.get("/portal/login")
def mostrar_login_portal(
    request: Request,
    next: Optional[str] = None,
    error: Optional[str] = None,
    db: Session = Depends(get_db),
):
    return render_template(
        request,
        db,
        "login.html",
        {
            "area": "portal",
            "titulo": "Portal de carga documental",
            "subtitulo": "Ingrese para cargar documentos y revisar el estado de sus entregas.",
            "accion": "/portal/login",
            "next": next or "/portal",
            "error": error,
            "usuario_demo": "docente",
            "clave_demo": "Docente123",
        },
    )


@router.post("/portal/login")
def login_portal(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    usuario = authenticate_user(db, username, password)
    if not usuario or usuario.rol not in ROLES_PORTAL:
        return RedirectResponse(
            url="/portal/login?error=Credenciales invalidas o usuario sin acceso al portal",
            status_code=303,
        )
    iniciar_sesion(request, usuario)
    return RedirectResponse(url=siguiente_url_segura(next, "/portal"), status_code=303)


@router.get("/admin/login")
def mostrar_login_admin(
    request: Request,
    next: Optional[str] = None,
    error: Optional[str] = None,
    db: Session = Depends(get_db),
):
    return render_template(
        request,
        db,
        "login.html",
        {
            "area": "admin",
            "titulo": "Administracion VIDI",
            "subtitulo": "Acceso interno para supervisar, validar y analizar documentos.",
            "accion": "/admin/login",
            "next": next or "/admin",
            "error": error,
            "usuario_demo": "admin",
            "clave_demo": "Admin123",
        },
    )


@router.post("/admin/login")
def login_admin(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    usuario = authenticate_user(db, username, password)
    if not usuario or usuario.rol not in ROLES_ADMIN:
        return RedirectResponse(
            url="/admin/login?error=Credenciales invalidas o usuario sin acceso administrativo",
            status_code=303,
        )
    iniciar_sesion(request, usuario)
    return RedirectResponse(url=siguiente_url_segura(next, "/admin"), status_code=303)


@router.get("/logout")
@router.get("/portal/logout")
@router.get("/admin/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)


@router.get("/portal")
def portal_dashboard(request: Request, db: Session = Depends(get_db)):
    usuario, redirect = requerir_roles(request, db, ROLES_PORTAL, "/portal/login")
    if redirect:
        return redirect

    documentos = (
        consulta_documentos_usuario(db, usuario)
        .order_by(Documento.fecha_subida.desc())
        .all()
    )
    documentos_con_pendientes = [
        {"documento": documento, "pendientes": campos_pendientes(documento)}
        for documento in documentos
    ]

    return render_template(
        request,
        db,
        "portal_dashboard.html",
        {
            "usuario": usuario,
            "metricas": obtener_metricas_usuario(db, usuario),
            "documentos_con_pendientes": documentos_con_pendientes,
            "progreso_requisitos": obtener_progreso_requisitos_usuario(db, usuario),
        },
    )


@router.get("/subir")
def redirigir_subir_legacy():
    return RedirectResponse(url="/portal/nuevo", status_code=303)


@router.get("/portal/nuevo")
def mostrar_formulario_subida(request: Request, db: Session = Depends(get_db)):
    usuario, redirect = requerir_roles(request, db, ROLES_PORTAL, "/portal/login")
    if redirect:
        return redirect

    requisito_codigo = request.query_params.get("requisito")
    requisito = obtener_requisito(requisito_codigo)

    return render_template(
        request,
        db,
        "portal_carga.html",
        {
            **contexto_opciones(),
            "usuario": usuario,
            "requisito_preseleccionado": requisito,
            "anio_actual": datetime.utcnow().year,
        },
    )


@router.post("/subir")
@router.post("/portal/nuevo")
def recibir_documento_portal(
    request: Request,
    docente: str = Form(...),
    correo: str = Form(...),
    dependencia: str = Form(...),
    tipo_documento: str = Form(...),
    anio: int = Form(...),
    periodo: str = Form(...),
    archivo: UploadFile = File(...),
    requisito_codigo: Optional[str] = Form(None),
    cargo_responsable: Optional[str] = Form(None),
    telefono: Optional[str] = Form(None),
    identificacion: Optional[str] = Form(None),
    proceso_institucional: Optional[str] = Form(None),
    programa_proyecto: Optional[str] = Form(None),
    linea_investigacion: Optional[str] = Form(None),
    numero_documento: Optional[str] = Form(None),
    fecha_documento: Optional[str] = Form(None),
    descripcion: Optional[str] = Form(None),
    palabras_clave: Optional[str] = Form(None),
    nivel_confidencialidad: Optional[str] = Form(None),
    prioridad: str = Form("Normal"),
    requiere_respuesta: Optional[str] = Form(None),
    observacion_usuario: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    usuario, redirect = requerir_roles(request, db, ROLES_PORTAL, "/portal/login")
    if redirect:
        return redirect

    requisito = obtener_requisito(requisito_codigo)

    if not archivo.filename:
        raise HTTPException(status_code=400, detail="Debe seleccionar un archivo")
    if prioridad not in PRIORIDADES:
        raise HTTPException(status_code=400, detail="Prioridad no permitida")
    if tipo_documento not in TIPOS_DOCUMENTO:
        raise HTTPException(status_code=400, detail="Tipo de documento no permitido")

    documento = Documento(
        usuario_id=usuario.id,
        requisito_codigo=requisito["codigo"] if requisito else None,
        nombre_original=archivo.filename,
        docente=docente.strip() or usuario.nombre,
        correo=correo.strip().lower() or usuario.correo,
        cargo_responsable=limpiar_opcional(cargo_responsable),
        telefono=limpiar_opcional(telefono),
        identificacion=limpiar_opcional(identificacion),
        dependencia=dependencia.strip(),
        tipo_documento=tipo_documento.strip(),
        proceso_institucional=limpiar_opcional(proceso_institucional),
        programa_proyecto=limpiar_opcional(programa_proyecto),
        linea_investigacion=limpiar_opcional(linea_investigacion),
        numero_documento=limpiar_opcional(numero_documento),
        fecha_documento=convertir_fecha(fecha_documento),
        anio=anio,
        periodo=periodo.strip(),
        descripcion=limpiar_opcional(descripcion),
        palabras_clave=limpiar_opcional(palabras_clave),
        nivel_confidencialidad=limpiar_opcional(nivel_confidencialidad),
        prioridad=prioridad,
        requiere_respuesta=requiere_respuesta == "on",
        observacion_usuario=limpiar_opcional(observacion_usuario),
        observacion=limpiar_opcional(observacion_usuario),
        estado=settings.DEFAULT_ESTADO,
        canal_origen="Portal de carga",
        storage_provider=settings.STORAGE_PROVIDER,
    )

    # Primero se registra para obtener un ID estable para el nombre del archivo.
    db.add(documento)
    db.commit()
    db.refresh(documento)

    documento.codigo_seguimiento = generar_codigo_seguimiento(documento.anio, documento.id)

    try:
        resultado = storage_service.save(
            archivo,
            documento_id=documento.id,
            dependencia=documento.dependencia,
            tipo_documento=documento.tipo_documento,
            anio=documento.anio,
        )
    except Exception as exc:
        db.delete(documento)
        db.commit()
        raise HTTPException(status_code=500, detail=f"No se pudo guardar el archivo: {exc}") from exc

    aplicar_resultado_storage(documento, resultado)

    db.commit()

    return RedirectResponse(
        url=f"/portal/enviado/{documento.id}",
        status_code=303,
    )


@router.get("/portal/enviado/{documento_id}")
def confirmar_envio(documento_id: int, request: Request, db: Session = Depends(get_db)):
    usuario, redirect = requerir_roles(request, db, ROLES_PORTAL, "/portal/login")
    if redirect:
        return redirect

    documento = obtener_documento_del_usuario_o_404(documento_id, usuario, db)
    return render_template(
        request,
        db,
        "confirmacion_carga.html",
        {
            "documento": documento,
            "pendientes": campos_pendientes(documento),
        },
    )


@router.get("/portal/documentos/{documento_id}")
def detalle_documento_portal(
    documento_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    usuario, redirect = requerir_roles(request, db, ROLES_PORTAL, "/portal/login")
    if redirect:
        return redirect

    documento = obtener_documento_del_usuario_o_404(documento_id, usuario, db)
    return render_template(
        request,
        db,
        "portal_detalle.html",
        {
            "documento": documento,
            "pendientes": campos_pendientes(documento),
            "requisito": obtener_requisito(documento.requisito_codigo),
        },
    )


@router.get("/portal/documentos/{documento_id}/descargar")
def descargar_documento_portal(
    documento_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    usuario, redirect = requerir_roles(request, db, ROLES_PORTAL, "/portal/login")
    if redirect:
        return redirect

    documento = obtener_documento_del_usuario_o_404(documento_id, usuario, db)
    return responder_archivo(documento)


@router.get("/admin")
def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    usuario, redirect = requerir_roles(request, db, ROLES_ADMIN, "/admin/login")
    if redirect:
        return redirect

    documentos_recientes = (
        db.query(Documento).order_by(Documento.fecha_subida.desc()).limit(8).all()
    )
    documentos_por_estado = (
        db.query(Documento.estado, func.count(Documento.id))
        .group_by(Documento.estado)
        .order_by(func.count(Documento.id).desc())
        .all()
    )
    documentos_por_dependencia = (
        db.query(Documento.dependencia, func.count(Documento.id))
        .group_by(Documento.dependencia)
        .order_by(func.count(Documento.id).desc())
        .limit(8)
        .all()
    )
    documentos_por_tipo = (
        db.query(Documento.tipo_documento, func.count(Documento.id))
        .group_by(Documento.tipo_documento)
        .order_by(func.count(Documento.id).desc())
        .limit(8)
        .all()
    )

    return render_template(
        request,
        db,
        "supervision_dashboard.html",
        {
            "metricas": obtener_metricas(db),
            "documentos_recientes": documentos_recientes,
            "documentos_por_estado": documentos_por_estado,
            "documentos_por_dependencia": documentos_por_dependencia,
            "serie_estado": serie_barras(documentos_por_estado),
            "serie_dependencia": serie_barras(documentos_por_dependencia),
            "serie_tipo": serie_barras(documentos_por_tipo),
            "cumplimiento_requisitos": obtener_cumplimiento_requisitos_admin(db),
        },
    )


@router.get("/supervision")
def redirigir_supervision_legacy():
    return RedirectResponse(url="/admin", status_code=303)


@router.get("/documentos")
@router.get("/supervision/documentos")
def redirigir_documentos_legacy():
    return RedirectResponse(url="/admin/documentos", status_code=303)


@router.get("/admin/documentos")
def listar_documentos_admin(
    request: Request,
    anio: Optional[int] = None,
    dependencia: Optional[str] = None,
    tipo_documento: Optional[str] = None,
    estado: Optional[str] = None,
    periodo: Optional[str] = None,
    proceso_institucional: Optional[str] = None,
    prioridad: Optional[str] = None,
    nivel_confidencialidad: Optional[str] = None,
    q: Optional[str] = None,
    mensaje: Optional[str] = None,
    db: Session = Depends(get_db),
):
    usuario, redirect = requerir_roles(request, db, ROLES_ADMIN, "/admin/login")
    if redirect:
        return redirect

    consulta = construir_consulta_documentos(
        db,
        anio=anio,
        dependencia=dependencia,
        tipo_documento=tipo_documento,
        estado=estado,
        periodo=periodo,
        proceso_institucional=proceso_institucional,
        prioridad=prioridad,
        nivel_confidencialidad=nivel_confidencialidad,
        q=q,
    )
    documentos = consulta.order_by(Documento.fecha_subida.desc()).all()

    return render_template(
        request,
        db,
        "supervision_documentos.html",
        {
            "documentos": documentos,
            "metricas": obtener_metricas(db),
            **contexto_opciones(),
            "filtros": {
                "anio": anio or "",
                "dependencia": dependencia or "",
                "tipo_documento": tipo_documento or "",
                "estado": estado or "",
                "periodo": periodo or "",
                "proceso_institucional": proceso_institucional or "",
                "prioridad": prioridad or "",
                "nivel_confidencialidad": nivel_confidencialidad or "",
                "q": q or "",
            },
            "mensaje": mensaje,
        },
    )


@router.get("/admin/sincronizacion")
def panel_sincronizacion(
    request: Request,
    estado: Optional[str] = None,
    db: Session = Depends(get_db),
):
    usuario, redirect = requerir_roles(request, db, ROLES_ADMIN, "/admin/login")
    if redirect:
        return redirect

    consulta = db.query(Documento)
    if estado:
        consulta = consulta.filter(Documento.sync_status == estado)

    documentos = consulta.order_by(Documento.fecha_subida.desc()).all()
    return render_template(
        request,
        db,
        "sincronizacion.html",
        {
            "documentos": documentos,
            "metricas": obtener_metricas(db),
            "estado": estado or "",
        },
    )


@router.post("/admin/documentos/{documento_id}/sincronizar")
def sincronizar_documento(
    documento_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    usuario, redirect = requerir_roles(request, db, ROLES_ADMIN, "/admin/login")
    if redirect:
        return redirect

    documento = obtener_documento_o_404(documento_id, db)
    try:
        reintentar_sincronizacion_onedrive(documento)
    except Exception as exc:
        documento.sync_status = "error"
        documento.sync_error = str(exc)
        documento.fecha_actualizacion = datetime.utcnow()
    db.commit()

    return RedirectResponse(url="/admin/sincronizacion", status_code=303)


@router.get("/documentos/{documento_id}")
@router.get("/supervision/documentos/{documento_id}")
def redirigir_detalle_legacy(documento_id: int):
    return RedirectResponse(url=f"/admin/documentos/{documento_id}", status_code=303)


@router.get("/admin/documentos/{documento_id}")
def detalle_documento_admin(
    documento_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    usuario, redirect = requerir_roles(request, db, ROLES_ADMIN, "/admin/login")
    if redirect:
        return redirect

    documento = obtener_documento_o_404(documento_id, db)
    return render_template(
        request,
        db,
        "detalle_documento.html",
        {
            "documento": documento,
            "pendientes": campos_pendientes(documento),
            "requisito": obtener_requisito(documento.requisito_codigo),
        },
    )


@router.get("/documentos/{documento_id}/validar")
@router.get("/supervision/documentos/{documento_id}/validar")
def redirigir_validacion_legacy(documento_id: int):
    return RedirectResponse(url=f"/admin/documentos/{documento_id}/validar", status_code=303)


@router.get("/admin/documentos/{documento_id}/validar")
def mostrar_validacion(
    documento_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    usuario, redirect = requerir_roles(request, db, ROLES_ADMIN, "/admin/login")
    if redirect:
        return redirect

    documento = obtener_documento_o_404(documento_id, db)
    return render_template(
        request,
        db,
        "validar_documento.html",
        {
            "documento": documento,
            "estados": ESTADOS_DOCUMENTO,
            "prioridades": PRIORIDADES,
            "pendientes": campos_pendientes(documento),
        },
    )


@router.post("/documentos/{documento_id}/validar")
@router.post("/supervision/documentos/{documento_id}/validar")
@router.post("/admin/documentos/{documento_id}/validar")
def validar_documento(
    documento_id: int,
    request: Request,
    estado: str = Form(...),
    observacion_validacion: Optional[str] = Form(None),
    usuario_validador: Optional[str] = Form(None),
    prioridad: Optional[str] = Form(None),
    requiere_respuesta: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    usuario, redirect = requerir_roles(request, db, ROLES_ADMIN, "/admin/login")
    if redirect:
        return redirect

    if estado not in ESTADOS_DOCUMENTO:
        raise HTTPException(status_code=400, detail="Estado de validacion no permitido")
    if prioridad and prioridad not in PRIORIDADES:
        raise HTTPException(status_code=400, detail="Prioridad no permitida")

    documento = obtener_documento_o_404(documento_id, db)
    documento.estado = estado
    documento.observacion_validacion = limpiar_opcional(observacion_validacion)
    documento.observacion = limpiar_opcional(observacion_validacion)
    documento.usuario_validador = limpiar_opcional(usuario_validador) or usuario.nombre
    documento.prioridad = prioridad or documento.prioridad or "Normal"
    documento.requiere_respuesta = requiere_respuesta == "on"
    documento.fecha_validacion = datetime.utcnow()
    documento.fecha_actualizacion = datetime.utcnow()

    db.commit()

    return RedirectResponse(
        url=f"/admin/documentos/{documento.id}?mensaje=Validacion guardada",
        status_code=303,
    )


@router.get("/documentos/{documento_id}/descargar")
@router.get("/supervision/documentos/{documento_id}/descargar")
@router.get("/admin/documentos/{documento_id}/descargar")
def descargar_documento_admin(
    documento_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    usuario, redirect = requerir_roles(request, db, ROLES_ADMIN, "/admin/login")
    if redirect:
        return redirect

    documento = obtener_documento_o_404(documento_id, db)
    return responder_archivo(documento)


def responder_archivo(documento: Documento) -> FileResponse:
    ruta = Path(documento.ruta_archivo)
    if not ruta.is_absolute():
        ruta = settings.BASE_DIR / ruta

    if not ruta.exists() or not ruta.is_file():
        raise HTTPException(status_code=404, detail="Archivo fisico no encontrado")

    return FileResponse(
        path=str(ruta),
        filename=documento.nombre_original,
        media_type="application/octet-stream",
    )
