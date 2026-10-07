"""
Actividad 2.2 - Diseno y simulacion de un agente recolector
Materia: Agentes Inteligentes - Unidad II. Agentes y su entorno

Agente de tipo REACTIVO BASADO EN MODELOS:
- Percibe solo la celda actual y las 4 celdas adyacentes (sensores locales).
- Mantiene una MEMORIA INTERNA (modelo del mundo) con todo lo que ha visto
  hasta el momento, para poder dirigirse hacia paquetes conocidos que ya
  no estan en su percepcion inmediata y para explorar celdas no visitadas.
"""

import copy

# ------------------------------------------------------------------
# CONSTANTES DEL ENTORNO
# ------------------------------------------------------------------
LIBRE = "."
PAQUETE = "P"
OBSTACULO = "X"
AGENTE = "A"
FUERA = "FUERA_DEL_TABLERO"

DIRECCIONES = {
    "ARRIBA":    (-1, 0),
    "ABAJO":     (1, 0),
    "IZQUIERDA": (0, -1),
    "DERECHA":   (0, 1),
}
ORDEN_EXPLORACION = ["ARRIBA", "DERECHA", "ABAJO", "IZQUIERDA"]  # barrido en reloj

MAX_ACCIONES = 50


class AgenteRecolector:
    """Implementa el PROGRAMA DEL AGENTE: la funcion que proyecta
    percepciones en acciones (func. agente = PEAS -> accion)."""

    def __init__(self, entorno, posicion_inicial):
        # --- Entorno real (solo lo usan percibir() y actuar(), NUNCA decidir()) ---
        self.entorno = entorno
        self.filas = len(entorno)
        self.columnas = len(entorno[0])
        self.posicion = list(posicion_inicial)

        # --- Medida de rendimiento ---
        self.puntuacion = 0
        self.paquetes_recogidos = 0
        self.movimientos = 0
        self.penalizaciones = 0
        self.historial_eventos = []

        # --- Memoria interna del agente (modelo del mundo) ---
        # Unicamente contiene lo que el agente ha percibido alguna vez.
        self.memoria = {}
        self.visitadas = set()
        self.total_paquetes = sum(row.count(PAQUETE) for row in entorno)

        self.acciones_ejecutadas = 0
        self.terminado = False

    # ----------------------------------------------------------------
    # SENSORES / PERCEPCIONES
    # ----------------------------------------------------------------
    def _contenido_celda(self, fila, col):
        """Sensor atomico: devuelve el contenido real de una celda del
        entorno, o FUERA si la celda esta fuera del tablero."""
        if 0 <= fila < self.filas and 0 <= col < self.columnas:
            return self.entorno[fila][col]
        return FUERA

    def percibir(self):
        """PERCEPCION: obtiene la informacion local disponible para el
        agente en el turno actual: posicion, celda actual y las 4
        celdas vecinas. Esta es la UNICA informacion "fresca" que el
        agente recibe del entorno en cada ciclo."""
        f, c = self.posicion
        percepcion = {
            "posicion": (f, c),
            "actual": self._contenido_celda(f, c),
            "ARRIBA": self._contenido_celda(f - 1, c),
            "ABAJO": self._contenido_celda(f + 1, c),
            "IZQUIERDA": self._contenido_celda(f, c - 1),
            "DERECHA": self._contenido_celda(f, c + 1),
        }
        # Actualiza la memoria/modelo interno con lo recien percibido
        self._actualizar_memoria(percepcion)
        return percepcion

    def _actualizar_memoria(self, percepcion):
        f, c = percepcion["posicion"]
        self.memoria[(f, c)] = percepcion["actual"]
        self.visitadas.add((f, c))
        for d, (df, dc) in DIRECCIONES.items():
            nf, nc = f + df, c + dc
            self.memoria[(nf, nc)] = percepcion[d]

    # ----------------------------------------------------------------
    # DECISION (logica / estrategia del agente)
    # ----------------------------------------------------------------
    def decidir(self, percepcion):
        """DECISION: a partir de la percepcion actual (y la memoria
        acumulada) selecciona UNA accion: RECOGER, ARRIBA, ABAJO,
        IZQUIERDA o DERECHA. Nunca elige deliberadamente una direccion
        que ya sabe que es obstaculo o fuera del tablero: eso hace al
        agente mas racional (evita penalizaciones evitables)."""

        # Regla 1: SI la celda actual contiene un paquete ENTONCES recogerlo.
        if percepcion["actual"] == PAQUETE:
            return "RECOGER"

        # Regla 2: SI existe un paquete en una celda adyacente
        # ENTONCES moverse hacia esa direccion.
        for d in ORDEN_EXPLORACION:
            if percepcion[d] == PAQUETE:
                return d

        # Regla 3: SI la memoria conoce un paquete en otra parte del
        # mapa (visto anteriormente pero fuera de la percepcion actual)
        # ENTONCES avanzar un paso en su direccion (camino mas corto
        # sobre las celdas YA conocidas y transitables).
        paquete_conocido = self._paquete_mas_cercano_conocido()
        if paquete_conocido:
            paso = self._siguiente_paso_hacia(paquete_conocido)
            if paso:
                return paso

        # Regla 4: SI hay una celda vecina libre y NO visitada
        # ENTONCES explorar hacia ella (para descubrir mas del mapa).
        candidatos_no_visitados = [
            d for d in ORDEN_EXPLORACION
            if self._transitable(percepcion[d])
            and self._posicion_destino(d) not in self.visitadas
        ]
        if candidatos_no_visitados:
            return candidatos_no_visitados[0]

        # Regla 5: SI ya no hay celdas nuevas adyacentes (todo
        # explorado o bloqueado alrededor) ENTONCES moverse hacia
        # alguna celda conocida y libre (aunque ya visitada) para
        # continuar recorriendo el tablero en busca de zonas nuevas.
        destino_lejano = self._celda_no_visitada_mas_cercana()
        if destino_lejano:
            paso = self._siguiente_paso_hacia(destino_lejano)
            if paso:
                return paso

        candidatos_libres = [
            d for d in ORDEN_EXPLORACION if self._transitable(percepcion[d])
        ]
        if candidatos_libres:
            return candidatos_libres[0]

        # Si ninguna regla aplica (agente completamente rodeado),
        # se queda sin accion posible: se notifica y se detiene.
        return None

    # -- utilidades de la estrategia (usan SOLO la memoria, no el entorno real) --
    def _transitable(self, contenido):
        return contenido in (LIBRE, PAQUETE)

    def _posicion_destino(self, direccion):
        f, c = self.posicion
        df, dc = DIRECCIONES[direccion]
        return (f + df, c + dc)

    def _paquete_mas_cercano_conocido(self):
        paquetes = [pos for pos, v in self.memoria.items() if v == PAQUETE]
        if not paquetes:
            return None
        f, c = self.posicion
        paquetes.sort(key=lambda p: abs(p[0] - f) + abs(p[1] - c))
        return paquetes[0]

    def _celda_no_visitada_mas_cercana(self):
        libres_no_visitadas = [
            pos for pos, v in self.memoria.items()
            if self._transitable(v) and pos not in self.visitadas
        ]
        if not libres_no_visitadas:
            return None
        f, c = self.posicion
        libres_no_visitadas.sort(key=lambda p: abs(p[0] - f) + abs(p[1] - c))
        return libres_no_visitadas[0]

    def _siguiente_paso_hacia(self, destino):
        """BFS sobre la memoria conocida (no sobre el entorno real) para
        encontrar el primer paso de un camino corto hacia 'destino'."""
        inicio = tuple(self.posicion)
        if inicio == destino:
            return None
        frontera = [inicio]
        padres = {inicio: None}
        while frontera:
            actual = frontera.pop(0)
            if actual == destino:
                break
            for d, (df, dc) in DIRECCIONES.items():
                vecino = (actual[0] + df, actual[1] + dc)
                contenido = self.memoria.get(vecino, None)
                if contenido is not None and self._transitable(contenido) and vecino not in padres:
                    padres[vecino] = (actual, d)
                    frontera.append(vecino)
        if destino not in padres:
            return None
        paso = destino
        primera_direccion = None
        while padres[paso] is not None:
            anterior, direccion = padres[paso]
            if anterior == inicio:
                primera_direccion = direccion
            paso = anterior
        return primera_direccion

    # ----------------------------------------------------------------
    # ACTUADORES / ACCIONES
    # ----------------------------------------------------------------
    def actuar(self, accion):
        """ACTUADORES: ejecuta la accion elegida y MODIFICA el entorno
        o la posicion del agente. Tambien dispara la actualizacion de
        la medida de rendimiento segun lo ocurrido."""
        if accion is None:
            return "sin_accion"

        if accion == "RECOGER":
            f, c = self.posicion
            if self.entorno[f][c] == PAQUETE:
                self.entorno[f][c] = LIBRE
                self.paquetes_recogidos += 1
                self._actualizar_rendimiento("recoger_paquete")
                return "paquete_recogido"
            return "nada_que_recoger"

        # Accion de movimiento
        df, dc = DIRECCIONES[accion]
        nf, nc = self.posicion[0] + df, self.posicion[1] + dc

        if not (0 <= nf < self.filas and 0 <= nc < self.columnas):
            self._actualizar_rendimiento("fuera_del_tablero")
            return "bloqueado_fuera_tablero"

        if self.entorno[nf][nc] == OBSTACULO:
            self._actualizar_rendimiento("obstaculo")
            return "bloqueado_obstaculo"

        # Movimiento valido
        self.posicion = [nf, nc]
        self.movimientos += 1
        self._actualizar_rendimiento("movimiento")
        return "movido"

    # ----------------------------------------------------------------
    # MEDIDA DE RENDIMIENTO
    # ----------------------------------------------------------------
    def _actualizar_rendimiento(self, evento):
        """Traduce un evento del entorno en un cambio de puntuacion,
        de acuerdo con la tabla de la Parte 2 de la actividad."""
        cambios = {
            "recoger_paquete": 10,
            "movimiento": -1,
            "fuera_del_tablero": -5,
            "obstaculo": -5,
        }
        delta = cambios.get(evento, 0)
        self.puntuacion += delta
        if evento in ("fuera_del_tablero", "obstaculo"):
            self.penalizaciones += 1

        if evento == "recoger_paquete" and self.paquetes_recogidos == self.total_paquetes:
            self.puntuacion += 20  # bono por recoger todos los paquetes
            self.historial_eventos.append(("bono_todos_los_paquetes", 20))

        self.historial_eventos.append((evento, delta))

    # ----------------------------------------------------------------
    # CICLO PRINCIPAL DEL AGENTE
    # ----------------------------------------------------------------
    def quedan_paquetes(self):
        return self.paquetes_recogidos < self.total_paquetes

    def mostrar_entorno(self):
        lineas = []
        for f in range(self.filas):
            fila_str = []
            for c in range(self.columnas):
                if [f, c] == self.posicion:
                    fila_str.append(AGENTE)
                else:
                    fila_str.append(self.entorno[f][c])
            lineas.append(" ".join(fila_str))
        return "\n".join(lineas)

    def ejecutar(self, verbose=True, max_acciones=MAX_ACCIONES):
        log = []
        log.append("Estado inicial:")
        log.append(self.mostrar_entorno())
        log.append(f"Posicion: {tuple(self.posicion)} | Puntuacion: {self.puntuacion}")
        log.append("")

        while self.quedan_paquetes() and self.acciones_ejecutadas < max_acciones:
            percepcion = self.percibir()
            accion = self.decidir(percepcion)
            resultado = self.actuar(accion)
            self.acciones_ejecutadas += 1

            log.append(
                f"Accion #{self.acciones_ejecutadas}: {accion} -> {resultado} | "
                f"Posicion: {tuple(self.posicion)} | Puntuacion: {self.puntuacion}"
            )
            log.append(self.mostrar_entorno())
            log.append("")

            if accion is None:
                log.append("El agente no tiene acciones validas disponibles. Simulacion detenida.")
                break

        if not self.quedan_paquetes():
            log.append(f"Todos los paquetes fueron recolectados en {self.acciones_ejecutadas} acciones.")
        elif self.acciones_ejecutadas >= max_acciones:
            log.append(f"Se alcanzo el limite de {max_acciones} acciones sin recolectar todos los paquetes.")

        log.append(
            f"RESULTADO FINAL -> Paquetes: {self.paquetes_recogidos}/{self.total_paquetes} | "
            f"Movimientos: {self.movimientos} | Penalizaciones: {self.penalizaciones} | "
            f"Puntuacion final: {self.puntuacion}"
        )

        if verbose:
            print("\n".join(log))

        return {
            "log": "\n".join(log),
            "paquetes_recogidos": self.paquetes_recogidos,
            "total_paquetes": self.total_paquetes,
            "movimientos": self.movimientos,
            "penalizaciones": self.penalizaciones,
            "puntuacion_final": self.puntuacion,
            "acciones_totales": self.acciones_ejecutadas,
        }


