# Actividad 4 - Control 2 - Redes (CC4303), primavera 2026
# Universidad de Chile - FCFM - Departamento de Ciencias de la Computacion
# Profesora: Ivana Bachmann
# Integrante: Diego Salinas
#
# Pruebas de send/recv/cierre (stop & wait y go back n) (lado cliente). Se ejecuta junto a pruebas_servidor.py.
# Uso: python3 pruebas_cliente.py IP PUERTO [-mode M] [-cc on|off] [-debug] [-perdida P]

import sys

import SocketTCP

def leer_opcion(nombre, por_defecto):
    if nombre in sys.argv:
        return sys.argv[sys.argv.index(nombre) + 1]
    return por_defecto
from pruebas_servidor import MENSAJE_LARGO

if __name__ == "__main__":
    address = (sys.argv[1], int(sys.argv[2]))
    modo = leer_opcion("-mode", "go_back_n")
    SocketTCP.MODO_DEBUG = "-debug" in sys.argv
    SocketTCP.PROBABILIDAD_PERDIDA = int(leer_opcion("-perdida", 0))
    SocketTCP.TIMEOUT_SEGUNDOS = float(leer_opcion("-timeout", SocketTCP.TIMEOUT_SEGUNDOS))

    client_socketTCP = SocketTCP.SocketTCP()
    client_socketTCP.set_congestion_control(leer_opcion("-cc", "on") == "on")
    client_socketTCP.connect(address)
    # test 1
    client_socketTCP.send("Mensje de len=16".encode(), mode=modo)
    # test 2
    client_socketTCP.send("Mensaje de largo 19".encode(), mode=modo)
    # test 3
    client_socketTCP.send("Mensaje de largo 19".encode(), mode=modo)
    # test 4
    client_socketTCP.send(("a" * 21 + "b" * 21).encode(), mode=modo)
    # test 5
    client_socketTCP.send(MENSAJE_LARGO, mode=modo)

    client_socketTCP.close()
    print("Conexion cerrada (close)")
