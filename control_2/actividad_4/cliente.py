# Actividad 4 - Control 2 - Redes (CC4303), primavera 2026
# Universidad de Chile - FCFM - Departamento de Ciencias de la Computacion
# Profesora: Ivana Bachmann
# Integrante: Diego Salinas
#
# Cliente: lee un archivo desde entrada estandar y lo envia al servidor usando SocketTCP.
# Uso: python3 cliente.py IP PUERTO [-mode go_back_n|stop_and_wait] [-cc on|off]
#                        [-timeout SEGUNDOS] [-perdida PORCENTAJE] [-debug] < archivo.txt

import sys
import time

import SocketTCP

def leer_opcion(nombre, por_defecto):
    if nombre in sys.argv:
        return sys.argv[sys.argv.index(nombre) + 1]
    return por_defecto

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python3 cliente.py IP PUERTO [-mode M] [-cc on|off] [-timeout S] [-perdida P] [-debug]",
              file=sys.stderr)
        sys.exit(1)
    direccion_servidor = (sys.argv[1], int(sys.argv[2]))
    modo = leer_opcion("-mode", "go_back_n")
    SocketTCP.MODO_DEBUG = "-debug" in sys.argv
    SocketTCP.PROBABILIDAD_PERDIDA = int(leer_opcion("-perdida", 0))
    SocketTCP.TIMEOUT_SEGUNDOS = float(leer_opcion("-timeout", SocketTCP.TIMEOUT_SEGUNDOS))
    # Se carga todo el archivo a memoria como bytes.
    contenido = sys.stdin.buffer.read()
    client_socketTCP = SocketTCP.SocketTCP()
    client_socketTCP.set_congestion_control(leer_opcion("-cc", "on") == "on")
    inicio = time.time()
    client_socketTCP.connect(direccion_servidor)
    print("Conectado a", client_socketTCP.direccion_destino, "- enviando", len(contenido), "bytes en modo", modo,
          "con control de congestion", client_socketTCP.congestion_control_on, file=sys.stderr)
    client_socketTCP.send(contenido, mode=modo)
    duracion = time.time() - inicio
    segmentos = client_socketTCP.number_of_sent_segments
    client_socketTCP.close()
    print("Archivo enviado y conexion cerrada", file=sys.stderr)
    print("resultado tiempo =", round(duracion, 3), "s, segmentos enviados =", segmentos, file=sys.stderr)
