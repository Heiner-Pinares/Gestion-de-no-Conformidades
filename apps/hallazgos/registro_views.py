"""Registro completo con el mismo alcance de acceso que los expedientes."""
import csv
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render
from .forms import BuscarHallazgoForm
from .registro import COLUMNAS_REGISTRO, RegistroGeneral
from .selectors import hallazgos_visibles


def texto_csv(valor):
    texto = "" if valor is None else str(valor)
    return "'" + texto if texto.lstrip().startswith(("=", "+", "-", "@")) or texto.startswith(("\t", "\r")) else texto


@login_required
def registro_general(request):
    form = BuscarHallazgoForm(request.GET or None)
    hallazgos = hallazgos_visibles(request.user)
    if request.GET and form.is_valid():
        datos = form.cleaned_data
        if datos.get("codigo"):
            hallazgos = hallazgos.filter(Q(codigo__icontains=datos["codigo"]) | Q(titulo__icontains=datos["codigo"]))
        for campo in ("estado", "tipo_registro", "proceso"):
            if datos.get(campo):
                hallazgos = hallazgos.filter(**{campo: datos[campo]})
        if datos.get("fecha_desde"):
            hallazgos = hallazgos.filter(fecha_registro__date__gte=datos["fecha_desde"])
        if datos.get("fecha_hasta"):
            hallazgos = hallazgos.filter(fecha_registro__date__lte=datos["fecha_hasta"])
    elif request.GET:
        hallazgos = hallazgos.none()
    filas = RegistroGeneral.objects.filter(hallazgo_id__in=hallazgos.values("pk"))
    if request.GET.get("formato") == "csv":
        respuesta = HttpResponse(content_type="text/csv; charset=utf-8")
        respuesta["Content-Disposition"] = 'attachment; filename="registro_general.csv"'
        respuesta.write("\ufeff")
        writer = csv.writer(respuesta)
        writer.writerow([titulo for _, titulo in COLUMNAS_REGISTRO])
        for fila in filas.iterator(chunk_size=500):
            writer.writerow([texto_csv(valor) for valor in fila.valores])
        return respuesta
    filtros = request.GET.copy()
    filtros.pop("page", None)
    filtros.pop("formato", None)
    exportacion = filtros.copy()
    exportacion["formato"] = "csv"
    return render(request, "hallazgos/registro_general.html", {
        "form": form, "columnas": [titulo for _, titulo in COLUMNAS_REGISTRO],
        "pagina": Paginator(filas, 25).get_page(request.GET.get("page")),
        "filtros": filtros.urlencode(), "exportacion": exportacion.urlencode(),
    })
