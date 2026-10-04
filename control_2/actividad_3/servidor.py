# Actividad 3 - Control 2 - Redes (CC4303), primavera 2026
# Universidad de Chile - FCFM - Departamento de Ciencias de la Computacion
# Profesora: Ivana Bachmann
# Integrante: Diego Salinas
#
# Servidor: acepta conexiones SocketTCP y escribe en salida estándar los archivos que recibe.
# Uso: python3 servidor.py IP PUERTO [-debug] [-perdida PORCENTAJE]

import sys

import SocketTCP

BUFF_SIZE = 64

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python3 servidor.py IP PUERTO [-debug] [-perdida PORCENTAJE]", file=sys.stderr)
        sys.exit(1)
    direccion_servidor = (sys.argv[1], int(sys.argv[2]))
    SocketTCP.MODO_DEBUG = "-debug" in sys.argv
    if "-perdida" in sys.argv:
        SocketTCP.PROBABILIDAD_PERDIDA = int(sys.argv[sys.argv.index("-perdida") + 1])
    server_socketTCP = SocketTCP.SocketTCP()
    server_socketTCP.bind(direccion_servidor)
    # Los mensajes informativos van a stderr, en stdout solo queda el contenido de los archivos.
    print("Servidor escuchando en", direccion_servidor, file=sys.stderr)
    while True:
        connection_socketTCP, new_address = server_socketTCP.accept()
        print("Conexion aceptada, nuevo socket en", new_address, file=sys.stderr)
        # Igual que con sockets de python, se llama a recv hasta que retorne b"": eso pasa cuando
        # recv recibe el FIN del cliente, y en ese caso recv ya se encargó de cerrar la conexión.
        total_recibido = 0
        mensaje = connection_socketTCP.recv(BUFF_SIZE)
        while mensaje:
            sys.stdout.buffer.write(mensaje)
            sys.stdout.flush()
            total_recibido += len(mensaje)
            mensaje = connection_socketTCP.recv(BUFF_SIZE)
        # Si la conexión sigue abierta (ej: se envió un archivo vacío) recv_close espera el FIN y cierra.
        connection_socketTCP.recv_close()
        print("\nArchivo recibido (" + str(total_recibido) + " bytes), conexion cerrada", file=sys.stderr)
