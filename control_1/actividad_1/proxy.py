# Actividad 1 - Control 1 - CC4303 Redes (Primavera 2026)
# Universidad de Chile - FCFM - Departamento de Ciencias de la Computacion
# Profesora: Ivana Bachmann
# Integrante: Diego Salinas

import socket
import sys
import json

# Dominio inventado.
DOMINIO_IMAGEN_LOCAL = "imagen.gatobloqueado.cl"
ARCHIVO_IMAGEN_LOCAL = "403.jpg"

def parse_HTTP_message(http_message):
    # Recibe mensaje completo en bytes y lo transforma a diccionario.
    partes = http_message.split(b"\r\n\r\n", 1)
    head = partes[0]
    body = partes[1] if len(partes) > 1 else b""
    lineas = head.split(b"\r\n")
    start_line = lineas[0].decode(errors="replace")
    headers = {}
    for linea in lineas[1:]:
        if linea == b"":
            continue
        linea_texto = linea.decode(errors="replace")
        if ":" in linea_texto:
            nombre_header, valor_header = linea_texto.split(":", 1)
            headers[nombre_header.strip()] = valor_header.strip()
    mensaje = {
        "start_line": start_line,
        "headers": headers,
        "body": body,
    }
    partes_start_line = start_line.split(" ")
    if len(partes_start_line) > 0 and partes_start_line[0].startswith("HTTP/"):
        # Es una respuesta.
        mensaje["tipo"] = "response"
        mensaje["version"] = partes_start_line[0]
        mensaje["codigo"] = partes_start_line[1] if len(partes_start_line) > 1 else ""
        mensaje["texto_estado"] = " ".join(partes_start_line[2:])
    else:
        # Es una petición.
        mensaje["tipo"] = "request"
        mensaje["metodo"] = partes_start_line[0] if len(partes_start_line) > 0 else ""
        mensaje["url"] = partes_start_line[1] if len(partes_start_line) > 1 else "/"
        mensaje["version"] = partes_start_line[2] if len(partes_start_line) > 2 else "HTTP/1.1"
    return mensaje

def create_HTTP_message(mensaje):
    # Recibe el diccionario y arma un mensaje en bytes para mandarse por el socket.
    if mensaje["tipo"] == "request":
        start_line = mensaje["metodo"] + " " + mensaje["url"] + " " + mensaje["version"]
    else:
        start_line = mensaje["version"] + " " + mensaje["codigo"] + " " + mensaje["texto_estado"]
    # Se recalcula el content-leght.
    mensaje["headers"]["Content-Length"] = str(len(mensaje["body"]))
    texto_headers = ""
    for nombre_header in mensaje["headers"]:
        texto_headers += nombre_header + ": " + mensaje["headers"][nombre_header] + "\r\n"
    head_completo = start_line + "\r\n" + texto_headers + "\r\n"
    return head_completo.encode() + mensaje["body"]

def obtener_content_length(head_bytes):
    # Busca content-length en el head.
    lineas = head_bytes.decode(errors="replace").split("\r\n")
    for linea in lineas:
        if linea.lower().startswith("content-length:"):
            return int(linea.split(":", 1)[1].strip())
    return 0

def recibir_mensaje_http(conexion, buffer_size):
    # Recibe un mensaje HTTP completo desde un socket sin asumir que alcanza a llegar todo en un solo recv().
    mensaje = b""
    while b"\r\n\r\n" not in mensaje:
        trozo = conexion.recv(buffer_size)
        # Se cerro la conexión antes de mandar el head completo.
        if not trozo:
            return mensaje
        mensaje += trozo
    head, _, resto_body = mensaje.partition(b"\r\n\r\n")
    content_length = obtener_content_length(head)
    body = resto_body
    while len(body) < content_length:
        trozo = conexion.recv(buffer_size)
        if not trozo:
            break
        body += trozo
    return head + b"\r\n\r\n" + body

def cargar_configuracion(ruta_archivo):
    with open(ruta_archivo) as archivo:
        return json.load(archivo)

def separar_url(url):
    # Recibe url del start line y devuelve el host, puesto y path.
    sin_protocolo = url
    if sin_protocolo.startswith("http://"):
        sin_protocolo = sin_protocolo[len("http://"):]
    if "/" in sin_protocolo:
        indice_barra = sin_protocolo.index("/")
        autoridad = sin_protocolo[:indice_barra]
        path = sin_protocolo[indice_barra:]
    else:
        autoridad = sin_protocolo
        path = "/"
    if ":" in autoridad:
        host, puerto_texto = autoridad.split(":", 1)
        puerto = int(puerto_texto)
    else:
        host = autoridad
        puerto = 80  # puerto por defecto de HTTP
    return host, puerto, path

