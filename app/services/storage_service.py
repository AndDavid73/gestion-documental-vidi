from fastapi import UploadFile

from app.config import settings
from app.storage_providers.local_storage import LocalStorageProvider
from app.storage_providers.mirror_storage import MirrorStorageProvider
from app.storage_providers.onedrive_storage import OneDriveStorageProvider
from app.storage_providers.sharepoint_storage import SharePointStorageProvider


class StorageService:
    """Fachada para cambiar el almacenamiento sin tocar rutas o vistas."""

    def __init__(self) -> None:
        self.provider = self._build_provider(settings.STORAGE_PROVIDER)

    def _build_provider(self, provider_name: str):
        if provider_name == "local":
            return LocalStorageProvider()
        if provider_name in {"local_onedrive", "mirror", "local+onedrive"}:
            return MirrorStorageProvider()
        if provider_name == "onedrive":
            return OneDriveStorageProvider()
        if provider_name == "sharepoint":
            return SharePointStorageProvider()
        raise ValueError(f"Proveedor de almacenamiento no soportado: {provider_name}")

    def save(
        self,
        archivo: UploadFile,
        *,
        documento_id: int,
        dependencia: str,
        tipo_documento: str,
        anio: int,
    ) -> dict:
        """Guarda el archivo con el proveedor configurado."""

        return self.provider.save_file(
            archivo,
            documento_id=documento_id,
            dependencia=dependencia,
            tipo_documento=tipo_documento,
            anio=anio,
        )
