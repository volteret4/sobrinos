import json
import os
import time
import uuid
from smartcard.System import readers
from smartcard.util import toHexString

CONFIG_FILE = "nfc_playlist.json"

REPRODUCTORES = {
    "1": {"nombre": "MoodeAudio (Red/HTTP)", "tipo": "http",  "id": "moode"},
    "2": {"nombre": "VLC (Local)",           "tipo": "local", "id": "vlc",  "comando": ["cvlc", "--play-and-exit"]},
    "3": {"nombre": "MPV (Local)",           "tipo": "local", "id": "mpv",  "comando": ["mpv", "--no-video"]},
    "4": {"nombre": "Kodi (JSON-RPC)",       "tipo": "kodi",  "id": "kodi"},
}


def cargar_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {}


def obtener_uid(reader):
    try:
        connection = reader.createConnection()
        connection.connect()
        command = [0xFF, 0xCA, 0x00, 0x00, 0x00]
        data, sw1, sw2 = connection.transmit(command)
        if sw1 == 0x90:
            return toHexString(data).replace(' ', '')
    except:
        return None


def escribir_nuevo_uid_en_tarjeta(reader, nuevo_id_hex):
    """Intenta escribir en el Bloque 4 (datos)."""
    try:
        connection = reader.createConnection()
        connection.connect()
        data_bytes = [int(nuevo_id_hex[i:i+2], 16) for i in range(0, len(nuevo_id_hex[:16]), 2)]
        data_bytes += [0] * (16 - len(data_bytes))
        write_command = [0xFF, 0xD6, 0x00, 0x04, 0x10] + data_bytes
        data, sw1, sw2 = connection.transmit(write_command)
        return sw1 == 0x90
    except Exception as e:
        print(f"Error de escritura: {e}")
        return False


def configurar_kodi(config_total):
    """Devuelve la config de Kodi guardada, preguntando si no existe o el usuario quiere cambiarla."""
    kodi_cfg = config_total.get("_kodi", {})
    if kodi_cfg.get("host"):
        print(f"  Kodi configurado en {kodi_cfg['host']}:{kodi_cfg['port']}")
        cambiar = input("  ¿Cambiar configuración de Kodi? (y/n) [n]: ").strip().lower()
        if cambiar != 'y':
            return kodi_cfg

    print("--- Configuración de Kodi ---")
    host     = input("  IP/hostname de Kodi [localhost]: ").strip() or "localhost"
    port     = input("  Puerto [8080]: ").strip() or "8080"
    usuario  = input("  Usuario (Enter para omitir): ").strip()
    password = input("  Contraseña (Enter para omitir): ").strip()
    kodi_cfg = {"host": host, "port": int(port), "usuario": usuario, "password": password}
    config_total["_kodi"] = kodi_cfg
    return kodi_cfg


def configurar_moode(config_total):
    """Devuelve la URL base de Moode guardada, preguntando si no existe o el usuario quiere cambiarla."""
    moode_cfg = config_total.get("_moode", {})
    if moode_cfg.get("url"):
        print(f"  MoodeAudio configurado en {moode_cfg['url']}")
        cambiar = input("  ¿Cambiar configuración de Moode? (y/n) [n]: ").strip().lower()
        if cambiar != 'y':
            return moode_cfg["url"]

    print("--- Configuración de MoodeAudio ---")
    ip = input("  IP/hostname de Moode: ").strip()
    url = f"http://{ip}/command/"
    config_total["_moode"] = {"url": url}
    return url


def seleccionar_reproductor():
    """Muestra el menú de reproductores y devuelve el elegido."""
    print("\n  Reproductores disponibles:")
    for k, v in REPRODUCTORES.items():
        print(f"    {k}. {v['nombre']}")
    sel = input("  Selecciona reproductor: ").strip()
    return REPRODUCTORES.get(sel, REPRODUCTORES["3"])


def main():
    print("--- Generador Universal con Gestión de IDs Únicos ---")
    config_total = cargar_config()

    r_list = readers()
    if not r_list:
        print("No se encontró lector.")
        return
    reader = r_list[0]

    print("\nEsperando tarjeta... (Ctrl+C para salir)")

    try:
        while True:
            uid = obtener_uid(reader)
            if uid:
                # Ignorar claves de configuración interna
                if uid.startswith("_"):
                    time.sleep(0.5)
                    continue

                # --- Lógica de ID Único ---
                if uid in config_total:
                    print(f"\n[!] El ID {uid} ya existe para: {config_total[uid].get('nombre', 'Desconocido')}")
                    nuevo = input("¿Generar nuevo ID único y grabarlo en la tarjeta? (y/n): ")

                    if nuevo.lower() == 'y':
                        nuevo_uid = uuid.uuid4().hex[:8].upper()
                        print(f"Generando nuevo ID: {nuevo_uid}...")
                        if escribir_nuevo_uid_en_tarjeta(reader, nuevo_uid):
                            print("¡Escritura exitosa en la tarjeta!")
                            uid = nuevo_uid
                        else:
                            print("Error: No se pudo escribir en la tarjeta.")
                            time.sleep(2)
                            continue
                    else:
                        print("Operación cancelada. Retire la tarjeta.")
                        time.sleep(2)
                        continue

                print(f"\n[+] Configurando ID: {uid}")

                player = seleccionar_reproductor()

                if player["tipo"] == "kodi":
                    configurar_kodi(config_total)
                    ruta = input("  Ruta en Kodi (ej. smb://nas/Music/Artist/Album/ o /ruta/local/): ").strip()
                    if not ruta:
                        print("Ruta vacía, cancelando.")
                        continue
                    nombre_meta = ruta.rstrip("/").split("/")[-1]
                    entrada = {
                        "nombre": nombre_meta,
                        "reproductor": "kodi",
                        "ruta": ruta,
                    }

                elif player["tipo"] == "http":
                    url_base = configurar_moode(config_total)
                    ruta_rel = input("  Ruta en NAS/ (ej. Rock/Artista/Album): ").strip()
                    if not ruta_rel:
                        print("Ruta vacía, cancelando.")
                        continue
                    comando_final = ["curl", "-G", "-s", "--data-urlencode",
                                     f"cmd=play_item NAS/{ruta_rel}", url_base]
                    nombre_meta = ruta_rel.rstrip("/").split("/")[-1]
                    entrada = {
                        "nombre": nombre_meta,
                        "reproductor": "moode",
                        "comando": comando_final,
                    }

                else:  # local (vlc, mpv)
                    ruta = input("  Ruta local: ").strip()
                    if not os.path.isdir(ruta):
                        print("Ruta inválida.")
                        continue
                    nombre_meta = os.path.basename(ruta)
                    entrada = {
                        "nombre": nombre_meta,
                        "reproductor": player["id"],
                        "comando": player["comando"] + [ruta],
                    }

                config_total[uid] = entrada
                with open(CONFIG_FILE, 'w') as f:
                    json.dump(config_total, f, indent=4, ensure_ascii=False)

                print(f"¡Asociación guardada para '{nombre_meta}' → {player['nombre']}!")
                print("Retire la tarjeta para continuar...")
                time.sleep(3)

            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\nSaliendo...")


if __name__ == "__main__":
    main()
