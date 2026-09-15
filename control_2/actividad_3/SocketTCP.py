# Actividad 3 - Control 2 - CC4303 Redes (Primavera 2026)
# Universidad de Chile - FCFM - Departamento de Ciencias de la Computacion
# Profesora: Ivana Bachmann
# Integrante: Diego Salinas
#
# Clase SocketTCP: sockets orientados a conexión implementados sobre sockets UDP
# usando Stop & Wait (3-way handshake, send/recv con ACKs y timeouts, y cierre de conexión).

import socket
import random
import sys
import time

# Estructura del header (5 bytes):
#   byte 0     -> flags: bit 0 = SYN, bit 1 = ACK, bit 2 = FIN
#   bytes 1..4 -> número de secuencia (entero sin signo, big endian)
# Después del header vienen a lo más 16 bytes de datos.
FLAG_SYN = 0b001
FLAG_ACK = 0b010
FLAG_FIN = 0b100
TAMANO_HEADER = 5
TAMANO_MAX_DATOS = 16
TAMANO_BUFFER_UDP = TAMANO_HEADER + TAMANO_MAX_DATOS
# El largo del mensaje se manda en el primer segmento de send() usando 8 bytes.
BYTES_LARGO_MENSAJE = 8

# Configuración global, los códigos cliente/servidor la cambian según los argumentos.
TIMEOUT_SEGUNDOS = 1.5
MODO_DEBUG = False
# Probabilidad (en %) de descartar un segmento antes de enviarlo, para simular pérdidas a mano.
# Como ambos extremos usan esta clase, las pérdidas ocurren en las dos direcciones.
PROBABILIDAD_PERDIDA = 0

def debug(*mensaje):
    # Los mensajes de debug van a stderr para no mezclarse con el archivo recibido en stdout.
    if MODO_DEBUG:
        print("(debug)", *mensaje, file=sys.stderr, flush=True)

