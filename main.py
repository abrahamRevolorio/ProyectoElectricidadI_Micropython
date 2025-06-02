import network
import time
from machine import Pin
import usocket
import ssl
import ujson

# --- Datos para conectarse a la red WiFi ---
SSID = "NombreDeTuRed"
PASSWORD = "ClaveDeTuRed"

# --- Datos del servidor que maneja el WebSocket ---
WS_HOST = "backend-proyectoelectricidadi.onrender.com"
WS_PORT = 443
DEVICE_ID = "raspi-001"
WS_PATH = f"/ws/{DEVICE_ID}"

# --- LED que vamos a controlar (el del propio Pico W) ---
led = Pin(1, Pin.OUT)

# --- Se encarga de conectar el dispositivo a internet usando WiFi ---
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("Conectando a WiFi...")
        wlan.connect(SSID, PASSWORD)

        # Esperamos unos segundos mientras se conecta
        for _ in range(20):
            if wlan.isconnected():
                break
            time.sleep(1)
            print(".", end="")

    # Si se conectó, seguimos. Si no, reiniciamos el dispositivo.
    if wlan.isconnected():
        print("\n✅ WiFi conectado! IP:", wlan.ifconfig()[0])
    else:
        print("\n❌ Fallo WiFi")
        machine.reset()

# --- Abre la conexión WebSocket con el backend y realiza el handshake ---
def websocket_connect():
    print("\nConectando WebSocket...")

    try:
        # Resolvemos la IP y abrimos socket con cifrado SSL
        addr = usocket.getaddrinfo(WS_HOST, WS_PORT)[0][-1]
        sock = usocket.socket()
        sock.connect(addr)
        sock = ssl.wrap_socket(sock, server_hostname=WS_HOST, cert_reqs=ssl.CERT_NONE)

        # Enviamos la petición de handshake para activar el canal WebSocket
        handshake = (
            f"GET {WS_PATH} HTTP/1.1\r\n"
            f"Host: {WS_HOST}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )

        sock.write(handshake.encode())
        response = sock.recv(1024)

        # Si el servidor no acepta la conexión, salimos
        if b"101 Switching Protocols" not in response:
            print("❌ Handshake fallido")
            print("Respuesta:", response)
            sock.close()
            return None

        print("🟢 WebSocket conectado!")
        return sock

    except Exception as e:
        print("Error en conexión WS:", e)
        return None

# --- Recibe un mensaje, interpreta el comando y actúa sobre el LED ---
def handle_message(msg):
    try:
        data = ujson.loads(msg)
        cmd = data.get("command", "").lower()

        # Encendemos o apagamos el LED según el mensaje recibido
        if cmd == "led_on" or cmd == " led_on":
            led.value(1)
            print("💡 LED ENCENDIDO")
        elif cmd == "led_off" or cmd == " led_off":
            led.value(0)
            print("🌑 LED APAGADO")
        else:
            print("Comando no reconocido:", cmd)

    except Exception as e:
        print("Error procesando mensaje:", e)

# --- Este es el flujo principal: conecta WiFi, WebSocket y escucha mensajes ---
def main():
    connect_wifi()

    while True:
        sock = websocket_connect()
        if not sock:
            print("Reintentando en 5s...")
            time.sleep(5)
            continue

        try:
            print("\nEsperando mensajes...")
            while True:
                try:
                    # Leemos los primeros bytes del mensaje (cabecera WebSocket)
                    header = sock.recv(2)
                    if not header:
                        print("Conexión cerrada por servidor")
                        break

                    # Calculamos el tamaño del mensaje completo
                    opcode = header[0] & 0x0F
                    length = header[1] & 0x7F

                    if length == 126:
                        length = int.from_bytes(sock.recv(2), 'big')
                    elif length == 127:
                        length = int.from_bytes(sock.recv(8), 'big')

                    # Leemos el mensaje completo y lo mandamos a manejar
                    payload = sock.recv(length)
                    if opcode == 1:  # Mensaje de texto
                        message = payload.decode()
                        print("📩 Mensaje recibido:", message)
                        handle_message(message)

                except Exception as e:
                    print("Error en recepción:", e)
                    break

        finally:
            # Siempre cerramos conexión y reintentamos si algo salió mal
            sock.close()
            print("Reconectando en 3s...")
            time.sleep(3)

# --- Ejecutamos todo ---
if __name__ == "__main__":
    main()