#!/usr/bin/env python3
"""
Enriquece las tarjetas de cine con datos de la API de TMDB.

Añade a cada entrada de tarjetas_video_info.json:
  sinopsis, géneros, rating, reparto, director, poster HD, enlace TMDB...

Uso:
  python tmdb_enriquecer.py                          # Procesa todas las entradas sin datos TMDB
  python tmdb_enriquecer.py --titulo "El Rey León"   # Solo ese título
  python tmdb_enriquecer.py --forzar                 # Vuelve a buscar aunque ya haya datos TMDB
  python tmdb_enriquecer.py --secretos mi_sops.yaml  # Archivo SOPS alternativo
"""

import argparse
import json
import logging
import sys
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

sys.path.insert(0, str(Path(__file__).parent))
from modules.secretos import cargar as cargar_secretos

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

TMDB_BASE    = "https://api.themoviedb.org/3"


def normalizar_busqueda(texto: str) -> str:
    """Elimina acentos para búsquedas más robustas en la API."""
    sin_acentos = unicodedata.normalize("NFD", texto).encode("ascii", "ignore").decode()
    return sin_acentos.strip()
TMDB_IMG_W5  = "https://image.tmdb.org/t/p/w500"
TMDB_IMG_W13 = "https://image.tmdb.org/t/p/w1280"
JSON_CINE    = Path("docs/cine/tarjetas_video_info.json")


# ─────────────────────────────────────────────
#  Cliente TMDB
# ─────────────────────────────────────────────

class TmdbClient:
    """Cliente minimalista para la API v3 de TMDB."""

    def __init__(self, api_key: str = "", token: str = ""):
        if token:
            headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
            self._base_params: Dict[str, str] = {"language": "es-ES"}
        elif api_key:
            headers = {"Accept": "application/json"}
            self._base_params = {"api_key": api_key, "language": "es-ES"}
        else:
            raise ValueError(
                "Se necesita TMDB_TOKEN (Bearer) o TMDB_API_KEY en los secretos."
            )
        self._session = requests.Session()
        self._session.headers.update(headers)

    def _get(self, endpoint: str, **params) -> Dict:
        url = f"{TMDB_BASE}/{endpoint.lstrip('/')}"
        resp = self._session.get(url, params={**self._base_params, **params}, timeout=10)
        if resp.status_code == 401:
            raise requests.HTTPError(
                "401 No autorizado. Comprueba que TMDB_TOKEN o TMDB_API_KEY son correctos "
                "en secrets.enc.yaml (o .env). Obtén tus credenciales en "
                "https://www.themoviedb.org/settings/api",
                response=resp,
            )
        resp.raise_for_status()
        return resp.json()

    def buscar_pelicula(self, titulo: str) -> List[Dict]:
        return self._get("search/movie", query=titulo).get("results", [])

    def buscar_serie(self, titulo: str) -> List[Dict]:
        return self._get("search/tv", query=titulo).get("results", [])

    def detalles_pelicula(self, tmdb_id: int) -> Dict:
        return self._get(f"movie/{tmdb_id}", append_to_response="credits")

    def detalles_serie(self, tmdb_id: int) -> Dict:
        return self._get(f"tv/{tmdb_id}", append_to_response="credits")


# ─────────────────────────────────────────────
#  Selección interactiva
# ─────────────────────────────────────────────

def _titulo_resultado(r: Dict, tipo: str) -> tuple[str, str]:
    """Devuelve (título, año) de un resultado según tipo."""
    if tipo == "movie":
        return r.get("title", "?"), (r.get("release_date") or "")[:4]
    return r.get("name", "?"), (r.get("first_air_date") or "")[:4]


def seleccionar(resultados: List[Dict], tipo: str) -> Optional[Dict]:
    """Muestra resultados y pide confirmación. Devuelve el elegido o None."""
    if not resultados:
        logger.warning("  Sin resultados en TMDB.")
        return None
    if len(resultados) == 1:
        titulo, año = _titulo_resultado(resultados[0], tipo)
        confirmar = input(f"  ¿Es '{titulo} ({año})'? (y/n) [y]: ").strip().lower()
        return resultados[0] if confirmar != "n" else None

    print(f"\n  Resultados encontrados ({tipo}):")
    for i, r in enumerate(resultados[:8]):
        titulo, año = _titulo_resultado(r, tipo)
        overview = (r.get("overview") or "Sin descripción")[:70]
        print(f"  [{i+1}] {titulo} ({año}) — {overview}…")
    print("  [0] Saltar")

    while True:
        try:
            sel = int(input("  Selección: ").strip())
            if sel == 0:
                return None
            if 1 <= sel <= min(len(resultados), 8):
                return resultados[sel - 1]
        except (ValueError, KeyboardInterrupt):
            return None


# ─────────────────────────────────────────────
#  Extracción de datos
# ─────────────────────────────────────────────

