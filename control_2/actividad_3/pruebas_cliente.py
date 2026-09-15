# Actividad 3 - Control 2 - CC4303 Redes (Primavera 2026)
# Universidad de Chile - FCFM - Departamento de Ciencias de la Computacion
# Profesora: Ivana Bachmann
# Integrante: Diego Salinas
#
# Pruebas de send/recv/cierre (lado cliente). Se ejecuta junto a pruebas_servidor.py.
# Uso: python3 pruebas_cliente.py IP PUERTO [-debug] [-perdida PORCENTAJE]

import sys

import SocketTCP
from pruebas_servidor import MENSAJE_LARGO

if __name__ == "__main__":
    address = (sys.argv[1], int(sys.argv[2]))
    SocketTCP.MODO_DEBUG = "-debug" in sys.argv
    if "-perdida" in sys.argv:
        SocketTCP.PROBABILIDAD_PERDIDA = int(sys.argv[sys.argv.index("-perdida") + 1])

    client_socketTCP = SocketTCP.SocketTCP()
    client_socketTCP.connect(address)
    # test 1
    client_socketTCP.send("Mensje de len=16".encode())
    # test 2
    client_socketTCP.send("Mensaje de largo 19".encode())
    # test 3
    client_socketTCP.send("Mensaje de largo 19".encode())
    # test 4
    client_socketTCP.send(("a" * 21 + "b" * 21).encode())
    # test 5
    client_socketTCP.send(MENSAJE_LARGO)

    client_socketTCP.close()
    print("Conexion cerrada (close)")
