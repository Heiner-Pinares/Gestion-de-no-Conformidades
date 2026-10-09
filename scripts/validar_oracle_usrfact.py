#!/usr/bin/env python3
"""Valida estáticamente el paquete Oracle USRFACT sin conectarse a Oracle."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import sqlparse


BASE = Path(__file__).resolve().parents[1]
CARPETA = BASE / "docs" / "oracle_usrfact"
MANIFEST = json.loads((CARPETA / "manifest_esquema.json").read_text(encoding="utf-8"))
ESPERADAS = {nombre.upper() for nombre in MANIFEST["tables"]}


def exigir(condicion: bool, mensaje: str) -> None:
    if not condicion:
        raise AssertionError(mensaje)


def separar_definiciones(cuerpo: str) -> list[str]:
    """Separa elementos de CREATE TABLE respetando paréntesis y literales."""
    resultado, actual = [], []
    profundidad = 0
    comilla = False
    i = 0
    while i < len(cuerpo):
        caracter = cuerpo[i]
        actual.append(caracter)
        if caracter == "'":
            if comilla and i + 1 < len(cuerpo) and cuerpo[i + 1] == "'":
                actual.append(cuerpo[i + 1])
                i += 1
            else:
                comilla = not comilla
        elif not comilla:
            if caracter == "(":
                profundidad += 1
            elif caracter == ")":
                profundidad -= 1
            elif caracter == "," and profundidad == 0:
                actual.pop()
                resultado.append("".join(actual).strip())
                actual = []
        i += 1
    if "".join(actual).strip():
        resultado.append("".join(actual).strip())
    return resultado


def tablas_y_columnas(sql: str) -> dict[str, set[str]]:
    tablas = {}
    patron = re.compile(r"CREATE\s+TABLE\s+(\w+)\s*\((.*?)\n\);", re.I | re.S)
    for nombre, cuerpo in patron.findall(sql):
        columnas = set()
        for definicion in separar_definiciones(cuerpo):
            primer_token = definicion.split(None, 1)[0].upper()
            if primer_token != "CONSTRAINT":
                columnas.add(primer_token.strip('"'))
        tablas[nombre.upper()] = columnas
    return tablas


def main() -> int:
    archivos_sql = sorted(CARPETA.glob("*.sql"))
    exigir(archivos_sql, "No se encontraron scripts SQL.")
    textos = {p.name: p.read_text(encoding="utf-8") for p in archivos_sql}

    ddl = textos["01_crear_tablas.sql"]
    relaciones = textos["02_relaciones_indices.sql"]
    triggers = textos["03_triggers_integridad.sql"]
    datos = textos["04_datos_base.sql"]
    baseline = textos["05_baseline_django.sql"]
    ajustes = textos["06_ajustar_identidades.sql"]
    permisos = textos["07_permisos.sql"]
    maestro = textos["INSTALAR_USRFACT.sql"]
    todo_en_uno = textos["INSTALAR_USRFACT_TODO_EN_UNO.sql"]

    tablas = tablas_y_columnas(ddl)
    exigir(set(tablas) == ESPERADAS,
           f"Inventario de tablas distinto: faltan={ESPERADAS-set(tablas)}, sobran={set(tablas)-ESPERADAS}")

    for nombre, esperado in MANIFEST["tables"].items():
        columnas_esperadas = {c.upper() for c in esperado["columns"]}
        columnas_ddl = tablas[nombre.upper()]
        exigir(columnas_ddl == columnas_esperadas,
               f"Columnas distintas en {nombre}: faltan={columnas_esperadas-columnas_ddl}, sobran={columnas_ddl-columnas_esperadas}")

    fks = re.findall(
        r"ALTER\s+TABLE\s+(\w+)\s+ADD\s+CONSTRAINT\s+(\w+)\s+"
        r"FOREIGN\s+KEY\s*\((\w+)\)\s+REFERENCES\s+(\w+)\s*\((\w+)\)",
        relaciones, re.I | re.S,
    )
    exigir(len(fks) == MANIFEST["foreign_key_count"] == 44,
           f"Se esperaban 44 FK y se encontraron {len(fks)}.")
    for tabla, _, columna, destino, columna_destino in fks:
        exigir(tabla.upper() in tablas, f"FK sobre tabla inexistente: {tabla}")
        exigir(destino.upper() in tablas, f"FK apunta a tabla inexistente: {destino}")
        exigir(columna.upper() in tablas[tabla.upper()], f"FK usa columna inexistente: {tabla}.{columna}")
        exigir(columna_destino.upper() in tablas[destino.upper()],
               f"FK apunta a columna inexistente: {destino}.{columna_destino}")

    identidades = len(re.findall(r"GENERATED\s+BY\s+DEFAULT\s+ON\s+NULL\s+AS\s+IDENTITY", ddl, re.I))
    exigir(identidades == 22, f"Se esperaban 22 identidades y se encontraron {identidades}.")

    identidades_ajustadas = re.findall(
        r"ALTER\s+TABLE\s+(\w+)\s+MODIFY\s+id\s+GENERATED\s+BY\s+DEFAULT\s+ON\s+NULL\s+AS\s+IDENTITY\s*"
        r"\(START\s+WITH\s+LIMIT\s+VALUE\s+INCREMENT\s+BY\s+1\s+CACHE\s+100\)\s*;",
        ajustes, re.I | re.S,
    )
    tablas_con_identidad = {
        tabla for tabla, columnas in tablas.items() if "ID" in columnas and
        re.search(rf"CREATE\s+TABLE\s+{tabla}\s*\(.*?\bid\s+NUMBER\(19\)\s+GENERATED", ddl, re.I | re.S)
    }
    exigir(len(identidades_ajustadas) == 22, f"Se esperaban 22 ajustes de identidad y hay {len(identidades_ajustadas)}.")
    exigir({t.upper() for t in identidades_ajustadas} == tablas_con_identidad,
           "Los ajustes no cubren exactamente todas las tablas con identidad.")

    exigir(not re.search(r"TIMESTAMP\(6\)\s+WITH\s+TIME\s+ZONE", ddl, re.I),
           "DateTimeField debe usar TIMESTAMP(6) para coincidir con Django Oracle.")
    exigir(not re.search(r"\bVARCHAR2\(\d+\s+CHAR\)", ddl, re.I),
           "CharField debe usar NVARCHAR2 sin semántica CHAR explícita.")
    exigir(not re.search(r"(?<!N)CLOB", ddl, re.I),
           "TextField/JSONField debe usar NCLOB para coincidir con Django Oracle.")

    indices = re.findall(r"CREATE\s+(?:UNIQUE\s+)?INDEX\s+(\w+)", relaciones, re.I)
    exigir(len(indices) == 40, f"Se esperaban 40 índices explícitos y se encontraron {len(indices)}.")

    nombres_triggers = re.findall(r"CREATE\s+OR\s+REPLACE\s+TRIGGER\s+(\w+)", triggers, re.I)
    exigir(len(nombres_triggers) == 11,
           f"Se esperaban 11 triggers y se encontraron {len(nombres_triggers)}.")

    nombres_constraints = re.findall(r"\bCONSTRAINT\s+(\w+)", ddl + "\n" + relaciones, re.I)
    objetos = [n.upper() for n in nombres_constraints + indices + nombres_triggers]
    exigir(len(objetos) == len(set(objetos)), "Hay nombres de objetos duplicados en el esquema Oracle.")
    largos = [n for n in [*tablas, *objetos] if len(n.encode("utf-8")) > 128]
    exigir(not largos, f"Identificadores mayores de 128 bytes: {largos}")

    prohibidos = re.compile(r"\b(JSONB|BYTEA|BOOLEAN|BIGSERIAL|TIMESTAMPTZ)\b|::", re.I)
    for nombre, texto in textos.items():
        exigir(not prohibidos.search(texto), f"Sintaxis PostgreSQL encontrada en {nombre}.")

    grants = re.findall(
        r"GRANT\s+SELECT\s*,\s*INSERT\s*,\s*UPDATE\s*,\s*DELETE\s+ON\s+(\w+)\s+"
        r"TO\s+C27826\s*,\s*C28111\s*,\s*C28134\s*;",
        permisos, re.I | re.S,
    )
    exigir({g.upper() for g in grants} == ESPERADAS,
           "Los GRANT no cubren exactamente las 24 tablas y los tres usuarios.")

    exigir(len(re.findall(r"INSERT\s+INTO\s+tbl_catalogo_nc\b", datos, re.I)) == 29,
           "La carga base no contiene 29 catálogos.")
    exigir(len(re.findall(r"INSERT\s+INTO\s+tbl_matriz_prioridad_nc\b", datos, re.I)) == 9,
           "La carga base no contiene 9 combinaciones de prioridad.")
    exigir(len(re.findall(r"INSERT\s+INTO\s+tbl_pregunta_causa_nc\b", datos, re.I)) == 32,
           "La carga base no contiene 32 preguntas 6M.")

    migraciones = re.findall(
        r"INSERT\s+INTO\s+tbl_django_migrations_nc\s*\(app,\s*name,\s*applied\)\s*"
        r"VALUES\s*\('([^']+)',\s*'([^']+)',\s*LOCALTIMESTAMP\)\s*;",
        baseline, re.I | re.S,
    )
    exigir(len(migraciones) == 56, f"La línea base debe contener 56 migraciones y contiene {len(migraciones)}.")
    exigir(len(migraciones) == len(set(migraciones)), "Hay migraciones duplicadas en la línea base Django.")

    llamados = re.findall(r"@@([^\s]+\.sql)", maestro, re.I)
    exigir(llamados == [
        "00_prevalidacion.sql", "01_crear_tablas.sql", "02_relaciones_indices.sql",
        "03_triggers_integridad.sql", "04_datos_base.sql", "05_baseline_django.sql",
        "06_ajustar_identidades.sql", "07_permisos.sql", "08_prueba_humo.sql",
        "09_validacion_final.sql",
    ], f"Orden de instalación incorrecto: {llamados}")

    exigir(not re.search(r"^\s*@@?", todo_en_uno, re.M),
           "El instalador todo en uno no puede depender de otros archivos SQL.")
    for nombre in [
        "00_prevalidacion.sql", "01_crear_tablas.sql", "02_relaciones_indices.sql",
        "03_triggers_integridad.sql", "04_datos_base.sql", "05_baseline_django.sql",
        "06_ajustar_identidades.sql", "07_permisos.sql", "08_prueba_humo.sql",
        "09_validacion_final.sql",
    ]:
        exigir(textos[nombre].rstrip() in todo_en_uno,
               f"El instalador todo en uno no contiene íntegramente {nombre}.")
    exigir(len(re.findall(r"^EXIT\s+SUCCESS\s*$", todo_en_uno, re.I | re.M)) == 1,
           "El instalador todo en uno debe terminar con un único EXIT SUCCESS.")

    # sqlparse no valida la gramática Oracle, pero sí detecta archivos vacíos y
    # permite revisar que todo el paquete pueda tokenizarse sin pérdida.
    for nombre, texto in textos.items():
        exigir(sqlparse.parse(texto), f"No fue posible tokenizar {nombre}.")

    print(
        "OK ESTATICO: 24 tablas, 229 columnas, 44 FK, 22 identidades, "
        "40 indices, 11 triggers, 22 identidades ajustadas, 29 catalogos, 9 prioridades, "
        "32 preguntas, 56 migraciones base y permisos para 3 usuarios."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
