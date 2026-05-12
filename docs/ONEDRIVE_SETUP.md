# Configurar OneDrive con Microsoft Graph

Esta guia resume lo que debe crear el administrador de Microsoft 365 / Azure.

## 1. Registrar aplicacion

1. Entrar a Microsoft Entra ID.
2. Ir a **App registrations**.
3. Crear una nueva aplicacion, por ejemplo `VIDI Gestion Documental`.
4. Copiar:
   - `Application (client) ID`
   - `Directory (tenant) ID`

## 2. Crear secreto

1. Entrar a la aplicacion registrada.
2. Ir a **Certificates & secrets**.
3. Crear un **Client secret**.
4. Copiar el valor del secreto una sola vez.

## 3. Permisos Graph

Agregar permisos de aplicacion para Microsoft Graph, segun la politica institucional:

- `Files.ReadWrite.All`
- o permisos equivalentes restringidos para SharePoint/Drive si la universidad lo configura asi.

Despues, un administrador debe aprobar **Grant admin consent**.

## 4. Obtener Drive ID

El sistema necesita el ID del drive donde guardara documentos.

Puede ser un OneDrive institucional o una biblioteca de SharePoint. Para SharePoint
normalmente conviene usar el drive de una biblioteca documental institucional.

Con Microsoft Graph Explorer o una llamada API:

```http
GET https://graph.microsoft.com/v1.0/sites/{site-id}/drives
```

o si ya conoce el drive:

```http
GET https://graph.microsoft.com/v1.0/drives/{drive-id}
```

## 5. Variables de entorno

Configurar en `.env` local o en Render:

```env
STORAGE_PROVIDER=local_onedrive
MICROSOFT_TENANT_ID=...
MICROSOFT_CLIENT_ID=...
MICROSOFT_CLIENT_SECRET=...
ONEDRIVE_DRIVE_ID=...
ONEDRIVE_BASE_FOLDER=VIDI_DOCUMENTOS
```

## 6. Verificacion

1. Iniciar la app.
2. Subir un documento desde `/portal`.
3. Entrar a `/admin/sincronizacion`.
4. Revisar si aparece como `synced`.
5. Si aparece `error`, revisar `sync_error` y permisos Graph.
