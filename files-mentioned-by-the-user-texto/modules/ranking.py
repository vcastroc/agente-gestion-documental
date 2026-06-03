def asignar_estado(compatibilidad, umbral_preseleccion=80, umbral_observacion=60):
    if compatibilidad >= umbral_preseleccion:
        return "Preseleccionado"
    if compatibilidad >= umbral_observacion:
        return "En observación"
    return "No recomendado"


def generar_ranking(resultados):
    return sorted(resultados, key=lambda item: item["compatibilidad"], reverse=True)


def seleccionar_top(ranking, top=3):
    return ranking[:top]
