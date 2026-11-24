#!/usr/bin/env python3
"""
Generador de Tarjetas de Álbumes
Crea dos imágenes verticales de 52x82mm para tarjetas de álbumes musicales.

Cara A: Portada del disco + información del álbum
Cara B: Lista de pistas

Requisitos:
- mutagen: para leer tags de archivos de música
- Pillow: para generar imágenes
- musicbrainzngs: para buscar información en MusicBrainz
- requests: para descargar portadas
"""

import io
import os
import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote, urlparse
import logging
import colorsys
from collections import Counter

try:
    from mutagen import File
    from mutagen.id3 import ID3NoHeaderError
except ImportError:
    print("Error: mutagen no está instalado. Instala con: pip install mutagen")
    sys.exit(1)

try:
    from PIL import Image, ImageDraw, ImageFont
    from PIL.ImageColor import getrgb
    import PIL.ImageStat as ImageStat
except ImportError:
    print("Error: Pillow no está instalado. Instala con: pip install Pillow")
    sys.exit(1)

try:
    import musicbrainzngs
    # Silenciar los warnings innecesarios de musicbrainzngs
    musicbrainzngs.set_useragent("AlbumCardGenerator", "1.0", "https://github.com/example/album-card-generator")

    # Configurar logging de musicbrainzngs para que no muestre warnings menores
    musicbrainz_logger = logging.getLogger('musicbrainzngs.musicbrainz')
    musicbrainz_logger.setLevel(logging.WARNING)

except ImportError:
    print("Error: musicbrainzngs no está instalado. Instala con: pip install musicbrainzngs")
    sys.exit(1)

try:
    import requests
    # Silenciar warnings de requests
    requests.packages.urllib3.disable_warnings()
    requests_logger = logging.getLogger('urllib3')
    requests_logger.setLevel(logging.WARNING)
except ImportError:
    print("Error: requests no está instalado. Instala con: pip install requests")
    sys.exit(1)

try:
    import qrcode
    from qrcode.image.styledpil import StyledPilImage
    from qrcode.image.styles.moduledrawers import RoundedModuleDrawer
except ImportError:
    print("Error: qrcode no está instalado. Instala con: pip install qrcode[pil]")
    sys.exit(1)


# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constantes de diseño (en píxeles a 300 DPI)
DPI = 300
CARD_WIDTH_MM = 52
CARD_HEIGHT_MM = 82
COVER_SIZE_MM = 51
TEXT_AREA_HEIGHT_MM = 30

# Conversión de mm a píxeles
CARD_WIDTH = int(CARD_WIDTH_MM * DPI / 25.4)  # ~613 px
CARD_HEIGHT = int(CARD_HEIGHT_MM * DPI / 25.4)  # ~969 px
COVER_SIZE = int(COVER_SIZE_MM * DPI / 25.4)  # ~601 px
TEXT_AREA_HEIGHT = int(TEXT_AREA_HEIGHT_MM * DPI / 25.4)  # ~354 px

GITHUB_PAGES_BASE = "https://volteret4.github.io/sobrinos"

# Colores
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY_LIGHT = (230, 230, 230)
GRAY_DARK = (80, 80, 80)


