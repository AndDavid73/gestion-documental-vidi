import base64
import hashlib
import hmac
import os
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import Usuario


PBKDF2_ITERATIONS = 260_000


def hash_password(password: str, salt: Optional[bytes] = None) -> str:
    """Genera un hash PBKDF2 usando solo libreria estandar de Python."""

    salt = salt or os.urandom(16)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    salt_b64 = base64.b64encode(salt).decode("ascii")
    key_b64 = base64.b64encode(key).decode("ascii")
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt_b64}${key_b64}"


def verify_password(password: str, password_hash: str) -> bool:
    """Verifica una contrasena contra el hash guardado."""

    try:
        algoritmo, iteraciones, salt_b64, key_b64 = password_hash.split("$", 3)
        if algoritmo != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64.encode("ascii"))
        expected = base64.b64decode(key_b64.encode("ascii"))
        candidate = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            int(iteraciones),
        )
        return hmac.compare_digest(candidate, expected)
    except (ValueError, TypeError):
        return False


def authenticate_user(db: Session, usuario_o_correo: str, password: str) -> Optional[Usuario]:
    """Busca el usuario por nombre de usuario o correo y valida su contrasena."""

    identificador = usuario_o_correo.strip().lower()
    usuario = (
        db.query(Usuario)
        .filter(
            or_(
                Usuario.username == identificador,
                Usuario.correo == identificador,
            )
        )
        .first()
    )
    if not usuario or not usuario.activo:
        return None
    if not verify_password(password, usuario.password_hash):
        return None
    return usuario
