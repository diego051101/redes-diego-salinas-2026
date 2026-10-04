# Actividad 4 - Control 2 - Redes (CC4303), primavera 2026
# Universidad de Chile - FCFM - Departamento de Ciencias de la Computacion
# Profesora: Ivana Bachmann
# Integrante: Diego Salinas
#
# Clase SocketTCP: sockets orientados a conexion sobre UDP. Mantiene el Stop & Wait
# de la actividad 3 y agrega Go-Back-N con control de congestion estilo TCP Tahoe
# (slow start y congestion avoidance) usando las clases SocketUDP, SlidingWindowCC
# y CongestionControl.

import random
import sys
import time

from socketUDP import SocketUDP
from slidingWindowCC import SlidingWindowCC
from CongestionControl import CongestionControl

# Estructura del header (5 bytes):
#   byte 0     -> flags: bit 0 = SYN, bit 1 = ACK, bit 2 = FIN
#   bytes 1..4 -> numero de secuencia (entero sin signo, big endian)
FLAG_SYN = 0b001
FLAG_ACK = 0b010
FLAG_FIN = 0b100
TAMANO_HEADER = 5
TAMANO_MAX_DATOS = 16
TAMANO_BUFFER_UDP = TAMANO_HEADER + TAMANO_MAX_DATOS
# El largo del mensaje se manda en el primer segmento de send usando 8 bytes.
BYTES_LARGO_MENSAJE = 8
# Go-Back-N: tamaño de los trozos de datos y ventana fija cuando no hay control de congestion.
MSS = 8
VENTANA_SIN_CONTROL = 8

# Configuracion global, los codigos cliente/servidor la cambian segun los argumentos.
TIMEOUT_SEGUNDOS = 1.5
MODO_DEBUG = False
# Probabilidad (en %) de descartar un segmento recibido, para simular perdidas a mano.
PROBABILIDAD_PERDIDA = 0

def debug(*mensaje):
    # Los mensajes de debug van a stderr para no mezclarse con el archivo recibido en stdout.
    if MODO_DEBUG:
        print("(debug)", *mensaje, file=sys.stderr, flush=True)

