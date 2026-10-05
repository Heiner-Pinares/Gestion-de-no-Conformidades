import re
import unicodedata
import zipfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import Usuario


NAMESPACE = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
COLUMNAS = {
    "Cod. Comunicación": "codigo",
    "Correo electrónico": "email",
    "Jefe": "jefe",
    "Nombre completo": "nombre",
    "Área": "area",
    "Gerencia": "gerencia",
    "Dirección": "direccion",
}


def _normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = texto.encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "", texto)


def _titulo(texto):
    return " ".join(parte.capitalize() for parte in (texto or "").strip().split())


def _indice_columna(referencia):
    letras = re.match(r"[A-Z]+", referencia or "")
    resultado = 0
    for letra in letras.group(0) if letras else "":
        resultado = resultado * 26 + ord(letra) - 64
    return resultado - 1


def _texto_compartido(elemento):
    return "".join(elemento.itertext()).strip()


def leer_xlsx(ruta):
    """Lee valores de la primera hoja XLSX sin incorporar otra dependencia."""
    try:
        archivo = zipfile.ZipFile(ruta)
    except (FileNotFoundError, zipfile.BadZipFile) as exc:
        raise CommandError(f"No se pudo abrir el archivo XLSX: {ruta}") from exc
    with archivo:
        compartidos = []
        if "xl/sharedStrings.xml" in archivo.namelist():
            raiz = ElementTree.fromstring(archivo.read("xl/sharedStrings.xml"))
            compartidos = [_texto_compartido(item) for item in raiz.findall(f"{NAMESPACE}si")]
        hojas = sorted(
            nombre for nombre in archivo.namelist()
            if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", nombre)
        )
        if not hojas:
            raise CommandError("El XLSX no contiene hojas legibles.")
        raiz = ElementTree.fromstring(archivo.read(hojas[0]))
        for fila in raiz.findall(f".//{NAMESPACE}sheetData/{NAMESPACE}row"):
            valores = {}
            for celda in fila.findall(f"{NAMESPACE}c"):
                indice = _indice_columna(celda.attrib.get("r", ""))
                tipo = celda.attrib.get("t")
                if tipo == "inlineStr":
                    nodo = celda.find(f"{NAMESPACE}is")
                    valor = _texto_compartido(nodo) if nodo is not None else ""
                else:
                    nodo = celda.find(f"{NAMESPACE}v")
                    valor = nodo.text if nodo is not None and nodo.text is not None else ""
                    if tipo == "s" and valor:
                        valor = compartidos[int(valor)]
                valores[indice] = str(valor).strip()
            if valores:
                yield [valores.get(i, "") for i in range(max(valores) + 1)]


def preparar_filas(ruta):
    filas = iter(leer_xlsx(ruta))
    try:
        cabecera_original = next(filas)
    except StopIteration as exc:
        raise CommandError("El XLSX está vacío.") from exc
    cabecera = [str(valor).strip() for valor in cabecera_original]
    indices = {}
    for etiqueta, clave in COLUMNAS.items():
        try:
            indices[clave] = cabecera.index(etiqueta)
        except ValueError as exc:
            raise CommandError(f"Falta la columna requerida: {etiqueta}") from exc
    resultado = []
    for numero, fila in enumerate(filas, start=2):
        datos = {
            clave: (fila[indice].strip() if indice < len(fila) else "")
            for clave, indice in indices.items()
        }
        if not any(datos.values()):
            continue
        faltantes = [clave for clave in ("codigo", "email", "nombre", "area") if not datos[clave]]
        if faltantes:
            raise CommandError(f"Fila {numero}: faltan {', '.join(faltantes)}.")
        datos["fila"] = numero
        resultado.append(datos)
    if not resultado:
        raise CommandError("No se encontraron usuarios para importar.")
    duplicados_codigo = [v for v, n in Counter(f["codigo"].casefold() for f in resultado).items() if n > 1]
    duplicados_email = [v for v, n in Counter(f["email"].casefold() for f in resultado).items() if n > 1]
    if duplicados_codigo or duplicados_email:
        raise CommandError("El archivo contiene códigos o correos duplicados.")
    return resultado


