#!/usr/bin/env python3
"""Actualiza checksums y crea el paquete autocontenido del esquema Oracle."""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path


BASE = Path(__file__).resolve().parents[1]
ORIGEN = BASE / "docs" / "oracle_usrfact"
CHECKSUMS = ORIGEN / "SHA256SUMS.txt"
DESTINO = BASE / "docs" / "portal_nc_oracle_usrfact.zip"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as archivo:
        for bloque in iter(lambda: archivo.read(1024 * 1024), b""):
            digest.update(bloque)
    return digest.hexdigest()


def main() -> None:
    archivos = sorted(
        path for path in ORIGEN.iterdir()
        if path.is_file() and path != CHECKSUMS and path.suffix.lower() != ".zip"
    )
    contenido = "".join(f"{sha256(path)}  {path.name}\n" for path in archivos)
    CHECKSUMS.write_text(contenido, encoding="utf-8", newline="\n")

    archivos.append(CHECKSUMS)
    with zipfile.ZipFile(DESTINO, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as paquete:
        for path in sorted(archivos):
            paquete.write(path, Path("oracle_usrfact") / path.name)

    print(f"{DESTINO}\nSHA256={sha256(DESTINO)}\narchivos={len(archivos)}")


if __name__ == "__main__":
    main()