class SocketTCP:
    def __init__(self):
        self.socket_udp = SocketUDP()
        self.socket_udp.settimeout(TIMEOUT_SEGUNDOS)
        self.timeout = TIMEOUT_SEGUNDOS
        self.direccion_destino = None
        self.seq = None
        # seq del ultimo ACK del handshake (lado cliente), por si hay que reenviarlo.
        self.seq_ack_handshake = None
        # Conexiones ya aceptadas (direccion, seq del SYN) para ignorar SYN duplicados.
        self.conexiones_aceptadas = set()
        # Estado de recv: bytes del mensaje actual que aun no llegan y datos que llegaron
        # pero no se han retornado porque no cabian en buff_size.
        self.bytes_por_recibir = 0
        self.datos_sin_entregar = b""
        self.conexion_cerrada = False
        # Control de congestion y estadisticas de Go-Back-N.
        self.congestion_control_on = True
        self.congestion_controler = None
        self.number_of_sent_segments = 0
        self.ultimo_seq_enviado = None

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

    def set_congestion_control(self, valor):
        # Setter pedido por la actividad: activa o desactiva el control de congestion.
        self.congestion_control_on = valor

    def direccion_local(self):
        return self.socket_udp.socket_udp.getsockname()

    def detener_timer(self):
        # El timer de SocketUDP no se detiene solo al recibir, hay que pararlo a mano.
        try:
            self.socket_udp.stop_timer(0)
        except AttributeError:
            pass

    def enviar_segmento(self, syn=False, ack=False, fin=False, seq=0, datos=b""):
        segmento = {"SYN": syn, "ACK": ack, "FIN": fin, "SEQ": seq, "DATOS": datos}
        self.number_of_sent_segments += 1
        try:
            self.socket_udp.sendto(self.create_segment(segmento), self.direccion_destino, timer_index=0)
        except RuntimeError:
            # El timer ya se habia cumplido mientras se enviaba: se reinicia y se envia igual.
            self.detener_timer()
            self.socket_udp.sendto(self.create_segment(segmento), self.direccion_destino, timer_index=0)

    def recibir_segmento(self):
        # Espera un segmento. Retorna (segmento, direccion), o (None, None) si se cumple
        # el timeout de SocketUDP. Los segmentos mal formados se ignoran.
        while True:
            try:
                mensaje, direccion = self.socket_udp.recvfrom(TAMANO_BUFFER_UDP)
            except TimeoutError:
                self.detener_timer()
                return None, None
            except ConnectionResetError:
                continue
            segmento = self.parse_segment(mensaje)
            if segmento is None:
                continue
            if random.randint(1, 100) <= PROBABILIDAD_PERDIDA:
                # Perdida simulada: el segmento llego, pero se descarta como si se hubiese perdido.
                debug("(perdida simulada) se descarta", self.describir(segmento))
                continue
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
        self.detener_timer()
        # El SYN+ACK viene desde el nuevo socket del servidor, desde ahora se habla con esa direccion.
        self.direccion_destino = direccion
        self.seq = seq_inicial + 2
        self.seq_ack_handshake = self.seq
        debug("connect: SYN+ACK recibido desde", direccion, "-> se envia ACK con seq =", self.seq)
        self.enviar_segmento(ack=True, seq=self.seq)
        self.detener_timer()

    def accept(self):
        # Lado servidor del 3-way handshake. Retorna un nuevo SocketTCP asociado a otra direccion.
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
        nuevo_socket.congestion_control_on = self.congestion_control_on
        # Puerto 0 = el sistema operativo elige un puerto libre, distinto al del socket que escucha.
        nuevo_socket.bind((self.direccion_local()[0], 0))
        nuevo_socket.direccion_destino = direccion_cliente
        debug("accept: se envia SYN+ACK con seq =", seq_cliente + 1, "desde", nuevo_socket.direccion_local())
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
                # Caso borde: se perdio el ultimo ACK y el cliente ya empezo a mandar datos (o FIN).
                # Se da el handshake por terminado y se descarta el segmento sin ACK: el cliente lo
                # reenviara por timeout y lo recibira recv (o recv_close).
                debug("accept: llego", self.describir(respuesta), "en vez del ACK -> se perdio el ACK del handshake,",
                      "se da la conexion por establecida y se descarta el segmento (el cliente lo reenviara)")
                break
            debug("accept: se ignora", self.describir(respuesta))
        nuevo_socket.detener_timer()
        nuevo_socket.seq = seq_cliente + 2
        self.conexiones_aceptadas.add((direccion_cliente, seq_cliente))
        return nuevo_socket, nuevo_socket.direccion_local()

    def es_syn_ack_duplicado(self, segmento, direccion):
        # Si el servidor no recibio el ACK del handshake sigue mandando SYN+ACK: se le reenvia.
        if segmento["SYN"] and segmento["ACK"] and direccion == self.direccion_destino:
            if self.seq_ack_handshake is not None:
                debug("SYN+ACK duplicado -> se reenvia el ACK del handshake con seq =", self.seq_ack_handshake)
                # No se detiene el timer: el emisor lo necesita corriendo para sus retransmisiones.
                self.enviar_segmento(ack=True, seq=self.seq_ack_handshake)
            return True
        return False

    # ------------------------------------------------------------------ envio y recepcion
    def send(self, message, mode="stop_and_wait"):
        if mode == "stop_and_wait":
            self.send_using_stop_and_wait(message)
        elif mode == "go_back_n":
            self.send_using_go_back_n(message)

    def recv(self, buff_size, mode="stop_and_wait"):
        if mode == "stop_and_wait":
            return self.recv_using_stop_and_wait(buff_size)
        elif mode == "go_back_n":
            return self.recv_using_go_back_n(buff_size)

    # ------------------------------------------------------------------ Stop & Wait
    def enviar_con_stop_and_wait(self, datos):
        # Envia un segmento de datos y lo reenvia hasta recibir el ACK con seq = seq + len(datos).
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
                self.detener_timer()
                self.seq = seq_ack_esperado
                return
            debug("send: se ignora", self.describir(segmento), "(se esperaba ACK seq =", str(seq_ack_esperado) + ")")

    def send_using_stop_and_wait(self, message):
        # Primer segmento: largo del mensaje. Luego el mensaje en trozos de a lo mas 16 bytes.
        largo_mensaje = len(message)
        debug("send: enviando mensaje de", largo_mensaje, "bytes con stop & wait")
        self.enviar_con_stop_and_wait(largo_mensaje.to_bytes(BYTES_LARGO_MENSAJE, "big"))
        for inicio in range(0, largo_mensaje, TAMANO_MAX_DATOS):
            self.enviar_con_stop_and_wait(message[inicio:inicio + TAMANO_MAX_DATOS])

    def recibir_con_stop_and_wait(self):
        # Espera el siguiente segmento de datos en orden, lo confirma con ACK y retorna sus datos.
        # Si llega un FIN se maneja el cierre de conexion y se retorna None.
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
                self.detener_timer()
                return segmento["DATOS"]
            if segmento["SEQ"] < self.seq:
                # Segmento repetido: se perdio el ACK, se reenvia sin guardar los datos de nuevo.
                seq_ack = segmento["SEQ"] + len(segmento["DATOS"])
                debug("recv: segmento duplicado seq =", segmento["SEQ"], "-> se reenvia ACK seq =", seq_ack)
                self.enviar_segmento(ack=True, seq=seq_ack)
                self.detener_timer()
                continue
            debug("recv: se ignora segmento con seq futuro", segmento["SEQ"], "(se esperaba", str(self.seq) + ")")

    def recv_using_stop_and_wait(self, buff_size):
        return self.recibir_mensaje(buff_size, self.recibir_con_stop_and_wait)

    # ------------------------------------------------------------------ Go-Back-N
    def send_using_go_back_n(self, message):
        # El primer elemento de la ventana informa el largo del mensaje, el resto son
        # trozos de MSS bytes. La ventana la maneja SlidingWindowCC.
        largo_mensaje = len(message)
        data_list = [largo_mensaje.to_bytes(BYTES_LARGO_MENSAJE, "big")]
        data_list += [message[inicio:inicio + MSS] for inicio in range(0, largo_mensaje, MSS)]
        if self.congestion_control_on:
            self.congestion_controler = CongestionControl(MSS)
            window_size = self.congestion_controler.get_MSS_in_cwnd()
        else:
            window_size = VENTANA_SIN_CONTROL
        debug("send: enviando mensaje de", largo_mensaje, "bytes con go back n")
        self.mostrar_congestion("inicio", window_size)
        data_window = SlidingWindowCC(window_size, data_list, self.seq)
        self.ultimo_seq_enviado = self.seq - 1
        self.enviar_nuevos_de_la_ventana(data_window, window_size)
        while data_window.get_data(0) is not None:
            segmento, direccion = self.recibir_segmento()
            if segmento is None:
                if self.congestion_control_on:
                    self.congestion_controler.event_timeout()
                    window_size = self.ajustar_ventana(data_window, window_size, "timeout")
                debug("send: timeout -> se reenvia la ventana desde seq =", data_window.get_sequence_number(0))
                self.reenviar_ventana(data_window, window_size)
                continue
            if direccion != self.direccion_destino or self.es_syn_ack_duplicado(segmento, direccion):
                continue
            if not segmento["ACK"] or segmento["SYN"] or segmento["FIN"]:
                debug("send: se ignora", self.describir(segmento))
                continue
            pasos = self.avanzar_ventana(data_window, window_size, segmento["SEQ"])
            if pasos == 0:
                debug("send: ACK duplicado seq =", segmento["SEQ"], "-> se ignora")
                continue
            self.seq = segmento["SEQ"]
            if self.congestion_control_on:
                self.congestion_controler.event_ack_received()
                window_size = self.ajustar_ventana(data_window, window_size, "ack")
            self.enviar_nuevos_de_la_ventana(data_window, window_size)
        self.detener_timer()

    def avanzar_ventana(self, data_window, window_size, ack_seq):
        # Mueve la ventana dejando fuera los elementos que el ACK acumulativo ya confirma.
        # Si el ACK queda mas alla de la ventana, la mueve completa y vuelve a revisar.
        pasos_totales = 0
        while True:
            pasos = 0
            for indice in range(window_size):
                seq_elemento = data_window.get_sequence_number(indice)
                if seq_elemento is None or seq_elemento >= ack_seq:
                    break
                pasos += 1
            if pasos == 0:
                return pasos_totales
            data_window.move_window(pasos)
            pasos_totales += pasos
            if pasos < window_size:
                return pasos_totales

    def ajustar_ventana(self, data_window, window_size, motivo):
        # Lleva el tamaño de la ventana de envio al valor que indica la ventana de congestion.
        nuevo_window_size = max(1, self.congestion_controler.get_MSS_in_cwnd())
        if nuevo_window_size != window_size:
            data_window.update_window_size(nuevo_window_size)
        self.mostrar_congestion(motivo, nuevo_window_size)
        return nuevo_window_size

    def enviar_nuevos_de_la_ventana(self, data_window, window_size):
        # Envia los elementos de la ventana que todavia no han sido enviados.
        for indice in range(window_size):
            datos = data_window.get_data(indice)
            seq_elemento = data_window.get_sequence_number(indice)
            if datos is None:
                return
            if seq_elemento > self.ultimo_seq_enviado:
                self.enviar_segmento(seq=seq_elemento, datos=datos)
                self.ultimo_seq_enviado = seq_elemento

    def reenviar_ventana(self, data_window, window_size):
        # Go-Back-N: ante un timeout se reenvia la ventana completa.
        self.detener_timer()
        for indice in range(window_size):
            datos = data_window.get_data(indice)
            seq_elemento = data_window.get_sequence_number(indice)
            if datos is None:
                return
            self.enviar_segmento(seq=seq_elemento, datos=datos)
            self.ultimo_seq_enviado = seq_elemento

    def mostrar_congestion(self, motivo, window_size):
        if not MODO_DEBUG:
            return
        if not self.congestion_control_on:
            debug("cc:", motivo, "-> sin control de congestion, ventana =", window_size, "segmentos")
            return
        controlador = self.congestion_controler
        estado = "slow start" if controlador.is_state_slow_start() else "congestion avoidance"
        debug("cc:", motivo, "-> estado =", estado, ", cwnd =", round(controlador.get_cwnd(), 2), "bytes, ssthresh =",
              controlador.get_ssthresh(), ", ventana =", window_size, "segmentos")

    def recibir_con_go_back_n(self):
        # Receptor Go-Back-N: acepta el segmento en orden y responde ACK acumulativo. Cualquier
        # segmento fuera de orden se descarta reenviando el ultimo ACK acumulativo.
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
                self.detener_timer()
                return segmento["DATOS"]
            debug("recv: segmento fuera de orden seq =", segmento["SEQ"], "-> se reenvia ACK seq =", self.seq)
            self.enviar_segmento(ack=True, seq=self.seq)
            self.detener_timer()

    def recv_using_go_back_n(self, buff_size):
        return self.recibir_mensaje(buff_size, self.recibir_con_go_back_n)

    # ------------------------------------------------------------------ recepcion comun
    def recibir_mensaje(self, buff_size, recibir_segmento_de_datos):
        if self.conexion_cerrada:
            return b""
        if self.bytes_por_recibir == 0 and len(self.datos_sin_entregar) == 0:
            # Empieza un mensaje nuevo: el primer segmento trae su largo.
            datos = recibir_segmento_de_datos()
            if datos is None:
                return b""
            self.bytes_por_recibir = int.from_bytes(datos, "big")
            debug("recv: se va a recibir un mensaje de", self.bytes_por_recibir, "bytes")
        # Se sigue recibiendo hasta tener buff_size bytes o hasta que se termine el mensaje.
        while len(self.datos_sin_entregar) < buff_size and self.bytes_por_recibir > 0:
            datos = recibir_segmento_de_datos()
            if datos is None:
                break
            self.datos_sin_entregar += datos
            self.bytes_por_recibir -= len(datos)
        # Si llego mas de buff_size el resto queda guardado para el siguiente llamado a recv.
        resultado = self.datos_sin_entregar[:buff_size]
        self.datos_sin_entregar = self.datos_sin_entregar[buff_size:]
        return resultado

    # ------------------------------------------------------------------ cierre
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
        self.detener_timer()
        if recibio_fin_ack:
            self.seq = seq_fin + 2
            debug("close: FIN+ACK recibido -> se envia el ultimo ACK 3 veces con seq =", self.seq)
            for _ in range(3):
                self.enviar_segmento(ack=True, seq=self.seq)
                self.detener_timer()
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
        # Llega el FIN: se responde FIN+ACK y se espera el ultimo ACK a lo mas 3 timeouts.
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
        self.detener_timer()
        self.seq = seq_fin + 2
        self.cerrar_recursos()

    def cerrar_recursos(self):
        self.conexion_cerrada = True
        self.socket_udp.close()