class SocketTCP:
    def __init__(self):
        self.socket_udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket_udp.settimeout(TIMEOUT_SEGUNDOS)
        self.timeout = TIMEOUT_SEGUNDOS
        self.direccion_destino = None
        self.seq = None
        # seq del último ACK del handshake (lado cliente), por si hay que reenviarlo.
        self.seq_ack_handshake = None
        # Conexiones ya aceptadas (dirección, seq del SYN) para ignorar SYN duplicados.
        self.conexiones_aceptadas = set()
        # Estado de recv: bytes del mensaje actual que aún no llegan y datos que llegaron
        # pero no se han retornado porque no cabían en buff_size.
        self.bytes_por_recibir = 0
        self.datos_sin_entregar = b""
        self.conexion_cerrada = False

    @staticmethod
    def parse_segment(segmento):
        # Pasa un segmento en bytes a un diccionario. Retorna None si es muy corto.
        if len(segmento) < TAMANO_HEADER:
            return None
        flags = segmento[0]
        return {
            "SYN": (flags & FLAG_SYN) != 0,
            "ACK": (flags & FLAG_ACK) != 0,
            "FIN": (flags & FLAG_FIN) != 0,
            "SEQ": int.from_bytes(segmento[1:TAMANO_HEADER], "big"),
            "DATOS": segmento[TAMANO_HEADER:],
        }

    @staticmethod
    def create_segment(diccionario):
        # Arma un segmento en bytes a partir del diccionario (inverso de parse_segment).
        flags = 0
        if diccionario.get("SYN"):
            flags |= FLAG_SYN
        if diccionario.get("ACK"):
            flags |= FLAG_ACK
        if diccionario.get("FIN"):
            flags |= FLAG_FIN
        header = bytes([flags]) + diccionario["SEQ"].to_bytes(TAMANO_HEADER - 1, "big")
        return header + diccionario.get("DATOS", b"")

    @staticmethod
    def describir(segmento):
        # Texto corto del segmento para el modo debug, ej: "[SYN+ACK seq=43]".
        flags = [nombre for nombre in ("SYN", "FIN", "ACK") if segmento[nombre]]
        texto = "+".join(flags) if flags else "DATOS"
        texto += " seq=" + str(segmento["SEQ"])
        if segmento["DATOS"]:
            texto += " datos=" + str(segmento["DATOS"])
        return "[" + texto + "]"

    def enviar_segmento(self, syn=False, ack=False, fin=False, seq=0, datos=b""):
        segmento = {"SYN": syn, "ACK": ack, "FIN": fin, "SEQ": seq, "DATOS": datos}
        if random.randint(1, 100) <= PROBABILIDAD_PERDIDA:
            debug("(perdida simulada) no se envia", self.describir(segmento))
            return
        self.socket_udp.sendto(self.create_segment(segmento), self.direccion_destino)

    def recibir_segmento(self):
        # Espera un segmento a lo más un timeout. Retorna (segmento, direccion) o (None, None) si
        # se cumple el timeout. Los segmentos mal formados se ignoran.
        while True:
            try:
                mensaje, direccion = self.socket_udp.recvfrom(TAMANO_BUFFER_UDP)
            except socket.timeout:
                return None, None
            except ConnectionResetError:
                # En Windows un sendto a un puerto cerrado hace fallar el siguiente recvfrom.
                continue
            segmento = self.parse_segment(mensaje)
            if segmento is not None:
                return segmento, direccion

    def bind(self, address):
        self.socket_udp.bind(address)

    def connect(self, address):
        # Lado cliente del 3-way handshake.
        self.direccion_destino = address
        seq_inicial = random.randint(0, 100)
        debug("connect: se envia SYN con seq =", seq_inicial)
        self.enviar_segmento(syn=True, seq=seq_inicial)
        while True:
            segmento, direccion = self.recibir_segmento()
            if segmento is None:
                debug("connect: timeout esperando SYN+ACK, reenviando SYN seq =", seq_inicial)
                self.enviar_segmento(syn=True, seq=seq_inicial)
                continue
            if segmento["SYN"] and segmento["ACK"] and segmento["SEQ"] == seq_inicial + 1:
                break
            debug("connect: se ignora", self.describir(segmento))
        # El SYN+ACK viene desde el nuevo socket del servidor, desde ahora hablamos con esa dirección.
        self.direccion_destino = direccion
        self.seq = seq_inicial + 2
        self.seq_ack_handshake = self.seq
        debug("connect: SYN+ACK recibido desde", direccion, "-> se envia ACK con seq =", self.seq)
        self.enviar_segmento(ack=True, seq=self.seq)

    def accept(self):
        # Lado servidor del 3-way handshake. Retorna un nuevo SocketTCP asociado a otra dirección.
        while True:
            segmento, direccion_cliente = self.recibir_segmento()
            if segmento is None:
                continue
            if not segmento["SYN"] or segmento["ACK"] or segmento["FIN"]:
                debug("accept: se ignora", self.describir(segmento))
                continue
            if (direccion_cliente, segmento["SEQ"]) in self.conexiones_aceptadas:
                debug("accept: SYN duplicado de una conexion ya aceptada, se ignora")
                continue
            break
        seq_cliente = segmento["SEQ"]
        debug("accept: SYN recibido desde", direccion_cliente, "con seq =", seq_cliente)
        nuevo_socket = SocketTCP()
        # Puerto 0 = el sistema operativo elige un puerto libre, distinto al del socket que escucha.
        nuevo_socket.bind((self.socket_udp.getsockname()[0], 0))
        nuevo_socket.direccion_destino = direccion_cliente
        debug("accept: se envia SYN+ACK con seq =", seq_cliente + 1, "desde", nuevo_socket.socket_udp.getsockname())
        nuevo_socket.enviar_segmento(syn=True, ack=True, seq=seq_cliente + 1)
        while True:
            respuesta, direccion = nuevo_socket.recibir_segmento()
            if respuesta is None:
                debug("accept: timeout esperando ACK, reenviando SYN+ACK seq =", seq_cliente + 1)
                nuevo_socket.enviar_segmento(syn=True, ack=True, seq=seq_cliente + 1)
                continue
            if direccion != direccion_cliente:
                continue
            if respuesta["ACK"] and not respuesta["SYN"] and not respuesta["FIN"] and respuesta["SEQ"] == seq_cliente + 2:
                debug("accept: ACK recibido con seq =", respuesta["SEQ"], "-> conexion establecida")
                break
            if not respuesta["SYN"] and not respuesta["ACK"] and respuesta["SEQ"] == seq_cliente + 2:
                # Caso borde: se perdió el último ACK y el cliente ya empezó a mandar datos (o FIN).
                # Se da el handshake por terminado y se descarta el segmento sin ACK: el cliente lo
                # reenviará por timeout y lo recibirá recv (o recv_close).
                debug("accept: llego", self.describir(respuesta), "en vez del ACK -> se perdio el ACK del handshake,",
                      "se da la conexion por establecida y se descarta el segmento (el cliente lo reenviara)")
                break
            debug("accept: se ignora", self.describir(respuesta))
        nuevo_socket.seq = seq_cliente + 2
        self.conexiones_aceptadas.add((direccion_cliente, seq_cliente))
        return nuevo_socket, nuevo_socket.socket_udp.getsockname()

    def es_syn_ack_duplicado(self, segmento, direccion):
        # Si el servidor no recibió nuestro ACK del handshake sigue mandando SYN+ACK: se lo reenviamos.
        if segmento["SYN"] and segmento["ACK"] and direccion == self.direccion_destino:
            if self.seq_ack_handshake is not None:
                debug("SYN+ACK duplicado -> se reenvia el ACK del handshake con seq =", self.seq_ack_handshake)
                self.enviar_segmento(ack=True, seq=self.seq_ack_handshake)
            return True
        return False

    def enviar_con_stop_and_wait(self, datos):
        # Envía un segmento de datos y lo reenvía hasta recibir el ACK con seq = seq + len(datos).
        seq_ack_esperado = self.seq + len(datos)
        self.enviar_segmento(seq=self.seq, datos=datos)
        while True:
            segmento, direccion = self.recibir_segmento()
            if segmento is None:
                debug("send: timeout esperando ACK", seq_ack_esperado, "-> reenviando segmento seq =", self.seq)
                self.enviar_segmento(seq=self.seq, datos=datos)
                continue
            if direccion != self.direccion_destino or self.es_syn_ack_duplicado(segmento, direccion):
                continue
            if segmento["ACK"] and not segmento["SYN"] and not segmento["FIN"] and segmento["SEQ"] == seq_ack_esperado:
                self.seq = seq_ack_esperado
                return
            debug("send: se ignora", self.describir(segmento), "(se esperaba ACK seq =", str(seq_ack_esperado) + ")")

    def send(self, message):
        # Primer segmento: largo del mensaje. Luego el mensaje en trozos de a lo más 16 bytes.
        largo_mensaje = len(message)
        debug("send: enviando mensaje de", largo_mensaje, "bytes")
        self.enviar_con_stop_and_wait(largo_mensaje.to_bytes(BYTES_LARGO_MENSAJE, "big"))
        for inicio in range(0, largo_mensaje, TAMANO_MAX_DATOS):
            self.enviar_con_stop_and_wait(message[inicio:inicio + TAMANO_MAX_DATOS])

    def recibir_con_stop_and_wait(self):
        # Espera el siguiente segmento de datos en orden, lo confirma con ACK y retorna sus datos.
        # Si llega un FIN se maneja el cierre de conexión y se retorna None.
        while True:
            segmento, direccion = self.recibir_segmento()
            if segmento is None or direccion != self.direccion_destino:
                continue
            if self.es_syn_ack_duplicado(segmento, direccion):
                continue
            if segmento["FIN"] and not segmento["ACK"] and segmento["SEQ"] == self.seq:
                self.terminar_cierre()
                return None
            if segmento["SYN"] or segmento["ACK"] or segmento["FIN"]:
                debug("recv: se ignora", self.describir(segmento))
                continue
            if segmento["SEQ"] == self.seq:
                self.seq += len(segmento["DATOS"])
                self.enviar_segmento(ack=True, seq=self.seq)
                return segmento["DATOS"]
            if segmento["SEQ"] < self.seq:
                # Segmento repetido: se perdió nuestro ACK, así que lo volvemos a mandar sin guardar los datos.
                seq_ack = segmento["SEQ"] + len(segmento["DATOS"])
                debug("recv: segmento duplicado seq =", segmento["SEQ"], "-> se reenvia ACK seq =", seq_ack)
                self.enviar_segmento(ack=True, seq=seq_ack)
                continue
            debug("recv: se ignora segmento con seq futuro", segmento["SEQ"], "(se esperaba", str(self.seq) + ")")

    def recv(self, buff_size):
        if self.conexion_cerrada:
            return b""
        if self.bytes_por_recibir == 0 and len(self.datos_sin_entregar) == 0:
            # Empieza un mensaje nuevo: el primer segmento trae su largo.
            datos = self.recibir_con_stop_and_wait()
            if datos is None:
                return b""
            self.bytes_por_recibir = int.from_bytes(datos, "big")
            debug("recv: se va a recibir un mensaje de", self.bytes_por_recibir, "bytes")
        # Se sigue recibiendo hasta tener buff_size bytes o hasta que se termine el mensaje.
        while len(self.datos_sin_entregar) < buff_size and self.bytes_por_recibir > 0:
            datos = self.recibir_con_stop_and_wait()
            if datos is None:
                break
            self.datos_sin_entregar += datos
            self.bytes_por_recibir -= len(datos)
        # Si llegó más de buff_size (ej: buff_size = 14 y llegó un trozo de 16) el resto queda guardado
        # para el siguiente llamado a recv.
        resultado = self.datos_sin_entregar[:buff_size]
        self.datos_sin_entregar = self.datos_sin_entregar[buff_size:]
        return resultado

    def close(self):
        # Cierre desde el lado "Host A": FIN -> FIN+ACK -> ACK.
        seq_fin = self.seq
        debug("close: se envia FIN con seq =", seq_fin)
        self.enviar_segmento(fin=True, seq=seq_fin)
        timeouts = 0
        recibio_fin_ack = False
        while timeouts < 3:
            segmento, direccion = self.recibir_segmento()
            if segmento is None:
                timeouts += 1
                if timeouts < 3:
                    debug("close: timeout", timeouts, "esperando FIN+ACK -> reenviando FIN")
                    self.enviar_segmento(fin=True, seq=seq_fin)
                continue
            if direccion != self.direccion_destino:
                continue
            if segmento["FIN"] and segmento["ACK"] and segmento["SEQ"] == seq_fin + 1:
                recibio_fin_ack = True
                break
            debug("close: se ignora", self.describir(segmento))
        if recibio_fin_ack:
            self.seq = seq_fin + 2
            debug("close: FIN+ACK recibido -> se envia el ultimo ACK 3 veces con seq =", self.seq)
            for _ in range(3):
                self.enviar_segmento(ack=True, seq=self.seq)
                time.sleep(self.timeout)
        else:
            debug("close: 3 timeouts sin FIN+ACK -> se asume que la contraparte se cerro")
        self.cerrar_recursos()

    def recv_close(self):
        # Cierre desde el lado "Host B": espera el FIN y luego lo maneja en terminar_cierre.
        while not self.conexion_cerrada:
            datos = self.recibir_con_stop_and_wait()
            if datos is not None:
                debug("recv_close: llegaron datos nuevos mientras se esperaba FIN, se descartan:", datos)

    def terminar_cierre(self):
        # Llega el FIN: se responde FIN+ACK y se espera el último ACK a lo más 3 timeouts.
        seq_fin = self.seq
        debug("recv_close: FIN recibido con seq =", seq_fin, "-> se envia FIN+ACK con seq =", seq_fin + 1)
        self.enviar_segmento(fin=True, ack=True, seq=seq_fin + 1)
        timeouts = 0
        while timeouts < 3:
            segmento, direccion = self.recibir_segmento()
            if segmento is None:
                timeouts += 1
                if timeouts < 3:
                    debug("recv_close: timeout", timeouts, "esperando ultimo ACK -> reenviando FIN+ACK")
                    self.enviar_segmento(fin=True, ack=True, seq=seq_fin + 1)
                continue
            if direccion != self.direccion_destino:
                continue
            if segmento["ACK"] and not segmento["FIN"] and not segmento["SYN"] and segmento["SEQ"] == seq_fin + 2:
                debug("recv_close: ultimo ACK recibido -> conexion cerrada")
                break
            if segmento["FIN"] and not segmento["ACK"]:
                debug("recv_close: FIN duplicado -> reenviando FIN+ACK")
                self.enviar_segmento(fin=True, ack=True, seq=seq_fin + 1)
                continue
            debug("recv_close: se ignora", self.describir(segmento))
        else:
            debug("recv_close: 3 timeouts sin el ultimo ACK -> se asume que la contraparte se cerro")
        self.seq = seq_fin + 2
        self.cerrar_recursos()

    def cerrar_recursos(self):
        self.conexion_cerrada = True
        self.socket_udp.close()
