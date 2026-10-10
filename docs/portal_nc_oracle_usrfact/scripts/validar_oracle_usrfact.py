#!/usr/bin/env python3
"""Valida estáticamente el paquete Oracle USRFACT sin conectarse a Oracle."""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import sqlparse


BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
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

    prevalidacion = textos["00_prevalidacion.sql"]
    ddl = textos["01_crear_tablas.sql"]
    relaciones = textos["02_relaciones_indices.sql"]
    triggers = textos["03_triggers_integridad.sql"]
    datos = textos["04_datos_base.sql"]
    baseline = textos["05_baseline_django.sql"]
    ajustes = textos["06_ajustar_identidades.sql"]
    permisos = textos["07_permisos.sql"]
    permisos_existente = textos["10_otorgar_permisos_usrfacsop.sql"]
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
    exigir(re.search(r"datos\s+NCLOB", prevalidacion, re.I),
           "La prevalidación no prueba el tipo NCLOB usado por JSONField.")
    exigir(re.search(r"CHECK\s*\(datos\s+IS\s+JSON\s*\(STRICT\)\)", prevalidacion, re.I),
           "La prevalidación no prueba NCLOB con IS JSON (STRICT).")
    exigir(re.search(r"USER_SYS_PRIVS.*CREATE TRIGGER", prevalidacion, re.I | re.S),
           "La prevalidación no exige el privilegio directo CREATE TRIGGER.")
    exigir(re.search(
        r"BEFORE\s+INSERT\s+OR\s+UPDATE\s+ON\s+tbl_nc_prevalidacion_nombre_largo_123",
        prevalidacion, re.I,
    ), "La prevalidación no compila y ejecuta el patrón de trigger NCLOB corregido.")
    exigir("ux_nc_prevalidacion_valor_123" in prevalidacion,
           "La prevalidación no prueba el índice condicional del catálogo.")
    exigir("UX_CAT_CLASE_VALOR_NC" in textos["09_validacion_final.sql"].upper(),
           "La validación final no comprueba el índice condicional del catálogo.")

    indices = re.findall(r"CREATE\s+(?:UNIQUE\s+)?INDEX\s+(\w+)", relaciones, re.I)
    exigir(len(indices) == 41, f"Se esperaban 41 índices explícitos y se encontraron {len(indices)}.")
    exigir(not re.search(r"CONSTRAINT\s+uk_cat_clase_valor_nc\b", ddl, re.I),
           "La unicidad condicional del catálogo no puede ser una restricción UNIQUE de Oracle.")
    exigir(re.search(
        r"CREATE\s+UNIQUE\s+INDEX\s+ux_cat_clase_valor_nc\s+ON\s+tbl_catalogo_nc\s*\(\s*"
        r"CASE\s+WHEN\s+valor\s+IS\s+NOT\s+NULL\s+THEN\s+clase\s+END\s*,\s*"
        r"CASE\s+WHEN\s+valor\s+IS\s+NOT\s+NULL\s+THEN\s+valor\s+END\s*\)",
        relaciones, re.I | re.S,
    ), "Falta el índice funcional que permite varios valores NULL por clase.")

    nombres_triggers = re.findall(r"CREATE\s+OR\s+REPLACE\s+TRIGGER\s+(\w+)", triggers, re.I)
    exigir(len(nombres_triggers) == 11,
           f"Se esperaban 11 triggers y se encontraron {len(nombres_triggers)}.")

    columnas_lob = set()
    for tabla, cuerpo in re.findall(r"CREATE\s+TABLE\s+(\w+)\s*\((.*?)\n\);", ddl, re.I | re.S):
        for definicion in separar_definiciones(cuerpo):
            partes = definicion.split(None, 1)
            if len(partes) == 2 and partes[0].upper() != "CONSTRAINT" and re.search(r"\b(?:NCLOB|CLOB|BLOB)\b", partes[1], re.I):
                columnas_lob.add((tabla.upper(), partes[0].strip('"').upper()))
    for columnas, tabla in re.findall(r"UPDATE\s+OF\s+(.*?)\s+ON\s+(\w+)", triggers, re.I | re.S):
        for columna in columnas.split(","):
            par = (tabla.upper(), columna.strip().upper())
            exigir(par not in columnas_lob,
                   f"Oracle 19c no permite UPDATE OF sobre la columna LOB {tabla}.{columna.strip()}.")

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
        r"TO\s+USRFACSOP\s*;",
        permisos, re.I | re.S,
    )
    exigir({g.upper() for g in grants} == ESPERADAS,
           "Los GRANT no cubren exactamente las 24 tablas para USRFACSOP.")

    grants_existente = re.findall(
        r"GRANT\s+SELECT\s*,\s*INSERT\s*,\s*UPDATE\s*,\s*DELETE\s+ON\s+(\w+)\s+"
        r"TO\s+USRFACSOP\s*;",
        permisos_existente, re.I | re.S,
    )
    exigir({g.upper() for g in grants_existente} == ESPERADAS,
           "El script para el esquema existente no cubre las 24 tablas para USRFACSOP.")
    exigir("v_permisos <> 96" in permisos_existente,
           "El script para el esquema existente no valida los 96 permisos DML.")

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

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    from django.db.migrations.loader import MigrationLoader

    django.setup()
    aplicaciones = {"accounts", "auth", "catalogos", "contenttypes", "hallazgos", "sessions"}
    migraciones_codigo = {
        (app, nombre)
        for app, nombre in MigrationLoader(None, ignore_no_migrations=True).disk_migrations
        if app in aplicaciones
    }
    exigir(set(migraciones) == migraciones_codigo,
           "La línea base Django no coincide exactamente con las migraciones del código: "
           f"faltan={sorted(migraciones_codigo-set(migraciones))}, "
           f"sobran={sorted(set(migraciones)-migraciones_codigo)}")

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
        "41 indices, 11 triggers, 22 identidades ajustadas, 29 catalogos, 9 prioridades, "
        "32 preguntas, 56 migraciones base y 96 permisos DML para USRFACSOP."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
