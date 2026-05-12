from pathlib import Path
import shutil
import unicodedata

from fastapi import UploadFile

from app.config import settings


def limpiar_segmento(valor: str) -> str:
    """Normaliza nombres de carpetas y archivos para almacenamiento local."""

    texto = unicodedata.normalize("NFKD", str(valor))
    texto = "".join(caracter for caracter in texto if not unicodedata.combining(caracter))
    texto = texto.upper().strip()

    caracteres_limpios = []
    for caracter in texto:
        if caracter.isalnum():
            caracteres_limpios.append(caracter)
        elif caracter in {" ", "-", "_", "/"}:
            caracteres_limpios.append("_")

    normalizado = "".join(caracteres_limpios)
    while "__" in normalizado:
        normalizado = normalizado.replace("__", "_")

    return normalizado.strip("_") or "SIN_CLASIFICAR"


class LocalStorageProvider:
    """Proveedor local para el prototipo inicial."""

    provider_name = "local"

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or settings.STORAGE_DIR

    def save_file(
        self,
        archivo: UploadFile,
        *,
        documento_id: int,
        dependencia: str,
        tipo_documento: str,
        anio: int,
    ) -> dict:
        dependencia_limpia = limpiar_segmento(dependencia)
        tipo_limpio = limpiar_segmento(tipo_documento)
        anio_limpio = limpiar_segmento(str(anio))

        extension = Path(archivo.filename or "").suffix.lower()
        nombre_guardado = (
            f"UCE_{dependencia_limpia}_{anio_limpio}_{tipo_limpio}_{documento_id:04d}{extension}"
        )

        carpeta_destino = self.base_dir / anio_limpio / dependencia_limpia / tipo_limpio
        carpeta_destino.mkdir(parents=True, exist_ok=True)

        ruta_destino = carpeta_destino / nombre_guardado
        archivo.file.seek(0)
        with ruta_destino.open("wb") as buffer:
            shutil.copyfileobj(archivo.file, buffer)

        ruta_relativa = ruta_destino.relative_to(settings.BASE_DIR).as_posix()

        return {
            "nombre_guardado": nombre_guardado,
            "ruta_archivo": ruta_relativa,
            "storage_provider": self.provider_name,
            "storage_path": ruta_relativa,
            "storage_url": None,
            "local_path": str(ruta_destino),
            "onedrive_item_id": None,
            "onedrive_drive_id": None,
            "onedrive_web_url": None,
            "onedrive_path": None,
            "sync_status": "local",
            "sync_error": None,
            "fecha_sync": None,
        }