def extraer(detalles: Dict, tipo: str) -> Dict[str, Any]:
    """Transforma la respuesta de TMDB en los campos que guardamos."""
    datos: Dict[str, Any] = {}

    tmdb_id = detalles.get("id")
    datos["tmdb_id"]  = tmdb_id
    datos["tmdb_url"] = (
        f"https://www.themoviedb.org/{'movie' if tipo == 'movie' else 'tv'}/{tmdb_id}"
    )
    datos["tmdb_rating"] = round(detalles.get("vote_average") or 0, 1)
    datos["tmdb_votos"]  = detalles.get("vote_count", 0)
    datos["sinopsis"]    = detalles.get("overview", "")
    datos["generos"]     = [g["name"] for g in detalles.get("genres", [])]

    poster = detalles.get("poster_path")
    if poster:
        datos["tmdb_poster"]   = f"{TMDB_IMG_W5}{poster}"
        datos["tmdb_poster_hd"] = f"{TMDB_IMG_W13}{poster}"

    backdrop = detalles.get("backdrop_path")
    if backdrop:
        datos["tmdb_backdrop"] = f"{TMDB_IMG_W13}{backdrop}"

    credits = detalles.get("credits", {})
    cast = [p["name"] for p in credits.get("cast", [])[:6]]
    if cast:
        datos["reparto"] = cast

    estudios = [c["name"] for c in detalles.get("production_companies", [])]
    if estudios:
        datos["estudios"] = estudios

    if tipo == "movie":
        datos["tmdb_titulo"] = detalles.get("title", "")
        año_tmdb             = (detalles.get("release_date") or "")[:4]
        datos["tmdb_año"]    = año_tmdb
        datos["year"]        = año_tmdb          # corrige el año introducido manualmente
        datos["duracion_min"] = detalles.get("runtime")
        director = next(
            (p["name"] for p in credits.get("crew", []) if p.get("job") == "Director"),
            None,
        )
        if director:
            datos["director"] = director
    else:
        datos["tmdb_titulo"]  = detalles.get("name", "")
        año_tmdb              = (detalles.get("first_air_date") or "")[:4]
        datos["tmdb_año"]     = año_tmdb
        datos["year"]         = año_tmdb          # corrige el año introducido manualmente
        datos["temporadas"]   = detalles.get("number_of_seasons")
        datos["episodios"]    = detalles.get("number_of_episodes")

    return datos


# ─────────────────────────────────────────────
#  Lógica principal por entrada
# ─────────────────────────────────────────────

def enriquecer_entrada(
    entrada: Dict, cliente: TmdbClient, forzar: bool = False
) -> Dict:
    titulo = entrada.get("title", "")
    tipo   = "movie" if entrada.get("type") != "series" else "series"

    if not forzar and "tmdb_id" in entrada:
        logger.info(f"'{titulo}' ya tiene datos TMDB. Usa --forzar para actualizar.")
        return entrada

    query = normalizar_busqueda(titulo)
    print(f"\n{'─' * 52}")
    print(f"  Buscando: '{query}' [{tipo}]")

    try:
        resultados = (
            cliente.buscar_pelicula(query)
            if tipo == "movie"
            else cliente.buscar_serie(query)
        )
    except requests.RequestException as e:
        logger.error(f"  Error de red buscando '{titulo}': {e}")
        return entrada

    elegido = seleccionar(resultados, tipo)
    if not elegido:
        logger.info(f"  Saltando '{titulo}'.")
        return entrada

    tmdb_id = elegido["id"]
    try:
        detalles = (
            cliente.detalles_pelicula(tmdb_id)
            if tipo == "movie"
            else cliente.detalles_serie(tmdb_id)
        )
    except requests.RequestException as e:
        logger.error(f"  Error obteniendo detalles de id={tmdb_id}: {e}")
        return entrada

    entrada.update(extraer(detalles, tipo))
    logger.info(f"  ✓ Enriquecido: {entrada.get('tmdb_titulo')} (id={tmdb_id})")
    return entrada


# ─────────────────────────────────────────────
#  CLI
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Enriquece tarjetas de cine con datos de TMDB"
    )
    parser.add_argument(
        "--titulo", help="Enriquece solo las entradas cuyo título contenga este texto"
    )
    parser.add_argument(
        "--json", default=str(JSON_CINE), help=f"JSON de tarjetas (por defecto: {JSON_CINE})"
    )
    parser.add_argument(
        "--forzar", action="store_true", help="Vuelve a buscar aunque ya haya datos TMDB"
    )
    parser.add_argument(
        "--secretos", default="secrets.enc.yaml", help="Archivo SOPS de secretos"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Modo detallado"
    )
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # ── Credenciales ──
    try:
        secretos = cargar_secretos(Path(args.secretos))
    except Exception as e:
        logger.error(f"No se pudieron cargar los secretos:\n  {e}")
        sys.exit(1)

    api_key = secretos.get("TMDB_API_KEY", "")
    token   = secretos.get("TMDB_TOKEN", "")

    if not api_key and not token:
        logger.error(
            "Faltan credenciales TMDB en los secretos.\n"
            "Añade TMDB_TOKEN (Bearer) o TMDB_API_KEY a secrets.enc.yaml."
        )
        sys.exit(1)

    try:
        cliente = TmdbClient(api_key=api_key, token=token)
    except ValueError as e:
        logger.error(e)
        sys.exit(1)

    # ── Cargar JSON ──
    json_path = Path(args.json)
    if not json_path.exists():
        logger.error(f"No se encontró '{json_path}'")
        sys.exit(1)

    with open(json_path, encoding="utf-8") as f:
        tarjetas: List[Dict] = json.load(f)

    # ── Filtrar si se especificó título ──
    if args.titulo:
        busqueda = args.titulo.lower()
        indices = [
            i for i, t in enumerate(tarjetas)
            if busqueda in t.get("title", "").lower()
        ]
        if not indices:
            logger.error(f"No se encontró '{args.titulo}' en {json_path}")
            sys.exit(1)
        for i in indices:
            tarjetas[i] = enriquecer_entrada(tarjetas[i], cliente, args.forzar)
    else:
        for i, entrada in enumerate(tarjetas):
            tarjetas[i] = enriquecer_entrada(entrada, cliente, args.forzar)

    # ── Guardar ──
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(tarjetas, f, indent=2, ensure_ascii=False)

    logger.info(f"\n✓ Guardado en '{json_path}'")


if __name__ == "__main__":
    main()