def dividir_nombre(nombre, email):
    partes = nombre.strip().split()
    if len(partes) < 3:
        raise CommandError(f"No se pudo separar nombres y apellidos: {nombre}")
    local = _normalizar(email.split("@", 1)[0])
    candidatos = []
    # El primer apellido debe dejar al menos un apellido posterior. El correo
    # ayuda a reconocer apellidos compuestos como De la Cruz o La Jara.
    for inicio in range(1, len(partes) - 1):
        for fin in range(inicio + 1, len(partes)):
            candidato = _normalizar("".join(partes[inicio:fin]))
            if len(candidato) >= 3 and candidato in local:
                candidatos.append((len(candidato), inicio, fin))
    if candidatos:
        _, inicio_apellido, fin_apellido = max(candidatos)
    else:
        inicio_apellido, fin_apellido = len(partes) - 2, len(partes) - 1
    nombres = _titulo(" ".join(partes[:inicio_apellido]))
    apellidos = _titulo(" ".join(partes[inicio_apellido:]))
    primer_nombre = _normalizar(partes[0])
    primer_apellido = _normalizar("".join(partes[inicio_apellido:fin_apellido]))
    return nombres, apellidos, f"{primer_nombre}.{primer_apellido}"


class Command(BaseCommand):
    help = "Importa las cuentas de Operaciones Comerciales desde un archivo XLSX."

    def add_arguments(self, parser):
        parser.add_argument("archivo", type=Path)
        parser.add_argument("--dry-run", action="store_true", help="Valida sin guardar cambios.")
        parser.add_argument(
            "--restablecer-claves", action="store_true",
            help="Vuelve a establecer el código de comunicación como clave de cuentas existentes.",
        )

    def handle(self, *args, **options):
        filas = preparar_filas(options["archivo"])
        nombres_jefes = {_normalizar(fila["jefe"]) for fila in filas if fila["jefe"]}
        perfiles = []
        for fila in filas:
            nombres, apellidos, base = dividir_nombre(fila["nombre"], fila["email"])
            perfiles.append({**fila, "nombres": nombres, "apellidos": apellidos, "base": base})

        if options["dry_run"]:
            bases = Counter(perfil["base"] for perfil in perfiles)
            self.stdout.write(self.style.SUCCESS(
                f"Validación correcta: {len(perfiles)} usuarios, "
                f"{len(nombres_jefes)} jefes y {sum(n - 1 for n in bases.values() if n > 1)} acceso duplicado resuelto con sufijo."
            ))
            return

        with transaction.atomic():
            usuarios_por_nombre = {}
            reservados = set(Usuario.objects.values_list("username", flat=True))
            creados = actualizados = claves = 0
            for perfil in perfiles:
                usuario = Usuario.objects.filter(email__iexact=perfil["email"]).first()
                creado = usuario is None
                if creado:
                    base = perfil["base"][:145]
                    username = base
                    numero = 2
                    while username in reservados:
                        sufijo = f".{numero}"
                        username = f"{base[:150-len(sufijo)]}{sufijo}"
                        numero += 1
                    reservados.add(username)
                    usuario = Usuario(username=username, roles=["USUARIO"], is_active=True)
                    usuario.set_password(perfil["codigo"])
                    claves += 1
                elif options["restablecer_claves"]:
                    usuario.set_password(perfil["codigo"])
                    claves += 1
                if not usuario.roles:
                    usuario.roles = ["USUARIO"]
                usuario.first_name = perfil["nombres"][:150]
                usuario.last_name = perfil["apellidos"][:150]
                usuario.email = perfil["email"].lower()[:254]
                usuario.area = perfil["area"][:150]
                usuario.gerencia = perfil["gerencia"][:150]
                usuario.direccion = perfil["direccion"][:150]
                if _normalizar(perfil["nombre"]) in nombres_jefes:
                    usuario.cargo = "Jefe"
                usuario.is_active = True
                usuario.save()
                usuarios_por_nombre[_normalizar(perfil["nombre"])] = usuario
                creados += creado
                actualizados += not creado

            vinculados = 0
            for perfil in perfiles:
                usuario = usuarios_por_nombre[_normalizar(perfil["nombre"])]
                jefe = usuarios_por_nombre.get(_normalizar(perfil["jefe"])) if perfil["jefe"] else None
                if usuario.jefe_id != (jefe.pk if jefe else None):
                    usuario.jefe = jefe
                    usuario.save(update_fields=["jefe"])
                vinculados += jefe is not None

        self.stdout.write(self.style.SUCCESS(
            f"Importación completada: {creados} creados, {actualizados} actualizados, "
            f"{claves} claves establecidas y {vinculados} relaciones de jefatura."
        ))
