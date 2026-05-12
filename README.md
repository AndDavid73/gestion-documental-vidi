# Sistema de Gestion Documental VIDI

Prototipo local para registrar, organizar y validar documentos institucionales del Vicerrectorado de Investigacion.

La version actual usa FastAPI, SQLAlchemy, Jinja2, Bootstrap, autenticacion por sesion, almacenamiento local y sincronizacion opcional con OneDrive mediante Microsoft Graph. En local puede usar SQLite; en produccion se recomienda PostgreSQL. Los archivos no se guardan dentro de la base de datos: la base conserva metadatos, rutas y estado de sincronizacion.

## Arquitectura inicial

```text
Portal / Admin
  -> FastAPI
  -> SQLAlchemy
  -> PostgreSQL o SQLite
  -> StorageService
  -> LocalStorageProvider
  -> OneDriveStorageProvider
  -> storage/ + OneDrive
```

La variable `STORAGE_PROVIDER` permite preparar el cambio futuro de proveedor:

```bash
STORAGE_PROVIDER=local
```

Para guardar local y sincronizar con OneDrive:

```bash
STORAGE_PROVIDER=local_onedrive
```

## Estructura del proyecto

```text
app/
  main.py
  config.py
  database.py
  models.py
  routes/
    documentos.py
  services/
    storage_service.py
  storage_providers/
    local_storage.py
    onedrive_storage.py
    mirror_storage.py
    sharepoint_storage.py
  templates/
  static/
storage/
database/
requirements.txt
Dockerfile
docker-compose.yml
render.yaml
.env.example
.gitignore
README.md
```

## Instalacion local

Crear y activar entorno virtual:

```bash
python -m venv .venv
source .venv/bin/activate
```

En Windows:

```bash
.venv\Scripts\activate
```

Instalar dependencias:

```bash
pip install -r requirements.txt
```

Crear variables locales:

```bash
cp .env.example .env
```

Ejecutar la aplicacion:

```bash
uvicorn app.main:app --reload
```

Abrir:

- Aplicacion: <http://127.0.0.1:8000>
- Documentacion API: <http://127.0.0.1:8000/docs>

## Ejecutar con Docker

```bash
cp .env.example .env
docker compose up --build
```

Abrir:

- <http://127.0.0.1:8000>

## Accesos de prueba

El prototipo crea dos usuarios locales al iniciar:

| Sistema | Usuario | Contrasena | Rol |
| --- | --- | --- | --- |
| Portal de carga | `docente` | `Docente123` | Cargador |
| Administracion VIDI | `admin` | `Admin123` | Administrador |

Estas credenciales son solo para desarrollo local. En produccion deben cambiarse
y la autenticacion deberia conectarse a un sistema institucional.

## Rutas principales

La aplicacion esta organizada en dos espacios:

1. **Portal de carga**: enlace para docentes, investigadores o responsables de dependencia.
2. **Supervision**: plataforma interna para recibir, revisar, filtrar, descargar y validar documentos.

- `GET /`: pagina de inicio.
- `GET /portal/login`: inicio de sesion de usuarios cargadores.
- `GET /portal`: escritorio del usuario cargador con sus documentos.
- `GET /portal/nuevo`: formulario de carga documental.
- `POST /portal/nuevo`: guarda archivo localmente y registra metadatos asociados al usuario.
- `GET /portal/enviado/{id}`: confirmacion con codigo de seguimiento.
- `GET /portal/documentos/{id}`: seguimiento visible para el usuario que subio el documento.
- `GET /admin/login`: inicio de sesion del sistema interno.
- `GET /admin`: panel interno con indicadores.
- `GET /admin/documentos`: bandeja documental con filtros.
- `GET /admin/documentos/{id}`: detalle completo del documento.
- `GET /admin/documentos/{id}/validar`: pantalla de validacion.
- `POST /admin/documentos/{id}/validar`: actualiza estado, prioridad y observaciones.
- `GET /admin/documentos/{id}/descargar`: descarga el archivo almacenado.
- `GET /admin/sincronizacion`: panel de sincronizacion local / OneDrive.
- `POST /admin/documentos/{id}/sincronizar`: reintenta subir un documento a OneDrive.

Las rutas antiguas `/subir` y `/documentos` siguen disponibles como compatibilidad,
pero la recomendacion es usar `/portal` y `/admin`.

## Metadatos registrados

El prototipo registra datos del responsable, dependencia, proceso institucional,
tipo documental, anio, periodo, prioridad, confidencialidad, proyecto o actividad,
linea de investigacion, numero de referencia, descripcion, palabras clave, ruta de
almacenamiento, estado de validacion, observaciones y usuario validador.