# ------------------------------------------------------------------
# ESCENARIOS DE PRUEBA (Parte 7)
# ------------------------------------------------------------------
ESCENARIO_1 = [
    [".", ".", ".", "P", "."],
    [".", "X", ".", ".", "."],
    ["A", ".", ".", "X", "P"],
    [".", ".", "P", ".", "."],
    [".", "X", ".", ".", "."],
]

ESCENARIO_2 = [
    ["P", ".", "X", ".", "."],
    [".", ".", "X", ".", "P"],
    [".", ".", "A", ".", "."],
    ["X", ".", ".", ".", "."],
    ["P", ".", "X", ".", "."],
]

ESCENARIO_3 = [
    [".", "X", ".", ".", "P"],
    [".", "X", ".", "X", "."],
    [".", ".", "A", ".", "."],
    ["P", "X", ".", "X", "."],
    [".", ".", ".", ".", "P"],
]


def _localizar_agente(mapa):
    for f, fila in enumerate(mapa):
        for c, val in enumerate(fila):
            if val == "A":
                return (f, c)
    return (0, 0)


def _preparar_entorno(mapa):
    entorno = copy.deepcopy(mapa)
    f, c = _localizar_agente(entorno)
    entorno[f][c] = LIBRE  # la posicion del agente se trata como celda libre
    return entorno, (f, c)


