#!/usr/bin/env python3
"""
Orquestador: portada → web → tarjeta NFC → GitHub
"""

import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent
PY   = sys.executable


def correr(cmd, desc=""):
    """Ejecuta un comando heredando stdin/stdout. Sale si falla."""
    if desc:
        print(f"\n  → {desc}")
    result = subprocess.run([str(c) for c in cmd], cwd=ROOT)
    if result.returncode != 0:
        sys.exit(f"\n[!] Error en: {' '.join(str(c) for c in cmd)}")


def preguntar(prompt, default_si=True):
    marca = "S/n" if default_si else "s/N"
    resp  = input(f"{prompt} [{marca}]: ").strip().lower()
    if not resp:
        return default_si
    return resp in ("s", "si", "sí", "y", "yes")


def paso_musica():
    ruta = input("\n  Ruta al directorio del álbum: ").strip()
    if not ruta or not Path(ruta).is_dir():
        sys.exit("  Ruta no válida.")
    correr([PY, "nfc/nfc_generar_portada.py", ruta], "Generando portadas")
    correr([PY, "album_web_generator.py", ruta],      "Actualizando web de música")


def paso_cine():
    # nfc_tarjetas_cine.py es interactivo y actualiza tarjetas_video_info.json
    correr([PY, "nfc/nfc_tarjetas_cine.py"], "Generando portada de cine")


def paso_nfc():
    correr([PY, "nfc/nfc_config_gen.py"], "Asociando tarjeta NFC")


def paso_git(tipo_str):
    subprocess.run(["git", "add", "docs/", "nfc_playlist.json"], cwd=ROOT)

    msg_default = f"Nueva tarjeta {tipo_str} {date.today().strftime('%Y-%m-%d')}"
    msg = input(f"\n  Mensaje de commit [{msg_default}]: ").strip() or msg_default

    result = subprocess.run(["git", "commit", "-m", msg], cwd=ROOT)
    if result.returncode != 0:
        print("  Nada que commitear.")
        return

    subprocess.run(["git", "push"], cwd=ROOT)
    print("\n  ✓ Web actualizada en GitHub Pages")


def main():
    print("═" * 42)
    print("       SOBRINOS — ORQUESTADOR")
    print("═" * 42)
    print()
    print("  ¿Qué tipo de contenido?")
    print("    1. Música (álbum)")
    print("    2. Cine / Serie")
    tipo = input("\n  → ").strip()

    # ── 1. Portada + web ──────────────────────────────────────────────────────
    print("\n── Paso 1/3: Portada ───────────────────────────────────────────")
    if tipo == "1":
        tipo_str = "álbum"
        paso_musica()
    elif tipo == "2":
        tipo_str = "cine"
        paso_cine()
    else:
        sys.exit("  Opción no válida.")

    # ── 2. Tarjeta NFC (opcional) ─────────────────────────────────────────────
    print("\n── Paso 2/3: Tarjeta NFC ───────────────────────────────────────")
    if preguntar("  ¿Asociar tarjeta NFC ahora?"):
        paso_nfc()
    else:
        print("  Omitido. Ejecuta 'python nfc/nfc_config_gen.py' cuando tengas el lector.")

    # ── 3. GitHub ─────────────────────────────────────────────────────────────
    print("\n── Paso 3/3: GitHub ────────────────────────────────────────────")
    if preguntar("  ¿Subir a GitHub ahora?"):
        paso_git(tipo_str)
    else:
        print("  Omitido. Ejecuta 'git add docs/ && git commit && git push' cuando quieras.")

    print("\n✓ ¡Listo!\n")


if __name__ == "__main__":
    main()
