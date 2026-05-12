from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from fastapi import UploadFile
import requests

from app.config import settings
from app.storage_providers.local_storage import limpiar_segmento


class OneDriveConfigError(RuntimeError):
    """Error de configuracion de Microsoft Graph / OneDrive."""


class OneDriveStorageProvider:
    """Proveedor OneDrive usando Microsoft Graph.

    Requiere una app registrada en Microsoft Entra ID con permisos para escribir
    en el drive configurado. El prototipo usa client credentials.
    """

    provider_name = "onedrive"
    graph_base_url = "https://graph.microsoft.com/v1.0"

    def __init__(self) -> None:
        self.tenant_id = settings.MICROSOFT_TENANT_ID
        self.client_id = settings.MICROSOFT_CLIENT_ID
        self.client_secret = settings.MICROSOFT_CLIENT_SECRET
        self.drive_id = settings.ONEDRIVE_DRIVE_ID
        self.base_folder = settings.ONEDRIVE_BASE_FOLDER.strip("/")
        self.chunk_size = settings.ONEDRIVE_UPLOAD_CHUNK_SIZE

    def _validate_config(self) -> None:
        missing = [
            name
            for name, value in {
                "MICROSOFT_TENANT_ID": self.tenant_id,
                "MICROSOFT_CLIENT_ID": self.client_id,
                "MICROSOFT_CLIENT_SECRET": self.client_secret,
                "ONEDRIVE_DRIVE_ID": self.drive_id,
            }.items()
            if not value
        ]
        if missing:
            raise OneDriveConfigError(
                "Faltan variables de OneDrive: " + ", ".join(missing)
            )

    def _get_access_token(self) -> str:
        self._validate_config()
        response = requests.post(
            f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token",
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials",
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["access_token"]

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._get_access_token()}"}

    def _remote_path(
        self,
        *,
        nombre_guardado: str,
        dependencia: str,
        tipo_documento: str,
        anio: int,
    ) -> str:
        partes = [
            self.base_folder,
            limpiar_segmento(str(anio)),
            limpiar_segmento(dependencia),
            limpiar_segmento(tipo_documento),
            nombre_guardado,
        ]
        return "/".join(parte for parte in partes if parte)

    def _encode_remote_path(self, remote_path: str) -> str:
        return "/".join(quote(segment, safe="") for segment in remote_path.split("/"))

    def upload_local_file(
        self,
        local_path: str | Path,
        *,
        nombre_guardado: str,
        dependencia: str,
        tipo_documento: str,
        anio: int,
    ) -> dict:
        local_path = Path(local_path)
        remote_path = self._remote_path(
            nombre_guardado=nombre_guardado,
            dependencia=dependencia,
            tipo_documento=tipo_documento,
            anio=anio,
        )

        if local_path.stat().st_size <= 4 * 1024 * 1024:
            item = self._upload_small_file(local_path, remote_path)
        else:
            item = self._upload_large_file(local_path, remote_path)

        return {
            "onedrive_item_id": item.get("id"),
            "onedrive_drive_id": self.drive_id,
            "onedrive_web_url": item.get("webUrl"),
            "onedrive_path": remote_path,
            "storage_url": item.get("webUrl"),
            "sync_status": "synced",
            "sync_error": None,
            "fecha_sync": datetime.utcnow(),
        }

    def _upload_small_file(self, local_path: Path, remote_path: str) -> dict:
        encoded_path = self._encode_remote_path(remote_path)
        url = (
            f"{self.graph_base_url}/drives/{self.drive_id}"
            f"/root:/{encoded_path}:/content"
        )
        with local_path.open("rb") as file_buffer:
            response = requests.put(
                url,
                headers=self._headers(),
                data=file_buffer,
                timeout=120,
            )
        response.raise_for_status()
        return response.json()

    def _upload_large_file(self, local_path: Path, remote_path: str) -> dict:
        encoded_path = self._encode_remote_path(remote_path)
        session_url = (
            f"{self.graph_base_url}/drives/{self.drive_id}"
            f"/root:/{encoded_path}:/createUploadSession"
        )
        session_response = requests.post(
            session_url,
            headers={
                **self._headers(),
                "Content-Type": "application/json",
            },
            json={"item": {"@microsoft.graph.conflictBehavior": "replace"}},
            timeout=60,
        )
        session_response.raise_for_status()
        upload_url = session_response.json()["uploadUrl"]

        total_size = local_path.stat().st_size
        with local_path.open("rb") as file_buffer:
            start = 0
            while start < total_size:
                chunk = file_buffer.read(self.chunk_size)
                end = start + len(chunk) - 1
                response = requests.put(
                    upload_url,
                    headers={
                        "Content-Length": str(len(chunk)),
                        "Content-Range": f"bytes {start}-{end}/{total_size}",
                    },
                    data=chunk,
                    timeout=180,
                )
                if response.status_code not in {200, 201, 202}:
                    response.raise_for_status()
                if response.status_code in {200, 201}:
                    return response.json()
                start = end + 1

        raise RuntimeError("La sesion de carga de OneDrive finalizo sin respuesta final.")

    def save_file(
        self,
        archivo: UploadFile,
        *,
        documento_id: int,
        dependencia: str,
        tipo_documento: str,
        anio: int,
    ) -> dict:
        raise NotImplementedError(
            "Use MirrorStorageProvider para guardar temporalmente local y subir a OneDrive."
        )