## Entregables requeridos del portal docente

El portal docente incluye una lista inicial de documentos esperados para medir
avance de cumplimiento:

- Articulo cientifico publicado o aceptado.
- Informe de avance de proyecto de investigacion.
- Evidencia PAP/PAC.
- Reporte de gestion de investigacion.
- Acta o resolucion de comite.
- Evidencia para evaluacion o acreditacion.

Cada carga puede asociarse a uno de estos entregables o registrarse como
documento libre. El escritorio del docente calcula porcentaje cargado, porcentaje
validado, documentos faltantes y documentos que requieren correccion.

El panel administrativo muestra indicadores tipo tablero: documentos por estado,
dependencia, tipo documental y cumplimiento de entregables requeridos.

## Almacenamiento local

Los archivos se guardan con esta estructura:

```text
storage/ANIO/DEPENDENCIA/TIPO_DOCUMENTO/UCE_DEPENDENCIA_ANIO_TIPO_0001.ext
```

## Almacenamiento local + OneDrive

Cuando `STORAGE_PROVIDER=local_onedrive`, el sistema:

1. Guarda el archivo en `storage/`.
2. Intenta subir una copia a OneDrive mediante Microsoft Graph.
3. Si OneDrive responde bien, marca `sync_status=synced` y guarda la URL.
4. Si OneDrive falla, conserva el archivo local y marca `sync_status=error`.
5. El administrador puede reintentar desde `/admin/sincronizacion`.

Variables necesarias:

```env
STORAGE_PROVIDER=local_onedrive
MICROSOFT_TENANT_ID=
MICROSOFT_CLIENT_ID=
MICROSOFT_CLIENT_SECRET=
ONEDRIVE_DRIVE_ID=
ONEDRIVE_BASE_FOLDER=VIDI_DOCUMENTOS
```

Para obtener estas variables debes registrar una aplicacion en Microsoft Entra ID
y darle permisos de Microsoft Graph para escribir en el drive institucional.
La carga usa Microsoft Graph con `PUT .../content` para archivos pequenos y
`createUploadSession` para archivos grandes.

## Despliegue en Render

El repositorio incluye `Dockerfile` y `render.yaml`.

Pasos:

1. Crear repositorio en GitHub.
2. Subir el codigo:

```bash
git add .
git commit -m "Preparar despliegue online VIDI"
git branch -M main
git remote add origin URL_DE_TU_REPOSITORIO
git push -u origin main
```

3. Entrar a Render y crear un Blueprint desde el repositorio.
4. Render creara el servicio web y una base PostgreSQL.
5. El blueprint incluye un disco persistente en `/app/storage` para conservar la copia local del servidor. En Render los discos persistentes requieren un servicio de pago.
6. En Environment Variables completar:

```env
APP_BASE_URL=https://tu-app.onrender.com
MICROSOFT_TENANT_ID=...
MICROSOFT_CLIENT_ID=...
MICROSOFT_CLIENT_SECRET=...
ONEDRIVE_DRIVE_ID=...
ONEDRIVE_BASE_FOLDER=VIDI_DOCUMENTOS
```

Render desplegara la app con Docker. El comando interno usa:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## Notas importantes de produccion

- No subir `.env`.
- Cambiar `SECRET_KEY`.
- Cambiar usuarios y contrasenas demo.
- Usar PostgreSQL, no SQLite.
- Configurar backups de base de datos.
- Confirmar permisos institucionales de Microsoft Graph antes de usar OneDrive.

Ejemplo:

```text
storage/2025/FACULTAD_DE_CIENCIAS/ARTICULO/UCE_FACULTAD_DE_CIENCIAS_2025_ARTICULO_0001.pdf
```

## GitHub

Este repositorio debe subir codigo, plantillas y configuracion base. No debe subir documentos institucionales, base de datos real ni variables sensibles.

El `.gitignore` excluye:

- `.venv/`
- `.env`
- `storage/*`
- `database/*`
- `__pycache__/`
- archivos `.pyc`

Se conservan `storage/.gitkeep` y `database/.gitkeep` para mantener la estructura vacia en Git.

## Siguientes fases sugeridas

1. Agregar login y roles.
2. Separar observaciones del usuario e historial de validacion.
3. Exportar consultas a Excel.
4. Migrar SQLite a PostgreSQL.
5. Implementar proveedores externos: OneDrive, SharePoint, Google Drive, Azure Blob Storage o S3.
6. Construir dashboard de seguimiento institucional.
