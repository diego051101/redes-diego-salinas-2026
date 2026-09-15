# Actividad 3 - Control 2 - CC4303 Redes (Primavera 2026)
# Universidad de Chile - FCFM - Departamento de Ciencias de la Computacion
# Profesora: Ivana Bachmann
# Integrante: Diego Salinas
#
# Pruebas de send/recv/cierre (lado servidor). Se ejecuta junto a pruebas_cliente.py.
# Uso: python3 pruebas_servidor.py IP PUERTO [-debug] [-perdida PORCENTAJE]

import sys

import SocketTCP

MENSAJE_LARGO = ("Este es un mensaje largo para probar Stop & Wait con perdidas. " * 8).encode()

def revisar(nombre, recibido, esperado):
    print(nombre, "received:", recibido)
    print(nombre + ":", "Passed" if recibido == esperado else "Failed")

if __name__ == "__main__":
    address = (sys.argv[1], int(sys.argv[2]))
    SocketTCP.MODO_DEBUG = "-debug" in sys.argv
    if "-perdida" in sys.argv:
        SocketTCP.PROBABILIDAD_PERDIDA = int(sys.argv[sys.argv.index("-perdida") + 1])

    server_socketTCP = SocketTCP.SocketTCP()
    server_socketTCP.bind(address)
    connection_socketTCP, new_address = server_socketTCP.accept()
    print("Nuevo socket en", new_address)

    # test 1
    revisar("Test 1", connection_socketTCP.recv(16), "Mensje de len=16".encode())
    # test 2
    revisar("Test 2", connection_socketTCP.recv(19), "Mensaje de largo 19".encode())
    # test 3: buff_size < message_length
    parte_1 = connection_socketTCP.recv(14)
    parte_2 = connection_socketTCP.recv(14)
    print("Test 3 largos:", len(parte_1), len(parte_2))
    revisar("Test 3", parte_1 + parte_2, "Mensaje de largo 19".encode())
    # test 4: mensaje de 2n bytes con n = 21 (no múltiplo de 16), recibido con 2 recv(n)
    parte_1 = connection_socketTCP.recv(21)
    parte_2 = connection_socketTCP.recv(21)
    print("Test 4 largos:", len(parte_1), len(parte_2))
    revisar("Test 4", parte_1 + parte_2, ("a" * 21 + "b" * 21).encode())
    # test 5: mensaje largo recibido con un único recv
    revisar("Test 5", connection_socketTCP.recv(len(MENSAJE_LARGO)), MENSAJE_LARGO)

    connection_socketTCP.recv_close()
    print("Conexion cerrada (recv_close)")
