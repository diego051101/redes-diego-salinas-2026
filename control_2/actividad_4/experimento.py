# Actividad 4 - Control 2 - Redes (CC4303), primavera 2026
# Universidad de Chile - FCFM - Departamento de Ciencias de la Computacion
# Profesora: Ivana Bachmann
# Integrante: Diego Salinas
#
# Experimento de la seccion Pruebas: compara Go-Back-N con y sin control de congestion
# midiendo tiempo de transferencia y segmentos enviados, con perdida inducida.
# Uso: python3 experimento.py [repeticiones]

import re
import subprocess
import sys
import time

PERDIDA = 20
TIMEOUT = 0.5
ARCHIVOS = ["archivo_100b.txt", "archivo_1200b.txt"]
MODOS_CC = ["on", "off"]

def una_corrida(archivo, control_congestion, puerto):
    servidor = subprocess.Popen(
        [sys.executable, "-u", "servidor.py", "localhost", str(puerto), "-mode", "go_back_n",
         "-timeout", str(TIMEOUT), "-perdida", str(PERDIDA)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(0.8)
    with open(archivo, "rb") as entrada:
        cliente = subprocess.run(
            [sys.executable, "-u", "cliente.py", "localhost", str(puerto), "-mode", "go_back_n",
             "-cc", control_congestion, "-timeout", str(TIMEOUT), "-perdida", str(PERDIDA)],
            stdin=entrada, capture_output=True, text=True, timeout=900)
    time.sleep(3 * TIMEOUT)
    servidor.terminate()
    recibido, salida_servidor = servidor.communicate(timeout=30)
    medicion = re.search(r"tiempo = ([\d.]+) s, segmentos enviados = (\d+)", cliente.stderr)
    enviados_servidor = re.search(r"resultado segmentos enviados = (\d+)", salida_servidor.decode(errors="replace"))
    contenido_original = open(archivo, "rb").read()
    return {
        "archivo": archivo,
        "control_congestion": control_congestion,
        "tiempo": float(medicion.group(1)),
        "segmentos_cliente": int(medicion.group(2)),
        "segmentos_servidor": int(enviados_servidor.group(1)) if enviados_servidor else 0,
        "integro": recibido == contenido_original,
    }

if __name__ == "__main__":
    repeticiones = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    puerto = 9700
    resultados = []
    for archivo in ARCHIVOS:
        for control_congestion in MODOS_CC:
            for repeticion in range(repeticiones):
                puerto += 1
                fila = una_corrida(archivo, control_congestion, puerto)
                fila["repeticion"] = repeticion + 1
                resultados.append(fila)
                print(fila, flush=True)
    with open("experimento_resultados.csv", "w", encoding="utf-8", newline="\n") as salida:
        salida.write("archivo,control_congestion,repeticion,tiempo,segmentos_cliente,segmentos_servidor,integro\n")
        for fila in resultados:
            salida.write("{archivo},{control_congestion},{repeticion},{tiempo},{segmentos_cliente},"
                         "{segmentos_servidor},{integro}\n".format(**fila))
    print("resultados guardados en experimento_resultados.csv")
