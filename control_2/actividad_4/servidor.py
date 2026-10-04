# Actividad 4 - Control 2 - Redes (CC4303), primavera 2026
# Universidad de Chile - FCFM - Departamento de Ciencias de la Computacion
# Profesora: Ivana Bachmann
# Integrante: Diego Salinas
#
# Servidor: acepta conexiones SocketTCP y escribe en salida estandar los archivos que recibe.
# Uso: python3 servidor.py IP PUERTO [-mode go_back_n|stop_and_wait] [-timeout SEGUNDOS]
#                          [-perdida PORCENTAJE] [-debug]

import sys

import SocketTCP

BUFF_SIZE = 64

def leer_opcion(nombre, por_defecto):
    if nombre in sys.argv:
        return sys.argv[sys.argv.index(nombre) + 1]
    return por_defecto

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python3 servidor.py IP PUERTO [-mode M] [-timeout S] [-perdida P] [-debug]", file=sys.stderr)
        sys.exit(1)
    direccion_servidor = (sys.argv[1], int(sys.argv[2]))
    modo = leer_opcion("-mode", "go_back_n")
    SocketTCP.MODO_DEBUG = "-debug" in sys.argv
    SocketTCP.PROBABILIDAD_PERDIDA = int(leer_opcion("-perdida", 0))
    SocketTCP.TIMEOUT_SEGUNDOS = float(leer_opcion("-timeout", SocketTCP.TIMEOUT_SEGUNDOS))
    server_socketTCP = SocketTCP.SocketTCP()
    server_socketTCP.bind(direccion_servidor)
    # Los mensajes informativos van a stderr, en stdout solo queda el contenido de los archivos.
    print("Servidor escuchando en", direccion_servidor, "en modo", modo, file=sys.stderr)
    while True:
        connection_socketTCP, new_address = server_socketTCP.accept()
        print("Conexion aceptada, nuevo socket en", new_address, file=sys.stderr)
        # Igual que con sockets de python, se llama a recv hasta que retorne b"": eso pasa cuando
        # recv recibe el FIN del cliente, y en ese caso recv ya se encargo de cerrar la conexion.
        total_recibido = 0
        mensaje = connection_socketTCP.recv(BUFF_SIZE, mode=modo)
        while mensaje:
            sys.stdout.buffer.write(mensaje)
            sys.stdout.flush()
            total_recibido += len(mensaje)
            mensaje = connection_socketTCP.recv(BUFF_SIZE, mode=modo)
        # Si la conexion sigue abierta (ej: se envio un archivo vacio) recv_close espera el FIN y cierra.
        connection_socketTCP.recv_close()
        print("Archivo recibido (" + str(total_recibido) + " bytes), conexion cerrada", file=sys.stderr)
        print("resultado segmentos enviados =", connection_socketTCP.number_of_sent_segments, file=sys.stderr)
