import json

from django.db import migrations


VALORES_PREDETERMINADOS = {
    "clientes_bajo_desde": 0,
    "clientes_bajo_hasta": 99,
    "clientes_medio_desde": 100,
    "clientes_medio_hasta": 499,
    "clientes_alto_desde": 500,
    "tiempo_bajo_desde": 0,
    "tiempo_bajo_hasta": 29,
    "tiempo_medio_desde": 30,
    "tiempo_medio_hasta": 120,
    "tiempo_alto_desde": 121,
    "financiero_medio_desde": 1000000,
    "financiero_alto_desde": 2000000,
}


def _entero(configuracion, campo):
    return int(configuracion.get(campo, VALORES_PREDETERMINADOS[campo]))


def _numero(valor):
    return f"{int(valor):,}"


def _json(valor):
    if isinstance(valor, str):
        return json.loads(valor or "{}")
    return valor or {}


def _rangos(configuracion):
    cb_d = _entero(configuracion, "clientes_bajo_desde")
    cb_h = _entero(configuracion, "clientes_bajo_hasta")
    cm_d = _entero(configuracion, "clientes_medio_desde")
    cm_h = _entero(configuracion, "clientes_medio_hasta")
    ca_d = _entero(configuracion, "clientes_alto_desde")
    tb_d = _entero(configuracion, "tiempo_bajo_desde")
    tb_h = _entero(configuracion, "tiempo_bajo_hasta")
    tm_d = _entero(configuracion, "tiempo_medio_desde")
    tm_h = _entero(configuracion, "tiempo_medio_hasta")
    ta_d = _entero(configuracion, "tiempo_alto_desde")
    fm_d = _entero(configuracion, "financiero_medio_desde")
    fa_d = _entero(configuracion, "financiero_alto_desde")
    return {
        "clientes": {
            1: f"{_numero(cb_d)} – {_numero(cb_h)} cuentas",
            2: f"{_numero(cm_d)} – {_numero(cm_h)} cuentas",
            3: f"{_numero(ca_d)} o más cuentas",
        },
        "tiempo": {
            1: f"{_numero(tb_d)} – {_numero(tb_h)} min",
            2: f"{_numero(tm_d)} – {_numero(tm_h)} min",
            3: f"{_numero(ta_d)} o más min",
        },
        "financiero": {
            1: f"Menos de S/ {_numero(fm_d)}",
            2: f"S/ {_numero(fm_d)} a menos de S/ {_numero(fa_d)}",
            3: f"S/ {_numero(fa_d)} o más",
        },
    }


def reconstruir_snapshots(apps, schema_editor):
    """Usa la auditoría administrativa para respetar el rango vigente en cada fecha."""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT fecha, antes, despues
              FROM evento
             WHERE registro_tipo = 'AUDITORIA_ADMINISTRACION'
               AND entidad = 'ConfiguracionImpacto'
               AND accion = 'actualizar'
             ORDER BY fecha, id
            """
        )
        auditorias = cursor.fetchall()

        if auditorias:
            configuracion_inicial = _json(auditorias[0][1]) or VALORES_PREDETERMINADOS
            cambios = [(fecha, _json(despues)) for fecha, _antes, despues in auditorias]
        else:
            cursor.execute(
                """
                SELECT clientes_bajo_desde, clientes_bajo_hasta,
                       clientes_medio_desde, clientes_medio_hasta, clientes_alto_desde,
                       tiempo_bajo_desde, tiempo_bajo_hasta,
                       tiempo_medio_desde, tiempo_medio_hasta, tiempo_alto_desde,
                       financiero_medio_desde, financiero_alto_desde
                  FROM configuracion
                 WHERE registro_tipo = 'CONFIGURACION_IMPACTO'
                 ORDER BY id
                 LIMIT 1
                """
            )
            fila = cursor.fetchone()
            configuracion_inicial = dict(VALORES_PREDETERMINADOS)
            if fila:
                configuracion_inicial.update(dict(zip(VALORES_PREDETERMINADOS, fila)))
            cambios = []

        cursor.execute(
            """
            SELECT id, fecha_registro, aplica_impacto,
                   impacto_clientes, impacto_tiempo, impacto_soles
              FROM registro_general
             ORDER BY fecha_registro, id
            """
        )
        actualizaciones = []
        for hallazgo_id, fecha_registro, aplica, clientes, tiempo, financiero in cursor.fetchall():
            configuracion = dict(configuracion_inicial)
            for fecha_cambio, despues in cambios:
                if fecha_cambio > fecha_registro:
                    break
                configuracion.update(despues)
            rangos = _rangos(configuracion)
            if aplica:
                seleccion_clientes = rangos["clientes"].get(clientes, "")
                seleccion_tiempo = rangos["tiempo"].get(tiempo, "")
                seleccion_financiero = rangos["financiero"].get(financiero, "")
            else:
                seleccion_clientes = seleccion_tiempo = seleccion_financiero = ""
            actualizaciones.append((seleccion_clientes, seleccion_tiempo, seleccion_financiero, hallazgo_id))

        cursor.executemany(
            """
            UPDATE registro_general
               SET impacto_clientes_seleccion = %s,
                   impacto_tiempo_seleccion = %s,
                   impacto_financiero_seleccion = %s
             WHERE id = %s
            """,
            actualizaciones,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("hallazgos", "0018_snapshot_rangos_impacto"),
    ]

    operations = [
        migrations.RunPython(reconstruir_snapshots, migrations.RunPython.noop),
    ]