def esta_bloqueado(host, path, lista_bloqueados):
    # Revisa si el host está en la lista de bloqueados del JSON.
    host_y_path = host + path
    for bloqueado in lista_bloqueados:
        if "/" in bloqueado:
            if host_y_path.startswith(bloqueado):
                return True
        else:
            if host == bloqueado:
                return True
    return False

def censurar_palabras(texto, forbidden_words):
    # Reemplaza cada palabra prohibida dentro del texto.
    for diccionario_palabra in forbidden_words:
        for palabra_mala in diccionario_palabra:
            reemplazo = diccionario_palabra[palabra_mala]
            texto = texto.replace(palabra_mala, reemplazo)
    return texto

def crear_respuesta_403():
    cuerpo_html = (
        "<html><head><title>403 Forbidden</title></head><body>"
        "<h1>403 Forbidden</h1>"
        "<p>Esta pagina fue bloqueada por el proxy.</p>"
        "<img src='http://" + DOMINIO_IMAGEN_LOCAL + "/" + ARCHIVO_IMAGEN_LOCAL + "'>"
        "</body></html>"
    ).encode()
    respuesta = {
        "tipo": "response",
        "version": "HTTP/1.1",
        "codigo": "403",
        "texto_estado": "Forbidden",
        "headers": {"Content-Type": "text/html"},
        "body": cuerpo_html,
    }
    return create_HTTP_message(respuesta)

def crear_respuesta_imagen_local():
    with open(ARCHIVO_IMAGEN_LOCAL, "rb") as archivo_imagen:
        contenido = archivo_imagen.read()
    respuesta = {
        "tipo": "response",
        "version": "HTTP/1.1",
        "codigo": "200",
        "texto_estado": "OK",
        "headers": {"Content-Type": "image/jpeg"},
        "body": contenido,
    }
    return create_HTTP_message(respuesta)

def atender_cliente(socket_cliente, configuracion, buffer_size):
    mensaje_bytes = recibir_mensaje_http(socket_cliente, buffer_size)
    if mensaje_bytes == b"":
        socket_cliente.close()
        return
    request = parse_HTTP_message(mensaje_bytes)
    host, puerto, path = separar_url(request["url"])
    print("-> peticion:", request["metodo"], "host:", host, "puerto:", puerto, "path:", path)
    # Para la segunda petición del navegador.
    if host == DOMINIO_IMAGEN_LOCAL:
        socket_cliente.send(crear_respuesta_imagen_local())
        socket_cliente.close()
        return
    if esta_bloqueado(host, path, configuracion["blocked"]):
        socket_cliente.send(crear_respuesta_403())
        socket_cliente.close()
        return
    # Intermediario con el servidor real que espera el path y no la url completa.
    request["url"] = path
    request["headers"]["X-ElQuePregunta"] = configuracion["user"]
    request["headers"]["Connection"] = "close"
    try:
        socket_servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        socket_servidor.connect((host, puerto))
        socket_servidor.send(create_HTTP_message(request))
        respuesta_bytes = recibir_mensaje_http(socket_servidor, buffer_size)
        socket_servidor.close()
    except OSError as error:
        print("no se pudo contactar al servidor:", error)
        socket_cliente.close()
        return
    if respuesta_bytes == b"":
        socket_cliente.close()
        return
    response = parse_HTTP_message(respuesta_bytes)
    tipo_contenido = response["headers"].get("Content-Type", "")
    if "text" in tipo_contenido:
        cuerpo_texto = response["body"].decode(errors="replace")
        cuerpo_censurado = censurar_palabras(cuerpo_texto, configuracion["forbidden_words"])
        response["body"] = cuerpo_censurado.encode()
    socket_cliente.send(create_HTTP_message(response))
    socket_cliente.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python3 proxy.py config.json [puerto] [buffer_size]")
        sys.exit(1)
    configuracion = cargar_configuracion(sys.argv[1])
    # Se define 0.0.0.0 para que funcione localmente desde el WSL.
    IP_PROXY = "0.0.0.0"
    PUERTO_PROXY = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
    BUFFER_SIZE = int(sys.argv[3]) if len(sys.argv) > 3 else 4096
    socket_proxy = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    socket_proxy.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    socket_proxy.bind((IP_PROXY, PUERTO_PROXY))
    socket_proxy.listen(5)
    print("Proxy escuchando en", IP_PROXY, "puerto", PUERTO_PROXY, "(buffer_size =", BUFFER_SIZE, ")")
    while True:
        socket_cliente, direccion_cliente = socket_proxy.accept()
        atender_cliente(socket_cliente, configuracion, BUFFER_SIZE)