def ejecutar_escenario(nombre, mapa, verbose=True):
    entorno, inicio = _preparar_entorno(mapa)
    agente = AgenteRecolector(entorno, inicio)
    if verbose:
        print("=" * 60)
        print(nombre)
        print("=" * 60)
    resultado = agente.ejecutar(verbose=verbose)
    return resultado


if __name__ == "__main__":
    resultados = {}
    resultados["Escenario 1"] = ejecutar_escenario("ESCENARIO 1", ESCENARIO_1)
    resultados["Escenario 2"] = ejecutar_escenario("ESCENARIO 2", ESCENARIO_2)
    resultados["Escenario 3"] = ejecutar_escenario("ESCENARIO 3", ESCENARIO_3)

    print("\n" + "=" * 60)
    print("TABLA COMPARATIVA DE RESULTADOS")
    print("=" * 60)
    print(f"{'Escenario':<12}{'Paquetes':<12}{'Movimientos':<14}{'Penalizaciones':<16}{'Puntuacion'}")
    for nombre, r in resultados.items():
        print(
            f"{nombre:<12}{str(r['paquetes_recogidos']) + '/' + str(r['total_paquetes']):<12}"
            f"{r['movimientos']:<14}{r['penalizaciones']:<16}{r['puntuacion_final']}"
        )