class ColorAnalyzer:
    """Analizador de colores para extraer paletas de imágenes"""

    @staticmethod
    def extract_dominant_color(image: Image.Image) -> Tuple[int, int, int]:
        """Extrae el color dominante de una imagen"""
        try:
            # Redimensionar para análisis más rápido
            img = image.copy()
            img = img.resize((150, 150), Image.Resampling.LANCZOS)
            img = img.convert('RGB')

            # Método 1: Color más común
            pixels = list(img.getdata())

            # Agrupar colores similares (reducir ruido)
            grouped_colors = []
            for r, g, b in pixels:
                # Reducir precisión para agrupar colores similares
                r = (r // 10) * 10
                g = (g // 10) * 10
                b = (b // 10) * 10
                grouped_colors.append((r, g, b))

            # Contar frecuencias
            color_counter = Counter(grouped_colors)

            # Filtrar colores muy oscuros o muy claros (probablemente bordes)
            filtered_colors = []
            for color, count in color_counter.most_common(20):
                r, g, b = color
                brightness = (r + g + b) / 3
                # Evitar negro puro, blanco puro y grises muy extremos
                if 20 < brightness < 235:
                    # Evitar colores muy desaturados (grises)
                    max_val = max(r, g, b)
                    min_val = min(r, g, b)
                    saturation = (max_val - min_val) / max_val if max_val > 0 else 0

                    if saturation > 0.1 or brightness < 100:  # Permitir colores oscuros aunque sean desaturados
                        filtered_colors.append((color, count))

            if filtered_colors:
                dominant_color = filtered_colors[0][0]
            else:
                # Fallback: usar estadísticas de imagen
                stat = ImageStat.Stat(img)
                dominant_color = tuple(int(c) for c in stat.mean)

            return dominant_color

        except Exception as e:
            logger.warning(f"Error extrayendo color dominante: {e}")
            return (80, 80, 80)  # Gris oscuro como fallback

    @staticmethod
    def get_contrast_color(bg_color: Tuple[int, int, int]) -> Tuple[int, int, int]:
        """Obtiene un color de texto que contraste bien con el fondo"""
        r, g, b = bg_color

        # Calcular luminancia (brillo percibido)
        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255

        if luminance > 0.5:
            # Fondo claro -> texto oscuro
            return (40, 40, 40)
        else:
            # Fondo oscuro -> texto claro
            return (240, 240, 240)

    @staticmethod
    def get_secondary_color(bg_color: Tuple[int, int, int]) -> Tuple[int, int, int]:
        """Obtiene un color secundario para texto menos importante"""
        primary = ColorAnalyzer.get_contrast_color(bg_color)
        r, g, b = primary

        # Hacer el color secundario un poco más sutil
        if sum(primary) > 400:  # Color claro
            return (max(0, r - 60), max(0, g - 60), max(0, b - 60))
        else:  # Color oscuro
            return (min(255, r + 60), min(255, g + 60), min(255, b + 60))

    @staticmethod
    def get_border_color(bg_color: Tuple[int, int, int]) -> Tuple[int, int, int]:
        """Obtiene un color sutil para bordes"""
        r, g, b = bg_color

        # Calcular luminancia
        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255

        if luminance > 0.5:
            # Fondo claro -> borde más oscuro
            factor = 0.8
        else:
            # Fondo oscuro -> borde más claro
            factor = 1.2

        new_r = min(255, max(0, int(r * factor)))
        new_g = min(255, max(0, int(g * factor)))
        new_b = min(255, max(0, int(b * factor)))

        return (new_r, new_g, new_b)

    @staticmethod
    def enhance_color(color: Tuple[int, int, int], saturation_boost: float = 1.2) -> Tuple[int, int, int]:
        """Realza un color aumentando su saturación"""
        r, g, b = [c / 255.0 for c in color]

        # Convertir a HSV
        h, s, v = colorsys.rgb_to_hsv(r, g, b)

        # Aumentar saturación
        s = min(1.0, s * saturation_boost)

        # Convertir de vuelta a RGB
        r, g, b = colorsys.hsv_to_rgb(h, s, v)

        return (int(r * 255), int(g * 255), int(b * 255))


class AlbumInfo:
    """Clase para almacenar información del álbum"""
    def __init__(self):
        self.artist = ""
        self.album = ""
        self.date = ""
        self.label = ""
        self.genres = []
        self.tracks = []
        self.mbid = ""
        self.artist_mbid = ""  # Nuevo campo para MBID del artista
        self.cover_art_url = ""
        self.cover_image = None
        self.color_palette = {
            'background': (255, 255, 255),
            'text_primary': (0, 0, 0),
            'text_secondary': (80, 80, 80),
            'border': (230, 230, 230)
        }
        self.qr_links = {
            'wikipedia_artist': "",
            'genius_album': ""
        }


class QRLinkGenerator:
    """Generador de enlaces para códigos QR"""

    @staticmethod
    def get_wikipedia_from_musicbrainz(artist_mbid: str) -> Optional[str]:
        """Obtiene el enlace de Wikipedia desde Wikidata a través de MusicBrainz"""
        try:
            logger.info(f"Buscando Wikipedia en MusicBrainz para MBID: {artist_mbid}")

            # Obtener información del artista desde MusicBrainz incluyendo Wikidata
            result = musicbrainzngs.get_artist_by_id(artist_mbid, includes=['url-rels'])

            if 'artist' not in result:
                return None

            artist = result['artist']

            # Buscar relaciones de URL, especialmente Wikidata
            wikidata_url = None
            wikipedia_urls = {}

            if 'url-relation-list' in artist:
                for url_rel in artist['url-relation-list']:
                    url = url_rel.get('target', '')
                    rel_type = url_rel.get('type', '')

                    # Enlace directo a Wikipedia
                    if 'wikipedia.org' in url:
                        if '/es.wikipedia.org/' in url:
                            wikipedia_urls['es'] = url
                        elif '/en.wikipedia.org/' in url:
                            wikipedia_urls['en'] = url
                        else:
                            # Otros idiomas
                            lang = url.split('.')[0].split('//')[-1]
                            wikipedia_urls[lang] = url

                    # Enlace de Wikidata
                    elif 'wikidata.org' in url and rel_type == 'wikidata':
                        wikidata_url = url

            # Preferir enlaces directos de Wikipedia (español > inglés > otros)
            if 'es' in wikipedia_urls:
                logger.info(f"Encontrada Wikipedia directa en español: {wikipedia_urls['es']}")
                return wikipedia_urls['es']
            elif 'en' in wikipedia_urls:
                logger.info(f"Encontrada Wikipedia directa en inglés: {wikipedia_urls['en']}")
                return wikipedia_urls['en']
            elif wikipedia_urls:
                # Tomar el primer idioma disponible
                first_lang = next(iter(wikipedia_urls))
                logger.info(f"Encontrada Wikipedia en {first_lang}: {wikipedia_urls[first_lang]}")
                return wikipedia_urls[first_lang]

            # Si no hay enlaces directos pero hay Wikidata, intentar obtener Wikipedia desde ahí
            if wikidata_url:
                wiki_from_wikidata = QRLinkGenerator._get_wikipedia_from_wikidata(wikidata_url)
                if wiki_from_wikidata:
                    return wiki_from_wikidata

        except Exception as e:
            logger.warning(f"Error obteniendo Wikipedia desde MusicBrainz: {e}")

        return None

    @staticmethod
    def _get_wikipedia_from_wikidata(wikidata_url: str) -> Optional[str]:
        """Obtiene enlaces de Wikipedia desde Wikidata"""
        try:
            # Extraer Q-ID de Wikidata
            qid = wikidata_url.split('/')[-1]
            if not qid.startswith('Q'):
                return None

            logger.info(f"Consultando Wikidata para {qid}")

            # Consulta SPARQL a Wikidata para obtener enlaces de Wikipedia
            sparql_query = f"""
            SELECT ?article ?lang WHERE {{
              ?article schema:about wd:{qid} ;
                       schema:inLanguage ?lang ;
                       schema:isPartOf ?wiki .
              ?wiki wikibase:wikiGroup "wikipedia" .
              FILTER(?lang IN ("es", "en"))
            }}
            ORDER BY DESC(?lang = "es")
            LIMIT 2
            """

            # Hacer petición a Wikidata
            sparql_endpoint = "https://query.wikidata.org/sparql"
            headers = {
                'User-Agent': 'AlbumCardGenerator/1.0',
                'Accept': 'application/json'
            }

            response = requests.get(
                sparql_endpoint,
                params={'query': sparql_query, 'format': 'json'},
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                results = data.get('results', {}).get('bindings', [])

                for result in results:
                    url = result.get('article', {}).get('value', '')
                    lang = result.get('lang', {}).get('value', '')

                    if url and lang:
                        logger.info(f"Encontrada Wikipedia desde Wikidata ({lang}): {url}")
                        return url

        except Exception as e:
            logger.warning(f"Error consultando Wikidata: {e}")

        return None

    @staticmethod
    def search_wikipedia_artist(artist_name: str, artist_mbid: str = None) -> Optional[str]:
        """Busca el enlace de Wikipedia del artista"""
        try:
            logger.info(f"Buscando Wikipedia para: {artist_name}")

            # Primero intentar con MusicBrainz/Wikidata si tenemos MBID
            if artist_mbid:
                mb_wikipedia = QRLinkGenerator.get_wikipedia_from_musicbrainz(artist_mbid)
                if mb_wikipedia:
                    return mb_wikipedia

            # Método de respaldo: búsqueda directa por nombre
            logger.info("Intentando búsqueda directa por nombre del artista")

            # Limpiar nombre del artista para búsqueda
            clean_artist = artist_name.replace(" ", "_").replace("&", "and")

            # URL directa de Wikipedia en español
            wiki_url_es = f"https://es.wikipedia.org/wiki/{clean_artist}"

            # Verificar si existe la página en español
            response = requests.head(wiki_url_es, timeout=5)
            if response.status_code == 200:
                logger.info(f"Encontrada Wikipedia en español: {wiki_url_es}")
                return wiki_url_es

            # Si no existe en español, probar en inglés
            wiki_url_en = f"https://en.wikipedia.org/wiki/{clean_artist}"
            response = requests.head(wiki_url_en, timeout=5)
            if response.status_code == 200:
                logger.info(f"Encontrada Wikipedia en inglés: {wiki_url_en}")
                return wiki_url_en

            # Buscar usando la API de Wikipedia
            search_url = "https://es.wikipedia.org/api/rest_v1/page/title"
            params = {
                'q': artist_name,
                'limit': 1
            }

            response = requests.get(search_url, params=params, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('pages'):
                    page_title = data['pages'][0]['title']
                    wiki_url = f"https://es.wikipedia.org/wiki/{page_title.replace(' ', '_')}"
                    logger.info(f"Encontrada Wikipedia por búsqueda: {wiki_url}")
                    return wiki_url

        except Exception as e:
            logger.warning(f"Error buscando Wikipedia para {artist_name}: {e}")

        return None

    @staticmethod
    def search_genius_album(artist_name: str, album_name: str) -> Optional[str]:
        """Busca el enlace de Genius del álbum"""
        try:
            logger.info(f"Buscando Genius para: {artist_name} - {album_name}")

            # Limpiar nombres para URL
            clean_artist = artist_name.lower().replace(" ", "-").replace("&", "and")
            clean_album = album_name.lower().replace(" ", "-").replace("&", "and")

            # Remover caracteres especiales
            import re
            clean_artist = re.sub(r'[^\w\-]', '', clean_artist)
            clean_album = re.sub(r'[^\w\-]', '', clean_album)

            # URL típica de Genius para álbumes
            genius_url = f"https://genius.com/albums/{clean_artist}/{clean_album}"

            # Verificar si existe la página
            try:
                response = requests.head(genius_url, timeout=5, allow_redirects=True)
                if response.status_code == 200:
                    logger.info(f"Encontrado Genius: {genius_url}")
                    return genius_url
            except:
                pass

            # Formato alternativo
            genius_url_alt = f"https://genius.com/{clean_artist}-{clean_album}-album"
            try:
                response = requests.head(genius_url_alt, timeout=5, allow_redirects=True)
                if response.status_code == 200:
                    logger.info(f"Encontrado Genius (formato alternativo): {genius_url_alt}")
                    return genius_url_alt
            except:
                pass

            # Si no se encuentra, generar URL de búsqueda
            search_query = f"{artist_name} {album_name}".replace(" ", "%20")
            search_url = f"https://genius.com/search?q={search_query}"
            logger.info(f"Generando URL de búsqueda Genius: {search_url}")
            return search_url

        except Exception as e:
            logger.warning(f"Error buscando Genius para {artist_name} - {album_name}: {e}")

        return None

    @staticmethod
    def generate_qr_links(album_info: AlbumInfo):
        """Genera los enlaces para los códigos QR"""
        try:
            # Buscar Wikipedia del artista (usando MBID si está disponible)
            if album_info.artist:
                wikipedia_link = QRLinkGenerator.search_wikipedia_artist(
                    album_info.artist,
                    album_info.artist_mbid
                )
                if wikipedia_link:
                    album_info.qr_links['wikipedia_artist'] = wikipedia_link

            # Buscar Genius del álbum
            if album_info.artist and album_info.album:
                genius_link = QRLinkGenerator.search_genius_album(album_info.artist, album_info.album)
                if genius_link:
                    album_info.qr_links['genius_album'] = genius_link

        except Exception as e:
            logger.warning(f"Error generando enlaces QR: {e}")


class QRCodeGenerator:
    """Generador de códigos QR"""

    @staticmethod
    def create_qr_code(url: str, size: int = 120, bg_color: Tuple[int, int, int] = (255, 255, 255),
                      fg_color: Tuple[int, int, int] = (0, 0, 0)) -> Optional[Image.Image]:
        """Crea un código QR con los colores especificados y máximo contraste"""
        try:
            # Optimizar colores para máximo contraste
            optimized_bg, optimized_fg = QRCodeGenerator._optimize_qr_colors(bg_color, fg_color)

            # Configurar QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=4,  # Aumentado para mejor definición
                border=1,
            )

            qr.add_data(url)
            qr.make(fit=True)

            # Crear imagen del QR
            qr_img = qr.make_image(
                fill_color=optimized_fg,
                back_color=optimized_bg,
                image_factory=StyledPilImage,
                module_drawer=RoundedModuleDrawer()
            )

            # Redimensionar al tamaño deseado
            qr_img = qr_img.resize((size, size), Image.Resampling.LANCZOS)

            return qr_img

        except Exception as e:
            logger.warning(f"Error creando código QR para {url}: {e}")
            return None

    @staticmethod
    def _optimize_qr_colors(bg_color: Tuple[int, int, int], fg_color: Tuple[int, int, int]) -> Tuple[Tuple[int, int, int], Tuple[int, int, int]]:
        """Optimiza los colores del QR para máximo contraste"""
        # Calcular luminancia del fondo
        bg_luminance = (0.299 * bg_color[0] + 0.587 * bg_color[1] + 0.114 * bg_color[2]) / 255

        # Si el fondo es muy claro, asegurar QR oscuro
        if bg_luminance > 0.6:
            # Fondo claro -> QR muy oscuro para máximo contraste
            optimized_fg = (20, 20, 20)  # Casi negro
            optimized_bg = bg_color

        # Si el fondo es muy oscuro, asegurar QR claro
        elif bg_luminance < 0.4:
            # Fondo oscuro -> QR muy claro para máximo contraste
            optimized_fg = (240, 240, 240)  # Casi blanco
            optimized_bg = bg_color

        # Para fondos intermedios, usar colores dados pero ajustados
        else:
            # Ajustar para garantizar contraste mínimo
            if bg_luminance > 0.5:
                optimized_fg = (30, 30, 30)  # Oscuro
            else:
                optimized_fg = (225, 225, 225)  # Claro
            optimized_bg = bg_color

        return optimized_bg, optimized_fg


class MusicFileProcessor:
    """Procesador de archivos de música"""

    def __init__(self, folder_path: str):
        self.folder_path = Path(folder_path)
        self.supported_formats = {'.mp3', '.flac', '.ogg', '.mp4', '.m4a', '.wv', '.dsf'}

    def get_audio_files(self) -> List[Path]:
        """Obtiene todos los archivos de audio de la carpeta"""
        audio_files = []
        for file_path in self.folder_path.rglob('*'):
            if file_path.suffix.lower() in self.supported_formats:
                audio_files.append(file_path)

        # Ordenar por nombre de archivo
        audio_files.sort()
        return audio_files

    def extract_album_info(self, audio_files: List[Path]) -> AlbumInfo:
        """Extrae información del álbum desde los archivos de audio"""
        album_info = AlbumInfo()

        if not audio_files:
            raise ValueError("No se encontraron archivos de audio")

        # Procesar el primer archivo para obtener información general del álbum
        first_file = audio_files[0]
        try:
            audio_file = File(first_file)
            if audio_file is None:
                raise ValueError(f"No se pudo leer el archivo: {first_file}")

            # Extraer información básica
            album_info.artist = self._get_tag(audio_file, 'artist', 'albumartist', 'TPE1', 'TPE2')
            album_info.album = self._get_tag(audio_file, 'album', 'TALB')
            album_info.date = self._get_tag(audio_file, 'date', 'year', 'TDRC')
            album_info.label = self._get_tag(audio_file, 'label', 'publisher', 'TPUB')

            # Géneros
            genre_tag = self._get_tag(audio_file, 'genre', 'TCON')
            if genre_tag:
                album_info.genres = [g.strip() for g in genre_tag.split(',')]

            # MBID
            album_info.mbid = self._get_tag(audio_file, 'musicbrainz_albumid', 'TXXX:MusicBrainz Album Id')

            # MBID del artista
            album_info.artist_mbid = self._get_tag(audio_file, 'musicbrainz_artistid', 'TXXX:MusicBrainz Artist Id')

        except Exception as e:
            logger.warning(f"Error procesando {first_file}: {e}")

        # Procesar todas las pistas
        for file_path in audio_files:
            try:
                audio_file = File(file_path)
                if audio_file is None:
                    continue

                track_number = self._get_tag(audio_file, 'tracknumber', 'track', 'TRCK')
                title = self._get_tag(audio_file, 'title', 'TIT2')

                # Limpiar número de pista (remover "1/10" -> "1")
                if track_number and '/' in track_number:
                    track_number = track_number.split('/')[0]

                track_info = {
                    'number': int(track_number) if track_number and track_number.isdigit() else len(album_info.tracks) + 1,
                    'title': title or file_path.stem,
                    'file': file_path
                }
                album_info.tracks.append(track_info)

            except Exception as e:
                logger.warning(f"Error procesando pista {file_path}: {e}")

        # Ordenar pistas por número
        album_info.tracks.sort(key=lambda x: x['number'])

        return album_info

    def _get_tag(self, audio_file, *tag_names) -> Optional[str]:
        """Obtiene el valor de un tag, probando múltiples nombres"""
        for tag_name in tag_names:
            try:
                if tag_name in audio_file:
                    value = audio_file[tag_name]
                    if isinstance(value, list) and value:
                        return str(value[0]).strip()
                    elif value:
                        return str(value).strip()
            except (KeyError, AttributeError):
                continue
        return None


class MusicBrainzEnricher:
    """Enriquece la información del álbum usando MusicBrainz"""

    def enrich_album_info(self, album_info: AlbumInfo) -> AlbumInfo:
        """Enriquece la información del álbum"""

        # Intentar con MBID primero
        if album_info.mbid:
            enriched = self._get_info_by_mbid(album_info)
            if enriched:
                album_info = enriched

        # Si no tiene MBID o no se encontró, buscar por artista y álbum
        elif album_info.artist and album_info.album:
            enriched = self._search_by_artist_album(album_info)
            if enriched:
                album_info = enriched

        # Generar enlaces para códigos QR
        logger.info("Generando enlaces para códigos QR...")
        QRLinkGenerator.generate_qr_links(album_info)

        if not album_info.artist or not album_info.album:
            logger.warning("No se pudo enriquecer la información desde MusicBrainz")

        return album_info

    def _get_info_by_mbid(self, album_info: AlbumInfo) -> Optional[AlbumInfo]:
        """Obtiene información usando el MBID"""
        try:
            result = musicbrainzngs.get_release_by_id(
                album_info.mbid,
                includes=['artist-credits', 'release-groups', 'labels', 'recordings']
            )
            return self._parse_musicbrainz_result(result['release'], album_info)
        except Exception as e:
            logger.warning(f"Error consultando MusicBrainz por MBID {album_info.mbid}: {e}")
            return None

    def _search_by_artist_album(self, album_info: AlbumInfo) -> Optional[AlbumInfo]:
        """Busca información por artista y álbum"""
        try:
            results = musicbrainzngs.search_releases(
                artist=album_info.artist,
                release=album_info.album,
                limit=5
            )

            if results['release-list']:
                # Tomar el primer resultado
                release = results['release-list'][0]

                # Obtener información completa
                detailed_result = musicbrainzngs.get_release_by_id(
                    release['id'],
                    includes=['artist-credits', 'release-groups', 'labels', 'recordings']
                )

                return self._parse_musicbrainz_result(detailed_result['release'], album_info)

        except Exception as e:
            logger.warning(f"Error buscando en MusicBrainz: {e}")

        return None

    def _parse_musicbrainz_result(self, release, original_info: AlbumInfo) -> AlbumInfo:
        """Parsea el resultado de MusicBrainz"""
        enriched = AlbumInfo()

        # Mantener información original como fallback
        enriched.artist = original_info.artist
        enriched.album = original_info.album
        enriched.tracks = original_info.tracks
        enriched.genres = original_info.genres

        # Enriquecer con datos de MusicBrainz
        try:
            # Artista
            if 'artist-credit' in release and release['artist-credit']:
                artist_names = []
                artist_mbids = []
                for ac in release['artist-credit']:
                    if 'artist' in ac:
                        artist_names.append(ac['artist']['name'])
                        # Extraer MBID del artista
                        if 'id' in ac['artist']:
                            artist_mbids.append(ac['artist']['id'])

                if artist_names:
                    enriched.artist = ', '.join(artist_names)
                if artist_mbids:
                    enriched.artist_mbid = artist_mbids[0]  # Usar el primer artista

            # Álbum
            if 'title' in release:
                enriched.album = release['title']

            # Fecha
            if 'date' in release:
                enriched.date = release['date']
            elif original_info.date:
                enriched.date = original_info.date

            # Sello discográfico
            if 'label-info-list' in release and release['label-info-list']:
                labels = []
                for label_info in release['label-info-list']:
                    if 'label' in label_info and 'name' in label_info['label']:
                        labels.append(label_info['label']['name'])
                if labels:
                    enriched.label = ', '.join(labels)
            elif original_info.label:
                enriched.label = original_info.label

            # Géneros (desde release-group)
            if 'release-group' in release and 'tag-list' in release['release-group']:
                genres = [tag['name'] for tag in release['release-group']['tag-list']]
                if genres:
                    enriched.genres = genres

            # MBID
            enriched.mbid = release['id']

            # URL de portada (Cover Art Archive)
            enriched.cover_art_url = f"https://coverartarchive.org/release/{release['id']}/front"

        except Exception as e:
            logger.warning(f"Error parseando resultado de MusicBrainz: {e}")

        return enriched


class CoverArtDownloader:
    """Descargador de portadas de álbumes"""

    def download_cover(self, album_info: AlbumInfo) -> Optional[Image.Image]:
        """Descarga la portada del álbum y extrae la paleta de colores"""

        cover_image = None

        # Intentar desde Cover Art Archive si tenemos MBID
        if album_info.cover_art_url:
            cover_image = self._download_from_url(album_info.cover_art_url)

        # Buscar archivo de imagen en la carpeta si no se descargó
        if not cover_image and album_info.tracks:
            folder_path = Path(album_info.tracks[0]['file']).parent
            cover_image = self._find_local_cover(folder_path)

        # Crear portada por defecto si no se encontró ninguna
        if not cover_image:
            cover_image = self._create_default_cover(album_info)

        # Extraer paleta de colores de la portada
        if cover_image:
            self._extract_color_palette(album_info, cover_image)

        return cover_image

    def _extract_color_palette(self, album_info: AlbumInfo, cover_image: Image.Image):
        """Extrae la paleta de colores de la portada"""
        try:
            logger.info("Extrayendo paleta de colores de la portada...")

            # Extraer color dominante
            dominant_color = ColorAnalyzer.extract_dominant_color(cover_image)

            # Realzar el color para el fondo
            enhanced_bg = ColorAnalyzer.enhance_color(dominant_color, saturation_boost=0.8)

            # Generar paleta completa
            album_info.color_palette = {
                'background': enhanced_bg,
                'text_primary': ColorAnalyzer.get_contrast_color(enhanced_bg),
                'text_secondary': ColorAnalyzer.get_secondary_color(enhanced_bg),
                'border': ColorAnalyzer.get_border_color(enhanced_bg)
            }

            logger.info(f"Paleta extraída - Fondo: {enhanced_bg}, Texto: {album_info.color_palette['text_primary']}")

        except Exception as e:
            logger.warning(f"Error extrayendo paleta de colores: {e}")
            # Mantener paleta por defecto
            album_info.color_palette = {
                'background': (255, 255, 255),
                'text_primary': (0, 0, 0),
                'text_secondary': (80, 80, 80),
                'border': (230, 230, 230)
            }

    def _download_from_url(self, url: str) -> Optional[Image.Image]:
        """Descarga imagen desde URL"""
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            image = Image.open(requests.get(url, stream=True).raw)
            return image

        except Exception as e:
            logger.warning(f"Error descargando portada desde {url}: {e}")
            return None

    def _find_local_cover(self, folder_path: Path) -> Optional[Image.Image]:
        """Busca archivos de imagen en la carpeta"""
        cover_names = ['cover', 'folder', 'front', 'album']
        image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']

        # Buscar archivos específicos
        for cover_name in cover_names:
            for ext in image_extensions:
                cover_file = folder_path / f"{cover_name}{ext}"
                if cover_file.exists():
                    try:
                        return Image.open(cover_file)
                    except Exception as e:
                        logger.warning(f"Error abriendo imagen {cover_file}: {e}")

        # Buscar cualquier imagen
        for file_path in folder_path.iterdir():
            if file_path.suffix.lower() in image_extensions:
                try:
                    return Image.open(file_path)
                except Exception as e:
                    logger.warning(f"Error abriendo imagen {file_path}: {e}")

        return None

    def _create_default_cover(self, album_info: AlbumInfo) -> Image.Image:
        """Crea una portada por defecto con colores mejorados"""
        size = 500

        # Colores base más atractivos
        base_colors = [
            (45, 55, 72),    # Azul gris oscuro
            (68, 51, 122),   # Púrpura
            (31, 81, 89),    # Verde azulado
            (120, 53, 15),   # Marrón cálido
            (74, 29, 30),    # Rojo oscuro
            (45, 74, 60),    # Verde oscuro
        ]

        # Elegir color base según el nombre del álbum
        color_index = sum(ord(c) for c in (album_info.album or "default")) % len(base_colors)
        base_color = base_colors[color_index]

        # Crear imagen con gradiente
        image = Image.new('RGB', (size, size), base_color)
        draw = ImageDraw.Draw(image)

        # Gradiente sutil
        for y in range(size):
            ratio = y / size
            r, g, b = base_color

            # Crear variación tonal
            new_r = max(0, min(255, int(r + ratio * 30 - 15)))
            new_g = max(0, min(255, int(g + ratio * 30 - 15)))
            new_b = max(0, min(255, int(b + ratio * 30 - 15)))

            draw.line([(0, y), (size, y)], fill=(new_r, new_g, new_b))

        # Añadir patrón geométrico sutil
        pattern_color = tuple(min(255, c + 20) for c in base_color)

        # Círculos concéntricos
        center = size // 2
        for radius in range(50, 200, 40):
            draw.ellipse([
                center - radius, center - radius,
                center + radius, center + radius
            ], outline=pattern_color, width=2)

        # Texto con mejor tipografía
        try:
            title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
            artist_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 30)
        except:
            title_font = ImageFont.load_default()
            artist_font = ImageFont.load_default()

        # Colores de texto contrastantes
        text_color = ColorAnalyzer.get_contrast_color(base_color)
        shadow_color = tuple(c // 3 for c in text_color)

        # Texto del álbum
        album_text = (album_info.album or "Album").upper()
        artist_text = (album_info.artist or "Artist").upper()

        # Posicionar texto del álbum
        bbox = draw.textbbox((0, 0), album_text, font=title_font)
        text_width = bbox[2] - bbox[0]
        x = (size - text_width) // 2
        y = int(size * 0.7)

        # Sombra sutil
        draw.text((x + 2, y + 2), album_text, fill=shadow_color, font=title_font)
        draw.text((x, y), album_text, fill=text_color, font=title_font)

        # Texto del artista
        bbox = draw.textbbox((0, 0), artist_text, font=artist_font)
        text_width = bbox[2] - bbox[0]
        x = (size - text_width) // 2
        y += 50

        draw.text((x + 1, y + 1), artist_text, fill=shadow_color, font=artist_font)
        draw.text((x, y), artist_text, fill=text_color, font=artist_font)

        return image


def _build_github_pages_url(album_info: "AlbumInfo") -> str:
    """Constructs the GitHub Pages URL for the album page."""
    safe_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_. "
    name = f"{album_info.artist} - {album_info.album}"
    safe_name = "".join(c if c in safe_chars else "_" for c in name)
    while "  " in safe_name:
        safe_name = safe_name.replace("  ", " ")
    while "__" in safe_name:
        safe_name = safe_name.replace("__", "_")
    safe_name = safe_name.strip(" -_")
    return f"{GITHUB_PAGES_BASE}/albums/{quote(safe_name)}.html"


class ArtistImageFetcher:
    """Fetches an artist photo from Wikipedia or Last.fm."""

    def fetch(self, album_info: "AlbumInfo") -> Optional[Image.Image]:
        image = self._from_wikipedia(album_info)
        if image:
            return image
        image = self._from_lastfm(album_info)
        return image

    def _from_wikipedia(self, album_info: "AlbumInfo") -> Optional[Image.Image]:
        wiki_url = album_info.qr_links.get("wikipedia_artist", "")
        if not wiki_url:
            return None
        try:
            parsed = urlparse(wiki_url)
            title = parsed.path.split("/wiki/")[-1]
            lang = parsed.netloc.split(".")[0]
            api_url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{quote(title)}"
            resp = requests.get(api_url, timeout=8, headers={"User-Agent": "SobrinosNFC/1.0"})
            resp.raise_for_status()
            data = resp.json()
            thumb = data.get("thumbnail", {}).get("source")
            if thumb:
                img_resp = requests.get(thumb, timeout=8)
                img_resp.raise_for_status()
                return Image.open(io.BytesIO(img_resp.content)).convert("RGB")
        except Exception as e:
            logger.debug(f"Wikipedia artist image failed: {e}")
        return None

    def _from_lastfm(self, album_info: "AlbumInfo") -> Optional[Image.Image]:
        api_key = os.environ.get("LASTFM_API_KEY", "")
        if not api_key or not album_info.artist:
            return None
        try:
            url = (
                "https://ws.audioscrobbler.com/2.0/"
                f"?method=artist.getinfo&artist={quote(album_info.artist)}"
                f"&api_key={api_key}&format=json"
            )
            resp = requests.get(url, timeout=8)
            resp.raise_for_status()
            images = resp.json().get("artist", {}).get("image", [])
            for img in reversed(images):
                src = img.get("#text", "")
                if src and "2a96cbd8b46e442fc41c2b86b821562f" not in src:
                    img_resp = requests.get(src, timeout=8)
                    img_resp.raise_for_status()
                    return Image.open(io.BytesIO(img_resp.content)).convert("RGB")
        except Exception as e:
            logger.debug(f"Last.fm artist image failed: {e}")
        return None


class CardGenerator:
    """Generador de tarjetas de álbumes"""

    def __init__(self, custom_font_path: str = None):
        self.custom_font_path = custom_font_path
        self.setup_fonts()

    def setup_fonts(self):
        self.fonts = {}

        font_paths = []
        if self.custom_font_path and os.path.exists(self.custom_font_path):
            font_paths.append(self.custom_font_path)

        font_paths.extend([
            # Debian / Raspberry Pi OS
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
            # Arch Linux
            "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/TTF/DejaVuSans.ttf",
            "/usr/share/fonts/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/liberation/LiberationSans-Regular.ttf",
            # macOS
            "/Library/Fonts/Arial Bold.ttf",
            "/Library/Fonts/Arial.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ])

        # Last resort: ask fc-list for any usable font
        try:
            import subprocess
            out = subprocess.check_output(["fc-list", "--format=%{file}\n"], timeout=5).decode()
            for line in out.splitlines():
                line = line.strip()
                if line.endswith((".ttf", ".TTF", ".otf")):
                    font_paths.append(line)
        except Exception:
            pass

        sizes = {'title': 76, 'artist': 64, 'info': 50, 'track': 44}

        for font_path in font_paths:
            if os.path.exists(font_path):
                try:
                    self.fonts = {k: ImageFont.truetype(font_path, v) for k, v in sizes.items()}
                    logger.info(f"✓ Fuentes cargadas desde: {font_path}")
                    return
                except Exception as e:
                    logger.debug(f"Error cargando {font_path}: {e}")
                    continue

        logger.warning("⚠️  No se encontró ninguna fuente TTF — las tarjetas usarán fuente de mapa de bits (texto pequeño)")
        default_font = ImageFont.load_default()
        self.fonts = {k: default_font for k in sizes}

    def generate_front_card(self, album_info: AlbumInfo) -> Image.Image:
        """Genera la cara A (frontal) de la tarjeta con colores dinámicos"""
        # Obtener paleta de colores
        bg_color = album_info.color_palette['background']
        text_primary = album_info.color_palette['text_primary']
        text_secondary = album_info.color_palette['text_secondary']
        border_color = album_info.color_palette['border']

        # Crear imagen base con color de fondo dinámico
        image = Image.new('RGB', (CARD_WIDTH, CARD_HEIGHT), bg_color)
        draw = ImageDraw.Draw(image)

        # Área de la portada (51x51mm en la parte superior)
        cover_y = 10
        cover_x = (CARD_WIDTH - COVER_SIZE) // 2

        # Redimensionar y colocar portada
        if album_info.cover_image:
            cover = album_info.cover_image.resize((COVER_SIZE, COVER_SIZE), Image.Resampling.LANCZOS)
            image.paste(cover, (cover_x, cover_y))

        # Marco sutil para la portada
        frame_color = ColorAnalyzer.get_border_color(bg_color)
        draw.rectangle([
            cover_x - 2, cover_y - 2,
            cover_x + COVER_SIZE + 2, cover_y + COVER_SIZE + 2
        ], outline=frame_color, width=3)

        # Área de texto (30mm en la parte inferior)
        text_y_start = cover_y + COVER_SIZE + 20
        text_area_height = CARD_HEIGHT - text_y_start - 20

        # Información del álbum
        current_y = text_y_start
        margin = 15
        text_bottom = CARD_HEIGHT - 20  # do not go below this

        def fits(y, step):
            return y + step <= text_bottom

        # Título del álbum
        if album_info.album:
            lines = self._wrap_text(draw, album_info.album, self.fonts['title'], CARD_WIDTH - 2 * margin)
            for line in lines[:3]:
                if not fits(current_y, 84):
                    break
                draw.text((margin, current_y), line, fill=text_primary, font=self.fonts['title'])
                current_y += 84

        current_y += 8

        # Artista
        if album_info.artist and fits(current_y, 72):
            lines = self._wrap_text(draw, album_info.artist, self.fonts['artist'], CARD_WIDTH - 2 * margin)
            for line in lines[:2]:
                if not fits(current_y, 72):
                    break
                draw.text((margin, current_y), line, fill=text_secondary, font=self.fonts['artist'])
                current_y += 72

        current_y += 8

        # Fecha
        if album_info.date and fits(current_y, 58):
            draw.text((margin, current_y), album_info.date[:4], fill=text_secondary, font=self.fonts['info'])
            current_y += 58

        # Géneros — sólo si hay espacio
        if album_info.genres and fits(current_y, 58):
            genres_text = " · ".join(album_info.genres[:2])
            draw.text((margin, current_y), genres_text, fill=text_secondary, font=self.fonts['info'])

        # Borde sutil de la tarjeta
        draw.rectangle([0, 0, CARD_WIDTH-1, CARD_HEIGHT-1], outline=border_color, width=2)

        return image

    def generate_back_card(self, album_info: AlbumInfo, custom_url: Optional[str] = None) -> Image.Image:
        """Genera la cara B: foto del artista (top), tracklist (medio), QR GitHub Pages (bottom)."""
        bg_color = album_info.color_palette['background']
        text_primary = album_info.color_palette['text_primary']
        text_secondary = album_info.color_palette['text_secondary']
        border_color = album_info.color_palette['border']

        image = Image.new('RGB', (CARD_WIDTH, CARD_HEIGHT), bg_color)
        draw = ImageDraw.Draw(image)

        margin = 25
        photo_height = 280  # px for artist photo strip

        # ── Artist photo ──────────────────────────────────────────────────────
        artist_image = ArtistImageFetcher().fetch(album_info)
        if artist_image:
            ratio = CARD_WIDTH / artist_image.width
            new_h = int(artist_image.height * ratio)
            artist_image = artist_image.resize((CARD_WIDTH, new_h), Image.Resampling.LANCZOS)
            # centre-crop to photo_height
            if new_h > photo_height:
                top = (new_h - photo_height) // 2
                artist_image = artist_image.crop((0, top, CARD_WIDTH, top + photo_height))
            else:
                photo_height = new_h
            image.paste(artist_image, (0, 0))
        else:
            photo_height = 0  # no photo — tracklist gets the extra space

        # ── Tracklist ─────────────────────────────────────────────────────────
        qr_section_height = 185
        num_col_width = 60
        title_x = margin + num_col_width
        max_title_w = CARD_WIDTH - title_x - margin
        track_bottom = CARD_HEIGHT - qr_section_height
        available_h = track_bottom - photo_height - margin

        # Pick the largest font size where all tracks fit
        track_font = self._fit_tracklist_font(
            draw, album_info.tracks, available_h, max_title_w
        )
        line_step = track_font.size + 8

        # Measure actual number column width with chosen font
        num_bbox = draw.textbbox((0, 0), "00.", font=track_font)
        num_col_width = (num_bbox[2] - num_bbox[0]) + 10
        title_x = margin + num_col_width
        max_title_w = CARD_WIDTH - title_x - margin

        current_y = photo_height + margin
        for track in album_info.tracks:
            lines = self._wrap_text(draw, track['title'], track_font, max_title_w)
            lines = lines[:2]
            needed = len(lines) * line_step + 4
            if current_y + needed > track_bottom:
                break
            draw.text((margin, current_y), f"{track['number']:02d}.",
                      fill=text_secondary, font=track_font)
            for j, line in enumerate(lines):
                draw.text((title_x, current_y + j * line_step), line,
                          fill=text_primary, font=track_font)
            current_y += needed

        # ── QR ────────────────────────────────────────────────────────────────
        self._draw_qr_section(image, draw, album_info, custom_url)

        draw.rectangle([0, 0, CARD_WIDTH - 1, CARD_HEIGHT - 1], outline=border_color, width=2)
        return image

    def _draw_qr_section(self, image: Image.Image, draw, album_info, custom_url: Optional[str] = None):
        """Draws a single centred QR pointing to the GitHub Pages album page."""
        bg  = album_info.color_palette['background']
        fg  = album_info.color_palette['text_secondary']
        margin = 25
        qr_size = 155

        url = custom_url or _build_github_pages_url(album_info)
        qr_img = QRCodeGenerator.create_qr_code(url, size=qr_size, bg_color=bg, fg_color=fg)
        if not qr_img:
            return

        x = (CARD_WIDTH - qr_size) // 2
        y = CARD_HEIGHT - qr_size - margin - 22
        image.paste(qr_img, (x, y))

    def _fit_tracklist_font(self, draw, tracks: list, available_h: int, max_title_w: int):
        """Return the largest font size where all tracks fit in available_h."""
        base_font = self.fonts['track']
        try:
            font_path = base_font.path
        except AttributeError:
            return base_font  # bitmap fallback — nothing to do

        for size in range(base_font.size, 20, -2):
            font = ImageFont.truetype(font_path, size)
            step = size + 8
            total = 0
            for track in tracks:
                lines = self._wrap_text_with_font(draw, track['title'], font, max_title_w)
                total += min(len(lines), 2) * step + 4
            if total <= available_h:
                return font

        return ImageFont.truetype(font_path, 22)

    def _wrap_text_with_font(self, draw, text: str, font, max_width: int) -> List[str]:
        words = text.split()
        lines, current = [], ""
        for word in words:
            test = (current + " " + word).strip()
            bbox = draw.textbbox((0, 0), test, font=font)
            if bbox[2] - bbox[0] <= max_width:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines or [text]

    def _wrap_text(self, draw, text: str, font, max_width: int) -> List[str]:
        """Divide el texto en líneas que caben en el ancho máximo"""
        words = text.split()
        lines = []
        current_line = ""

        for word in words:
            test_line = current_line + " " + word if current_line else word
            bbox = draw.textbbox((0, 0), test_line, font=font)
            text_width = bbox[2] - bbox[0]

            if text_width <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word

        if current_line:
            lines.append(current_line)

        return lines

    def _truncate_text(self, draw, text: str, font, max_width: int) -> str:
        """Trunca el texto para que quepa en el ancho máximo"""
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]

        if text_width <= max_width:
            return text

        # Truncar con "..."
        ellipsis = "..."
        max_chars = len(text)

        while max_chars > 0:
            truncated = text[:max_chars] + ellipsis
            bbox = draw.textbbox((0, 0), truncated, font=font)
            text_width = bbox[2] - bbox[0]

            if text_width <= max_width:
                return truncated

            max_chars -= 1

        return ellipsis


def main():
    """Función principal"""
    parser = argparse.ArgumentParser(description="Generador de Tarjetas de Álbumes")
    PROJECT_ROOT = Path(__file__).parent.parent
    parser.add_argument("folder", help="Carpeta que contiene los archivos del álbum")
    parser.add_argument("-o", "--output",
                        help=f"Carpeta de salida (por defecto: {PROJECT_ROOT / 'docs' / 'portadas' / 'musica'})")
    parser.add_argument("--custom-url", help="URL personalizada para el QR (por defecto: GitHub Pages del álbum)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Modo verboso")
    parser.add_argument("-f", "--font", help="Ruta a archivo de fuente TTF personalizada")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    folder_path = Path(args.folder)
    if not folder_path.exists():
        logger.error(f"La carpeta {folder_path} no existe")
        sys.exit(1)

    output_path = Path(args.output) if args.output else PROJECT_ROOT / "docs" / "portadas" / "musica"
    output_path.mkdir(parents=True, exist_ok=True)

    try:
        # Procesar archivos de música
        logger.info("Procesando archivos de música...")
        processor = MusicFileProcessor(folder_path)
        audio_files = processor.get_audio_files()

        if not audio_files:
            logger.error("No se encontraron archivos de audio en la carpeta")
            sys.exit(1)

        logger.info(f"Encontrados {len(audio_files)} archivos de audio")

        # Extraer información del álbum
        album_info = processor.extract_album_info(audio_files)
        logger.info(f"Álbum: {album_info.artist} - {album_info.album}")

        # Enriquecer con MusicBrainz
        logger.info("Buscando información en MusicBrainz...")
        enricher = MusicBrainzEnricher()
        album_info = enricher.enrich_album_info(album_info)

        # Descargar portada
        logger.info("Descargando portada...")
        downloader = CoverArtDownloader()
        album_info.cover_image = downloader.download_cover(album_info)

        # Generar tarjetas
        logger.info("Generando tarjetas...")
        generator = CardGenerator(custom_font_path=args.font)

        qr_url = args.custom_url or _build_github_pages_url(album_info)
        logger.info(f"QR apuntará a: {qr_url}")

        front_card = generator.generate_front_card(album_info)
        back_card = generator.generate_back_card(album_info, custom_url=args.custom_url)

        # Guardar imágenes
        album_name = album_info.album or "album"
        album_name = "".join(c for c in album_name if c.isalnum() or c in (' ', '-', '_')).rstrip()

        front_path = output_path / f"{album_name}_cara_A.png"
        back_path = output_path / f"{album_name}_cara_B.png"

        front_card.save(front_path, dpi=(DPI, DPI))
        back_card.save(back_path, dpi=(DPI, DPI))

        logger.info(f"Tarjetas guardadas:")
        logger.info(f"  Cara A: {front_path}")
        logger.info(f"  Cara B: {back_path}")

        # Guardar información del álbum como JSON
        info_path = output_path / f"{album_name}_info.json"
        album_data = {
            "artist": album_info.artist,
            "album": album_info.album,
            "date": album_info.date,
            "label": album_info.label,
            "genres": album_info.genres,
            "mbid": album_info.mbid,
            "tracks": [{"number": t["number"], "title": t["title"]} for t in album_info.tracks]
        }

        with open(info_path, 'w', encoding='utf-8') as f:
            json.dump(album_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Información guardada en: {info_path}")

    except Exception as e:
        logger.error(f"Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
