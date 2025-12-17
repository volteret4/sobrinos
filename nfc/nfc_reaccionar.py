import json
import subprocess
import time
import os
from smartcard.System import readers
from smartcard.util import toHexString

CONFIG_FILE = "nfc_playlist.json"

def leer_id_logico(connection):
    """Intenta leer el ID personalizado del bloque 4"""
    try:
        # Comando para leer 16 bytes del bloque 4
        command = [0xFF, 0xB0, 0x00, 0x04, 0x10]
        data, sw1, sw2 = connection.transmit(command)
        if sw1 == 0x90:
            # Convertimos a hex y tomamos los primeros 8 caracteres (lo que grabamos)
            return toHexString(data).replace(' ', '')[:8].upper()
    except:
        return None
    return None

def obtener_uid_fisico(connection):
    """Obtiene el UID de fábrica"""
    try:
        command = [0xFF, 0xCA, 0x00, 0x00, 0x00]
        data, sw1, sw2 = connection.transmit(command)
        if sw1 == 0x90:
            return toHexString(data).replace(' ', '')
    except:
        return None

def monitorear():
    reader_list = readers()
    if not reader_list: return
    reader = reader_list[0]
    ultima_tarjeta, tiempo_ultima = None, 0

    print(">>> Lector Activo (Busca IDs físicos y lógicos) <<<")

    while True:
        try:
            connection = reader.createConnection()
            connection.connect()

            # 1. Intentar leer el ID lógico (el que pudimos haber grabado nosotros)
            id_detectado = leer_id_logico(connection)

            # 2. Si no hay ID lógico o no está en el JSON, intentar con el UID físico
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)

            if id_detectado not in config:
                id_detectado = obtener_uid_fisico(connection)

            ahora = time.time()
            if id_detectado and (id_detectado != ultima_tarjeta or ahora - tiempo_ultima > 4):
                if id_detectado in config:
                    print(f"Tarjeta reconocida: {config[id_detectado]['nombre']}")
                    subprocess.Popen(" ".join(config[id_detectado]['comando']), shell=True)
                else:
                    print(f"ID desconocido: {id_detectado}")

                ultima_tarjeta, tiempo_ultima = id_detectado, ahora

            connection.disconnect()
        except:
            pass
        time.sleep(0.5)

if __name__ == "__main__":
    monitorear()
