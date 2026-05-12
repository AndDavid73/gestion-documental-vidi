from fastapi import UploadFile

from app.storage_providers.local_storage import LocalStorageProvider
from app.storage_providers.onedrive_storage import OneDriveStorageProvider


class MirrorStorageProvider:
    """Guarda localmente y luego intenta sincronizar con OneDrive."""

    provider_name = "local_onedrive"

    def __init__(self) -> None:
        self.local = LocalStorageProvider()
        self.onedrive = OneDriveStorageProvider()

    def save_file(
        self,
        archivo: UploadFile,
        *,
        documento_id: int,
        dependencia: str,
        tipo_documento: str,
        anio: int,
    ) -> dict:
        local_result = self.local.save_file(
            archivo,
            documento_id=documento_id,
            dependencia=dependencia,
            tipo_documento=tipo_documento,
            anio=anio,
        )
        local_result["storage_provider"] = self.provider_name

        try:
            onedrive_result = self.onedrive.upload_local_file(
                local_result["local_path"],
                nombre_guardado=local_result["nombre_guardado"],
                dependencia=dependencia,
                tipo_documento=tipo_documento,
                anio=anio,
            )
            local_result.update(onedrive_result)
            local_result["storage_url"] = onedrive_result["onedrive_web_url"]
            local_result["storage_path"] = local_result["ruta_archivo"]
            local_result["sync_status"] = "synced"
        except Exception as exc:
            local_result.update(
                {
                    "onedrive_item_id": None,
                    "onedrive_drive_id": None,
                    "onedrive_web_url": None,
                    "onedrive_path": None,
                    "sync_status": "error",
                    "sync_error": str(exc),
                    "fecha_sync": None,
                }
            )

        return local_result
