# Actividad 2 - Control 1 - CC4303 Redes (Primavera 2026)
# Universidad de Chile - FCFM - Departamento de Ciencias de la Computacion
# Profesora: Ivana Bachmann
# Integrante: Diego Salinas

import socket
import sys

from dnslib import DNSRecord, RR
from dnslib.dns import QTYPE

# IP de a.root-servers.net (servidor raíz).
IP_RAIZ = "198.41.0.4"
PUERTO_DNS = 53
TIMEOUT_SEGUNDOS = 3

# Guardamos los ultimos veinte dominios consultados para el cache.
historial_consultas = []
ip_guardadas = {} 

def registrar_consulta_en_historial(dominio):
    historial_consultas.append(dominio)
    if len(historial_consultas) > 20:
        historial_consultas.pop(0)

def obtener_dominios_mas_frecuentes():
    # Cuenta cuántas veces aparece cada dominio y devuelve los tres mas repetidos.
    conteo = {}
    for dominio in historial_consultas:
        conteo[dominio] = conteo.get(dominio, 0) + 1
    dominios_ordenados = sorted(conteo.items(), key=lambda par: par[1], reverse=True)
    top_3 = [dominio for dominio, veces in dominios_ordenados[:3]]
    return top_3

def crear_respuesta_desde_cache(mensaje_consulta, ip):
    consulta = DNSRecord.parse(mensaje_consulta)
    respuesta = consulta.reply()
    nombre_dominio = str(consulta.get_q().get_qname())
    respuesta.add_answer(*RR.fromZone(nombre_dominio + " A " + ip))
    return respuesta.pack()

def enviar_consulta_dns(mensaje_bytes, ip_destino, puerto_destino=PUERTO_DNS):
    # Manda el mensaje a un servidor DNS y espera la respuesta.
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(TIMEOUT_SEGUNDOS)
    try:
        sock.sendto(mensaje_bytes, (ip_destino, puerto_destino))
        respuesta_bytes, _ = sock.recvfrom(4096)
    finally:
        sock.close()
    return respuesta_bytes

def buscar_ip_en_respuesta(respuesta_bytes):
    # Si hay un registro tipo A en el Answer devuelve esa IP, en caso contrario devuelve None.
    respuesta = DNSRecord.parse(respuesta_bytes)
    for registro in respuesta.rr:
        if QTYPE.get(registro.rtype) == "A":
            return str(registro.rdata)
    return None

def buscar_ip_en_additional(respuesta):
    for registro in respuesta.ar:
        if QTYPE.get(registro.rtype) == "A":
            return str(registro.rdata)
    return None

def buscar_nombre_ns_en_authority(respuesta):
    for registro in respuesta.auth:
        if QTYPE.get(registro.rtype) == "NS":
            return str(registro.rdata)
    return None

def resolver(mensaje_consulta, ip_servidor=IP_RAIZ, nombre_servidor=".", modo_debug=False):
    # Pregunta al servidor indicado y, si delega a otro Name Server, sigue preguntando.
    consulta = DNSRecord.parse(mensaje_consulta)
    dominio_consultado = str(consulta.get_q().get_qname())
    if modo_debug:
        print("(debug) Consultando '" + dominio_consultado + "' a '" + nombre_servidor +
              "' con direccion IP '" + ip_servidor + "'")
    try:
        respuesta_bytes = enviar_consulta_dns(mensaje_consulta, ip_servidor)
    except socket.timeout:
        return None
    respuesta = DNSRecord.parse(respuesta_bytes)
    # Ya llegó la respuesta final.
    if respuesta.header.a > 0 and buscar_ip_en_respuesta(respuesta_bytes) is not None:
        return respuesta_bytes
    # Se delegó a otro Name Server.
    if respuesta.header.auth > 0:
        nombre_siguiente_ns = buscar_nombre_ns_en_authority(respuesta)
        if nombre_siguiente_ns is None:
            return None
        ip_en_additional = buscar_ip_en_additional(respuesta)
        if ip_en_additional is not None:
            return resolver(mensaje_consulta, ip_en_additional, nombre_siguiente_ns, modo_debug)
        else:
            consulta_para_el_ns = DNSRecord.question(nombre_siguiente_ns).pack()
            respuesta_del_ns = resolver(consulta_para_el_ns, IP_RAIZ, ".", modo_debug)
            if respuesta_del_ns is None:
                return None
            ip_del_ns = buscar_ip_en_respuesta(respuesta_del_ns)
            if ip_del_ns is None:
                return None
            return resolver(mensaje_consulta, ip_del_ns, nombre_siguiente_ns, modo_debug)
    # Cualquier otro caso es ignorado.
    return None

if __name__ == "__main__":
    # Se define 0.0.0.0 para que funcione localmente desde el WSL.
    IP_SERVIDOR = "0.0.0.0"
    PUERTO_SERVIDOR = 8000
    modo_debug = "-debug" in sys.argv
    socket_resolver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    socket_resolver.bind((IP_SERVIDOR, PUERTO_SERVIDOR))
    print("Resolver escuchando en", IP_SERVIDOR, "puerto", PUERTO_SERVIDOR, "(modo_debug =", modo_debug, ")")
    while True:
        mensaje_recibido, direccion_cliente = socket_resolver.recvfrom(4096)
        print("Mensaje DNS recibido (bytes):")
        print(mensaje_recibido)
        consulta_cliente = DNSRecord.parse(mensaje_recibido)
        dominio = str(consulta_cliente.get_q().get_qname())
        registrar_consulta_en_historial(dominio)
        top_3_dominios = obtener_dominios_mas_frecuentes()
        if dominio in top_3_dominios and dominio in ip_guardadas:
            if modo_debug:
                print("(debug) '" + dominio + "' esta en el cache -> IP " + ip_guardadas[dominio])
            respuesta_final = crear_respuesta_desde_cache(mensaje_recibido, ip_guardadas[dominio])
        else:
            respuesta_final = resolver(mensaje_recibido, modo_debug=modo_debug)
            if respuesta_final is None:
                continue
            ip_encontrada = buscar_ip_en_respuesta(respuesta_final)
            if ip_encontrada is not None:
                ip_guardadas[dominio] = ip_encontrada
        socket_resolver.sendto(respuesta_final, direccion_cliente)
