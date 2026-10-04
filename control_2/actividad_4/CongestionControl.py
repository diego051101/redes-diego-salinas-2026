# Actividad 4 - Control 2 - Redes (CC4303), primavera 2026
# Universidad de Chile - FCFM - Departamento de Ciencias de la Computacion
# Profesora: Ivana Bachmann
# Integrante: Diego Salinas
#
# Clase CongestionControl: maneja la ventana de congestion con slow start y
# congestion avoidance (AIMD), al estilo de TCP Tahoe sin fast retransmit.

SLOW_START = "slow start"
CONGESTION_AVOIDANCE = "congestion avoidance"

class CongestionControl:
    def __init__(self, MSS: int):
        self.MSS = MSS
        # La ventana parte en 1 MSS y el umbral solo se define en el primer timeout.
        self.cwnd = MSS
        self.ssthresh = None
        self.current_state = SLOW_START

    def get_cwnd(self) -> int:
        # Tamaño de la ventana de congestion en bytes.
        return self.cwnd

    def get_MSS_in_cwnd(self) -> int:
        # Cantidad de MSS completos que caben en la ventana de congestion.
        return int(self.cwnd // self.MSS)

    def get_ssthresh(self) -> int:
        return self.ssthresh

    def is_state_slow_start(self) -> bool:
        return self.current_state == SLOW_START

    def is_state_congestion_avoidance(self) -> bool:
        return self.current_state == CONGESTION_AVOIDANCE

    def event_ack_received(self) -> None:
        if self.is_state_slow_start():
            # Crecimiento exponencial: 1 MSS por cada ACK recibido.
            self.cwnd += self.MSS
            if self.ssthresh is not None and self.cwnd >= self.ssthresh:
                self.current_state = CONGESTION_AVOIDANCE
        else:
            # Additive increase: 1 MSS por cada ventana completa de ACKs.
            self.cwnd += self.MSS / self.get_MSS_in_cwnd()

    def event_timeout(self) -> None:
        # Multiplicative decrease: el umbral baja a la mitad y la ventana vuelve a 1 MSS.
        self.ssthresh = int(self.cwnd / 2)
        self.cwnd = self.MSS
        self.current_state = SLOW_START
