import json
import subprocess
import threading
import time
import os
import sys
from smartcard.System import readers
from smartcard.util import toHexString

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from reproductores.kodi_api_manager import KodiAPIManager, _kodi_from_env

CONFIG_FILE = "nfc_playlist.json"
FLASK_PORT  = 5000


# ── Lectura de tarjeta ────────────────────────────────────────────────────────

def leer_id_logico(connection):
    """Lee el ID personalizado del bloque 4 (solo Mifare Classic)."""
    try:
        data, sw1, sw2 = connection.transmit([0xFF, 0xB0, 0x00, 0x04, 0x10])
        if sw1 == 0x90:
            return toHexString(data).replace(' ', '')[:8].upper()
    except Exception:
        pass
    return None


def obtener_uid_fisico(connection):
    """UID de fábrica — funciona con Mifare Classic y NTAG."""
    try:
        data, sw1, sw2 = connection.transmit([0xFF, 0xCA, 0x00, 0x00, 0x00])
        if sw1 == 0x90:
            return toHexString(data).replace(' ', '')
    except Exception:
        pass
    return None


# ── Kodi ──────────────────────────────────────────────────────────────────────

def _kodi_con_fallback(config):
    """Intenta sops/env; si no hay host configurado, usa _kodi del JSON."""
    try:
        kodi = _kodi_from_env()
        if kodi.base_url != "http://localhost:8080/jsonrpc":
            return kodi
    except Exception:
        pass
    kodi_cfg = config.get("_kodi", {})
    return KodiAPIManager(
        host=kodi_cfg.get("host", "localhost"),
        port=int(kodi_cfg.get("port", 8080)),
        username=kodi_cfg.get("usuario", ""),
        password=kodi_cfg.get("password", ""),
    )


def ejecutar_accion(entrada, config):
    """Dispara la reproducción según el reproductor y tipo de la entrada."""
    reproductor = entrada.get("reproductor", "")

    if reproductor == "kodi":
        kodi   = _kodi_con_fallback(config)
        tipo   = entrada.get("tipo", "fichero")
        nombre = entrada.get("nombre", "")
        rutas  = entrada.get("rutas") or ([entrada["ruta"]] if entrada.get("ruta") else [])

        if not rutas:
            print(f"  ✗ '{nombre}' no tiene ruta (tarjeta antigua con kodi_id): vuelve a asociarla")
            return False, nombre

        print(f"  → Kodi {kodi.base_url} | tipo={tipo} ruta={rutas[0]}")

        if tipo == "serie":
            exito = kodi.play_next_episode_by_path(rutas[0])
        elif tipo in ("album", "artista"):
            exito = kodi.play_music_paths(rutas)
        else:  # pelicula, fichero
            exito = kodi.play_file(rutas[0])

        print(f"  {'✓ OK' if exito else '✗ Error'}: {nombre}")
        return exito, nombre

    else:
        subprocess.Popen(" ".join(entrada["comando"]), shell=True)
        return True, entrada.get("nombre", "")


def cargar_config():
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)


# ── Servidor HTTP (para Android / NTAG) ──────────────────────────────────────

