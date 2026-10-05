from django.db import transaction
from django.utils import timezone
from apps.catalogos.models import PreguntaCausa
from .common import bloquear, campos_permitidos, ciclo_vigente, editable, exigir, gestionar, registrar

CONTROL_CAMPOS = ["tipos", "nombre", "descripcion", "mitiga_riesgo", "frecuencia", "responsable", "evidencia"]


class CausaService:
    @staticmethod
    @transaction.atomic
    def guardar(*, usuario, hallazgo, datos, finalizar=False):
        hallazgo = bloquear(hallazgo)
        gestionar(usuario, hallazgo)
        editable(hallazgo, {"EN_ANALISIS", "PBI_EN_GESTION"})
        campos_permitidos(datos, ["respuestas", "otros_activos", "control", "causa_raiz"])
        ciclo = ciclo_vigente(hallazgo)
        analisis = ciclo
        if analisis.analisis_inicio is None:
            analisis.analisis_inicio = timezone.now()
            analisis.analisis_responsable = usuario
        exigir(analisis.analisis_fin is None, "El análisis finalizado es histórico. Una nueva gestión requiere un nuevo plan.")
        if not analisis.checklist_snapshot:
            preguntas = PreguntaCausa.objects.filter(activo=True, categoria__activo=True).order_by("categoria__orden", "orden")
            analisis.checklist_snapshot = [{
                "id": p.pk, "codigo": p.codigo, "texto": p.texto,
                "es_otro": p.texto.strip().rstrip(":").casefold() == "otro",
            } for p in preguntas]
        snapshot = {str(p["id"]): p for p in analisis.checklist_snapshot}
        exigir(bool(snapshot), "Configure el catálogo de preguntas 6M antes de analizar.")
        analisis.causa_raiz = datos.get("causa_raiz", analisis.causa_raiz).strip()
        recibidos = set()
        almacenadas = {str(item["pregunta_id"]): item for item in analisis.respuestas}
        otros_validos = {
            clave for clave, version in snapshot.items()
            if version.get("es_otro", version["texto"].strip().rstrip(":").casefold() == "otro")
        }
        otros_activos = {str(clave) for clave in datos.get("otros_activos", [])}
        exigir(otros_activos <= otros_validos, "La pregunta adicional no pertenece al cuestionario del plan.")
        for item in datos.get("respuestas", []):
            campos_permitidos(item, ["pregunta", "texto_personalizado", "respuesta", "comentario"])
            pregunta = item.get("pregunta")
            clave = str(getattr(pregunta, "pk", pregunta))
            exigir(clave in snapshot and clave not in recibidos, "La pregunta no pertenece al cuestionario del plan o está duplicada.")
            recibidos.add(clave)
            exigir(item.get("respuesta") in {"SI", "NO", "NA"}, "Cada respuesta debe ser Sí, No o No aplica.")
            version = snapshot[clave]
            es_otro = clave in otros_validos
            texto = version["texto"]
            if es_otro:
                texto = item.get("texto_personalizado", "").strip()
                exigir(bool(texto), "Escriba el punto o pregunta adicional.")
                exigir(len(texto) <= 500, "La pregunta adicional supera 500 caracteres.")
                otros_activos.add(clave)
            almacenadas[clave] = {
                "pregunta_id": version["id"], "codigo_snapshot": version["codigo"], "texto_snapshot": texto,
                "es_otro": es_otro,
                "respuesta": item["respuesta"], "comentario": item.get("comentario", ""),
                "usuario_id": usuario.pk, "fecha": timezone.now().isoformat(),
            }
        for clave in otros_validos - otros_activos:
            almacenadas.pop(clave, None)
        analisis.respuestas = list(almacenadas.values())
        respuestas = {r["codigo_snapshot"]: r["respuesta"] for r in analisis.respuestas}
        control = datos.get("control") or {}
        campos_permitidos(control, CONTROL_CAMPOS)
        if respuestas.get("4.1") == "SI":
            if finalizar or any(control.values()):
                exigir(all(control.get(c) for c in CONTROL_CAMPOS), "La pregunta 4.1 exige completar todos los datos del control del proceso.")
                exigir(isinstance(control["tipos"], list) and set(control["tipos"]) <= {"PREVENTIVO", "DETECTIVO", "CORRECTIVO"}, "Tipo de control no válido.")
                exigir(control["mitiga_riesgo"] in {"SI", "NO", "NA"}, "Indique si el control mitiga el riesgo.")
                for campo, limite in [("nombre", 250), ("frecuencia", 150), ("responsable", 200)]:
                    exigir(len(control[campo]) <= limite, f"El campo {campo} supera {limite} caracteres.")
                analisis.control = control
        else:
            analisis.control = {}
        if finalizar:
            obligatorias = set(snapshot) - otros_validos
            respondidas = {str(item["pregunta_id"]) for item in analisis.respuestas}
            exigir(obligatorias <= respondidas, "Responda todas las preguntas del checklist 6M del plan.")
            analisis.analisis_fin = timezone.now()
        analisis.save()
        registrar(hallazgo, usuario, "FINALIZAR_ANALISIS" if finalizar else "GUARDAR_ANALISIS", metadata={"analisis": analisis.pk, "ciclo": ciclo.numero, "respuestas": len(respuestas)})
        return analisis
