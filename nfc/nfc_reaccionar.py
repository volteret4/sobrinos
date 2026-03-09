import json
import subprocess
import time
import os
import sys
from smartcard.System import readers
from smartcard.util import toHexString

# Importar KodiAPIManager desde reproductores/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from reproductores.kodi_api_manager import KodiAPIManager

CONFIG_FILE = "nfc_playlist.json"


def leer_id_logico(connection):
    """Intenta leer el ID personalizado del bloque 4"""
    try:
        command = [0xFF, 0xB0, 0x00, 0x04, 0x10]
        data, sw1, sw2 = connection.transmit(command)
        if sw1 == 0x90:
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


def ejecutar_accion(entrada, config):
    """Ejecuta la acción correspondiente según el reproductor configurado."""
    reproductor = entrada.get("reproductor", "")

    if reproductor == "kodi":
        kodi_cfg = config.get("_kodi", {})
        kodi = KodiAPIManager(
            host=kodi_cfg.get("host", "localhost"),
            port=kodi_cfg.get("port", 8080),
            username=kodi_cfg.get("usuario", ""),
            password=kodi_cfg.get("password", ""),
        )
        exito = kodi.play_file(entrada["ruta"])
        if not exito:
            print(f"Error: Kodi no pudo reproducir '{entrada['ruta']}'")
    else:
        subprocess.Popen(" ".join(entrada["comando"]), shell=True)


def monitorear():
    reader_list = readers()
    if not reader_list:
        return
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
                    entrada = config[id_detectado]
                    reproductor = entrada.get("reproductor", "desconocido")
                    print(f"Tarjeta reconocida: {entrada['nombre']} [{reproductor}]")
                    ejecutar_accion(entrada, config)
                else:
                    print(f"ID desconocido: {id_detectado}")

                ultima_tarjeta, tiempo_ultima = id_detectado, ahora

            connection.disconnect()
        except:
            pass
        time.sleep(0.5)


if __name__ == "__main__":
    monitorear()
