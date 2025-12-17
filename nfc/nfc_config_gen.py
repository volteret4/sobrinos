import json
import os
import time
import uuid
from smartcard.System import readers
from smartcard.util import toHexString

CONFIG_FILE = "nfc_playlist.json"

REPRODUCTORES = {
    "1": {"nombre": "MoodeAudio (Red/HTTP)", "tipo": "http"},
    "2": {"nombre": "VLC (Local)", "comando": ["cvlc", "--play-and-exit"], "tipo": "local"},
    "3": {"nombre": "MPV (Local)", "comando": ["mpv", "--no-video"], "tipo": "local"}
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
        # Comando estándar para obtener UID
        command = [0xFF, 0xCA, 0x00, 0x00, 0x00]
        data, sw1, sw2 = connection.transmit(command)
        if sw1 == 0x90:
            return toHexString(data).replace(' ', '')
    except:
        return None

def escribir_nuevo_uid_en_tarjeta(reader, nuevo_id_hex):
    """
    Intenta escribir en el Bloque 1 (Datos).
    Nota: Esto requiere tarjetas que permitan escritura en bloques de datos.
    """
    try:
        connection = reader.createConnection()
        connection.connect()
        # Convertir el string hex a lista de bytes (limitado a 16 bytes para un bloque)
        # Tomamos los primeros 8 caracteres hex para simplificar
        data_bytes = [int(nuevo_id_hex[i:i+2], 16) for i in range(0, len(nuevo_id_hex[:16]), 2)]
        # Rellenar hasta 16 bytes si es necesario
        data_bytes += [0] * (16 - len(data_bytes))

        # Comando de escritura (APDU para Update Binary - Bloque 0x04)
        write_command = [0xFF, 0xD6, 0x00, 0x04, 0x10] + data_bytes
        data, sw1, sw2 = connection.transmit(write_command)

        return sw1 == 0x90
    except Exception as e:
        print(f"Error de escritura: {e}")
        return False

def main():
    print("--- Generador Universal con Gestión de IDs Únicos ---")
    for k, v in REPRODUCTORES.items():
        print(f"{k}. {v['nombre']}")

    sel = input("Selecciona tu reproductor: ")
    player = REPRODUCTORES.get(sel, REPRODUCTORES["3"])

    url_base = ""
    if player["tipo"] == "http":
        ip = input("Introduce la IP de Moode: ").strip()
        url_base = f"http://{ip}/command/"

    config_total = cargar_config()
    r_list = readers()
    if not r_list:
        print("No se encontró lector."); return
    reader = r_list[0]

    print("\nEsperando tarjeta...")

    try:
        while True:
            uid = obtener_uid(reader)
            if uid:
                # --- Lógica de ID Único ---
                if uid in config_total:
                    print(f"\n[!] ¡Atención! El ID {uid} ya existe para: {config_total[uid].get('nombre', 'Desconocido')}")
                    nuevo = input("¿Deseas generar un nuevo ID único y grabarlo en la tarjeta? (y/n): ")

                    if nuevo.lower() == 'y':
                        # Generar un ID aleatorio de 8 caracteres hex
                        nuevo_uid = uuid.uuid4().hex[:8].upper()
                        print(f"Generando nuevo ID: {nuevo_uid}...")

                        if escribir_nuevo_uid_en_tarjeta(reader, nuevo_uid):
                            print("¡Escritura exitosa en la tarjeta!")
                            uid = nuevo_uid
                        else:
                            print("Error: No se pudo escribir en la tarjeta. Es posible que esté protegida.")
                            time.sleep(2)
                            continue
                    else:
                        print("Operación cancelada. Retire la tarjeta.")
                        time.sleep(2)
                        continue

                print(f"\n[+] Configurando ID: {uid}")

                # --- Configuración de comandos (Moode o Local) ---
                if player["tipo"] == "http":
                    ruta_rel = input("Ruta en NAS/ (ej. Rock/Live): ").strip()
                    comando_final = ["curl", "-G", "-s", "--data-urlencode", f"cmd=play_item NAS/{ruta_rel}", url_base]
                    nombre_meta = ruta_rel.split('/')[-1]
                else:
                    ruta = input("Ruta local: ").strip()
                    if not os.path.isdir(ruta):
                        print("Ruta inválida."); continue
                    comando_final = player["comando"] + [ruta]
                    nombre_meta = os.path.basename(ruta)

                config_total[uid] = {"nombre": nombre_meta, "comando": comando_final}
                with open(CONFIG_FILE, 'w') as f:
                    json.dump(config_total, f, indent=4)

                print(f"¡Asociación guardada para {nombre_meta}!")
                print("Retire la tarjeta para continuar...")
                time.sleep(3)
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nSaliendo...")

if __name__ == "__main__":
    main()
