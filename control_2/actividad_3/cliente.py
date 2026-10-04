# Actividad 3 - Control 2 - Redes (CC4303), primavera 2026
# Universidad de Chile - FCFM - Departamento de Ciencias de la Computacion
# Profesora: Ivana Bachmann
# Integrante: Diego Salinas
#
# Cliente: lee un archivo desde entrada estándar y lo envía al servidor usando SocketTCP.
# Uso: python3 cliente.py IP PUERTO [-debug] [-perdida PORCENTAJE] < archivo.txt

import sys

import SocketTCP

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python3 cliente.py IP PUERTO [-debug] [-perdida PORCENTAJE] < archivo.txt", file=sys.stderr)
        sys.exit(1)
    direccion_servidor = (sys.argv[1], int(sys.argv[2]))
    SocketTCP.MODO_DEBUG = "-debug" in sys.argv
    if "-perdida" in sys.argv:
        SocketTCP.PROBABILIDAD_PERDIDA = int(sys.argv[sys.argv.index("-perdida") + 1])
    # Se carga todo el archivo a memoria como bytes.
    contenido = sys.stdin.buffer.read()
    client_socketTCP = SocketTCP.SocketTCP()
    client_socketTCP.connect(direccion_servidor)
    print("Conectado a", client_socketTCP.direccion_destino, "- enviando", len(contenido), "bytes", file=sys.stderr)
    client_socketTCP.send(contenido)
    client_socketTCP.close()
    print("Archivo enviado y conexion cerrada", file=sys.stderr)
