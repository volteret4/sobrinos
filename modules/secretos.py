"""
Cargador de secretos cifrados con SOPS + age.
Fallback a .env si no existe archivo cifrado.
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Dict

PROYECTO_ROOT = Path(__file__).parent.parent
SECRETS_FILE  = PROYECTO_ROOT / "secrets.enc.yaml"
ENV_FILE      = PROYECTO_ROOT / ".env"
# El clave age del usuario está en ~/.config/age/keys.txt (no en el path por defecto de SOPS)
AGE_KEY_FILE  = Path.home() / ".config" / "age" / "keys.txt"


def _env_sops() -> dict:
    """Entorno con SOPS_AGE_KEY_FILE apuntando a la clave del usuario."""
    env = os.environ.copy()
    if AGE_KEY_FILE.exists() and "SOPS_AGE_KEY_FILE" not in env:
        env["SOPS_AGE_KEY_FILE"] = str(AGE_KEY_FILE)
    return env


def desde_sops(archivo: Path = SECRETS_FILE) -> Dict[str, str]:
    """Descifra un archivo SOPS y devuelve sus claves como dict."""
    if not archivo.exists():
        raise FileNotFoundError(
            f"No se encontró '{archivo}'.\n"
            f"Crea secrets.yaml a partir de secrets.yaml.example y ejecúta:\n"
            f"  sops --encrypt secrets.yaml > secrets.enc.yaml && rm secrets.yaml"
        )
    resultado = subprocess.run(
        ["sops", "--decrypt", "--output-type", "json", str(archivo)],
        capture_output=True, text=True, env=_env_sops()
    )
    if resultado.returncode != 0:
        raise RuntimeError(
            f"Error descifrando '{archivo}':\n{resultado.stderr.strip()}"
        )
    return json.loads(resultado.stdout)


def desde_env(archivo: Path = ENV_FILE) -> Dict[str, str]:
    """Lee un archivo .env y devuelve sus claves."""
    secretos: Dict[str, str] = {}
    if not archivo.exists():
        return secretos
    with open(archivo) as f:
        for linea in f:
            linea = linea.strip()
            if linea and not linea.startswith("#") and "=" in linea:
                clave, _, valor = linea.partition("=")
                secretos[clave.strip()] = valor.strip()
    return secretos


def cargar(archivo_sops: Path = SECRETS_FILE) -> Dict[str, str]:
    """
    Carga secretos desde SOPS si existe el archivo cifrado,
    si no usa .env como fallback.
    """
    if archivo_sops.exists():
        return desde_sops(archivo_sops)
    return desde_env()


def cifrar_env(
    env_path: Path = ENV_FILE,
    salida: Path = SECRETS_FILE,
    formato: str = "yaml",
) -> None:
    """
    Migra las claves del .env a un secrets.enc.yaml cifrado con SOPS.
    Util para migrar credenciales existentes.
    """
    secretos = desde_env(env_path)
    if not secretos:
        raise ValueError(f"No se encontraron claves en {env_path}")

    # Escribir YAML temporal sin cifrar
    tmp = salida.with_suffix(".tmp.yaml")
    with open(tmp, "w") as f:
        for clave, valor in secretos.items():
            f.write(f"{clave}: {json.dumps(valor)}\n")

    resultado = subprocess.run(
        ["sops", "--encrypt", str(tmp)],
        capture_output=True, text=True, env=_env_sops()
    )
    tmp.unlink()

    if resultado.returncode != 0:
        raise RuntimeError(f"Error cifrando con SOPS:\n{resultado.stderr.strip()}")

    salida.write_text(resultado.stdout)
    print(f"✓ Secretos cifrados en '{salida}'")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Gestión de secretos con SOPS")
    sub = parser.add_subparsers(dest="cmd")

    # Ver secretos descifrados
    sub.add_parser("ver", help="Muestra los secretos descifrados (solo claves, no valores)")

    # Migrar .env → secrets.enc.yaml
    p_migrar = sub.add_parser("migrar", help="Cifra el .env con SOPS")
    p_migrar.add_argument("--env", default=str(ENV_FILE))
    p_migrar.add_argument("--salida", default=str(SECRETS_FILE))

    args = parser.parse_args()

    if args.cmd == "ver":
        s = cargar()
        print("Claves disponibles:")
        for k in s:
            print(f"  {k}: {'*' * 8}")
    elif args.cmd == "migrar":
        cifrar_env(Path(args.env), Path(args.salida))
    else:
        parser.print_help()