def _html_respuesta(nombre, exito=True):
    color  = "#16a34a" if exito else "#dc2626"
    icono  = "▶" if exito else "✗"
    estado = "Reproduciendo en Kodi..." if exito else "Error al reproducir"
    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{nombre}</title>
  <style>
    body {{
      font-family: -apple-system, sans-serif;
      background: #0f172a;
      color: #f8fafc;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      margin: 0;
      text-align: center;
      padding: 2rem;
    }}
    .card {{
      background: #1e293b;
      border-radius: 1.5rem;
      padding: 3rem 2rem;
      max-width: 360px;
      width: 100%;
      box-shadow: 0 25px 50px rgba(0,0,0,.5);
    }}
    .icono {{ font-size: 4rem; color: {color}; margin-bottom: 1rem; }}
    h1 {{ font-size: 1.5rem; margin: 0 0 .5rem; }}
    p  {{ color: #94a3b8; margin: 0; font-size: .9rem; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="icono">{icono}</div>
    <h1>{nombre}</h1>
    <p>{estado}</p>
  </div>
</body>
</html>"""


def iniciar_servidor_http():
    """Arranca Flask en un hilo daemon para recibir peticiones de Android."""
    try:
        from flask import Flask, Response
    except ImportError:
        print("[HTTP] Flask no instalado — servidor Android desactivado.")
        print("       Instala con: pip install flask")
        return

    app = Flask(__name__)
    app.logger.disabled = True

    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)

    @app.route("/play/<uid>")
    def play(uid):
        uid = uid.strip().upper()
        try:
            config  = cargar_config()
            entrada = config.get(uid)
            if not entrada:
                html = _html_respuesta(f"Tarjeta desconocida: {uid}", exito=False)
                return Response(html, status=404, mimetype="text/html")
            print(f"[HTTP] Tarjeta reconocida: {entrada.get('nombre')} (uid={uid})")
            exito, nombre = ejecutar_accion(entrada, config)
            return Response(_html_respuesta(nombre, exito), mimetype="text/html")
        except Exception as e:
            return Response(_html_respuesta(str(e), exito=False), status=500, mimetype="text/html")

    @app.route("/api/status")
    def status():
        from flask import jsonify
        try:
            config = cargar_config()
            kodi   = _kodi_con_fallback(config)
            return jsonify(kodi.get_player_status())
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/")
    def index():
        try:
            config = cargar_config()
            kodi   = _kodi_con_fallback(config)
            estado = kodi.get_status_summary()
        except Exception:
            estado = "Sin conexión con Kodi"
        html = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sobrinos</title>
<style>body{{font-family:-apple-system,sans-serif;background:#0f172a;color:#f8fafc;
  padding:2rem;max-width:480px;margin:auto}}</style></head>
<body><h1>📦 Sobrinos</h1><pre style="color:#94a3b8">{estado}</pre>
<p style="color:#64748b;font-size:.85rem">Acerca una tarjeta NTAG al móvil para reproducir.</p>
</body></html>"""
        return html

    hilo = threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=FLASK_PORT, debug=False, use_reloader=False),
        daemon=True,
        name="http-android",
    )
    hilo.start()
    print(f"[HTTP] Servidor Android escuchando en :{FLASK_PORT}")


# ── Bucle NFC principal ───────────────────────────────────────────────────────

def monitorear():
    reader_list = readers()
    if not reader_list:
        print("No se encontró lector NFC.")
        return
    reader = reader_list[0]
    ultima_tarjeta, tiempo_ultima = None, 0

    print(">>> Lector NFC activo <<<")

    while True:
        try:
            connection = reader.createConnection()
            connection.connect()

            config = cargar_config()

            # Mifare Classic: probar ID lógico (bloque 4) primero
            id_detectado = leer_id_logico(connection)
            if not id_detectado or id_detectado not in config:
                id_detectado = obtener_uid_fisico(connection)

            ahora = time.time()
            if id_detectado and (id_detectado != ultima_tarjeta or ahora - tiempo_ultima > 4):
                if id_detectado in config:
                    entrada = config[id_detectado]
                    print(f"Tarjeta: {entrada['nombre']} [{entrada.get('reproductor','?')}]")
                    ejecutar_accion(entrada, config)
                else:
                    print(f"ID desconocido: {id_detectado}")
                ultima_tarjeta, tiempo_ultima = id_detectado, ahora

            connection.disconnect()

        except Exception as e:
            err = str(e)
            ignorar = ("No card", "removeCard", "No smart card", "no card")
            if not any(x in err for x in ignorar):
                print(f"  [!] {err}")

        time.sleep(0.5)


if __name__ == "__main__":
    iniciar_servidor_http()
    monitorear()
