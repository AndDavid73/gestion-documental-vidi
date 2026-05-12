from fastapi import UploadFile


class SharePointStorageProvider:
    """Marcador para una futura integracion con SharePoint."""

    provider_name = "sharepoint"

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
            "SharePointStorageProvider aun no esta implementado. Use STORAGE_PROVIDER=local."
        )

