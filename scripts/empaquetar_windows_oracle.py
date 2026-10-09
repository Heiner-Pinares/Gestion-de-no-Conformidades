#!/usr/bin/env python3
"""Crea una entrega del código para Windows sin secretos ni archivos locales."""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path


BASE = Path(__file__).resolve().parents[1]
DESTINO = BASE / "docs" / "portal_nc_windows_oracle.zip"
EXCLUIR_DIRECTORIOS = {
    ".git", ".venv", ".runtime", ".cache", "__pycache__", "media", "staticfiles",
}
EXCLUIR_ARCHIVOS = {".env", ".env.local", ".DS_Store"}


def incluir(path: Path) -> bool:
    relativos = path.relative_to(BASE).parts
    if any(parte in EXCLUIR_DIRECTORIOS for parte in relativos):
        return False
    if path.name in EXCLUIR_ARCHIVOS or path.suffix in {".pyc", ".pyo"}:
        return False
    if path == DESTINO or path.suffix.lower() == ".zip":
        return False
    return True


def main() -> None:
    archivos = sorted(path for path in BASE.rglob("*") if path.is_file() and incluir(path))
    with zipfile.ZipFile(DESTINO, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as paquete:
        for path in archivos:
            paquete.write(path, Path("portal_nc") / path.relative_to(BASE))
    digest = hashlib.sha256(DESTINO.read_bytes()).hexdigest()
    print(f"{DESTINO}\nSHA256={digest}\narchivos={len(archivos)}")


if __name__ == "__main__":
    main()
