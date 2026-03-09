#!/usr/bin/env python3
"""
Generador de Tarjetas NFC para Películas y Series.

Obtiene datos y póster directamente de TMDB, luego genera:
  Cara A — póster a sangre, sin texto
  Cara B — fondo color + título + año + QR TMDB

Uso:
  python nfc/nfc_tarjetas_cine.py
  python nfc/nfc_tarjetas_cine.py -o /ruta/salida -f /ruta/fuente.ttf
  python nfc/nfc_tarjetas_cine.py --secretos secrets.enc.yaml
"""

import colorsys
import json
import logging
import re
import sys
from collections import Counter
from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Error: pip install Pillow"); sys.exit(1)

try:
    import qrcode
    from qrcode.image.styledpil import StyledPilImage
    from qrcode.image.styles.moduledrawers import RoundedModuleDrawer
except ImportError:
    print("Error: pip install qrcode[pil]"); sys.exit(1)

try:
    import cairosvg
except ImportError:
    print("Error: pip install cairosvg"); sys.exit(1)

# ── Importaciones del proyecto ──────────────────────────────────────────────
PROYECTO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROYECTO_ROOT))

from modules.secretos import cargar as cargar_secretos
from tmdb_enriquecer import TmdbClient, extraer, normalizar_busqueda, seleccionar

# ── Constantes ───────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DPI         = 300
CARD_WIDTH  = int(52 * DPI / 25.4)   # ~613 px
CARD_HEIGHT = int(82 * DPI / 25.4)   # ~969 px

WEB_BASE  = "https://volteret4.github.io/sobrinos/"

# Colores de fallback cuando no hay póster
BG_SERIES = (180, 220, 240)
BG_MOVIE  = (180, 230, 180)

JSON_CINE     = PROYECTO_ROOT / "docs" / "cine" / "tarjetas_video_info.json"
NFC_PLAYLIST  = PROYECTO_ROOT / "nfc_playlist.json"
LOGOS_DIR     = PROYECTO_ROOT / "docs" / "cine" / "logos"

# Emoji por género (NotoColorEmoji)
GENRES_ICONS: Dict[str, str] = {
    "acción":          "🏃",
    "aventura":        "🌊",
    "comedia":         "🤡",
    "drama":           "🎭",
    "terror":          "👻",
    "ciencia ficción": "🚀",
    "animación":       "🎨",
    "romance":         "❤️",
    "thriller":        "🔪",
    "suspense":        "🍿",
    "fantasía":        "🧚",
    "musical":         "🎵",
    "misterio":        "🔍",
    "documental":      "🌍",
    "familia":         "🏠",
    "historia":        "📜",
    "bélica":          "🪖",
    "western":         "🤠",
    "crimen":          "🔫",
    "kids":             "👑",
}

# Colores por género (fallback si no hay emoji font)
GENRE_COLORS: Dict[str, Tuple[int, int, int]] = {
    "acción":          (220,  55,  55),
    "aventura":        ( 50, 180, 100),
    "comedia":         (240, 180,  40),
    "drama":           ( 80, 100, 200),
    "terror":          ( 90,  20,  20),
    "ciencia ficción": ( 40, 160, 220),
    "animación":       (255, 140,  40),
    "romance":         (220,  80, 150),
    "thriller":        ( 80,  80,  80),
    "suspense":        ( 80,  80,  80),
    "fantasía":        (150,  60, 220),
    "musical":         (200,  80, 180),
    "misterio":        ( 60,  60, 110),
    "documental":      (120, 150,  80),
    "familia":         ( 60, 200, 200),
    "historia":        (160, 120,  60),
    "bélica":          ( 90,  70,  50),
    "western":         (190, 140,  60),
    "crimen":          ( 50,  50,  80),
}



# Estudios especiales → etiqueta para la tarjeta
STUDIO_LABELS: Dict[str, str] = {
    "walt disney":          "DISNEY",
    "disney":               "DISNEY",
    "pixar":                "PIXAR",
    "marvel":               "MARVEL",
    "studio ghibli":        "GHIBLI",
    "dreamworks":           "DREAMWORKS",
    "lucasfilm":            "LUCASFILM",
    "a24":                  "A24",
    "warner bros":          "WARNER BROS",
    "universal":            "UNIVERSAL",
    "sony pictures":        "SONY",
    "paramount":            "PARAMOUNT",
    "20th century":         "20TH CENTURY",
    "netflix":              "NETFLIX",
    "amazon":               "AMAZON",
    "apple":                "APPLE TV+",
}

# SVG filename por etiqueta de estudio (en LOGOS_DIR)
STUDIO_LOGOS: Dict[str, str] = {
    "DISNEY":      "disney.svg",
    "PIXAR":       "pixar.svg",
    "MARVEL":      "marvel.svg",
    "DREAMWORKS":  "dreamworks.svg",
    "WARNER BROS": "warnerbros.svg",
    "UNIVERSAL":   "universal.svg",
    "SONY":        "sony.svg",
    "PARAMOUNT":   "paramount.svg",
    "NETFLIX":     "netflix.svg",
    "AMAZON":      "amazon.svg",
    "APPLE TV+":   "apple.svg",
}

# Colores de fondo para la etiqueta de estudio (cuando no hay SVG)
STUDIO_COLORS: Dict[str, Tuple[int, int, int]] = {
    "DISNEY":      ( 30,  70, 180),
    "PIXAR":       ( 30, 140, 220),
    "MARVEL":      (180,  20,  20),
    "GHIBLI":      ( 60, 140,  80),
    "DREAMWORKS":  ( 30,  90, 150),
    "LUCASFILM":   ( 80,  60,  30),
    "A24":         ( 30,  30,  30),
    "WARNER BROS": ( 30,  30, 100),
    "UNIVERSAL":   ( 10,  10,  10),
    "SONY":        ( 20,  20, 180),
    "PARAMOUNT":   ( 20,  60, 140),
    "20TH CENTURY":( 50,  20,  20),
    "NETFLIX":     (180,  20,  20),
    "AMAZON":      ( 30, 120, 180),
    "APPLE TV+":   ( 30,  30,  30),
}


# ─────────────────────────────────────────────
#  Color dinámico a partir del póster
# ─────────────────────────────────────────────

def color_dominante(imagen: Image.Image) -> Tuple[int, int, int]:
    """Extrae el color dominante de una imagen, ignorando blancos y negros puros."""
    img = imagen.copy().resize((150, 150), Image.Resampling.LANCZOS).convert("RGB")
    # Redondear a bloques de 10 para agrupar colores similares
    agrupados = [((r // 10) * 10, (g // 10) * 10, (b // 10) * 10)
                 for r, g, b in img.getdata()]
    for color, _ in Counter(agrupados).most_common(20):
        r, g, b = color
        brillo = (r + g + b) / 3
        saturacion = (max(r, g, b) - min(r, g, b)) / max(r, g, b, 1)
        if 20 < brillo < 235 and saturacion > 0.12:
            return color
    # Fallback: media estadística
    from PIL import ImageStat
    stat = ImageStat.Stat(img)
    return tuple(int(c) for c in stat.mean)


def realzar_color(color: Tuple[int, int, int], boost: float = 0.7) -> Tuple[int, int, int]:
    """Aumenta la saturación para que el fondo sea más vivo pero no agresivo."""
    r, g, b = (c / 255.0 for c in color)
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    s = min(1.0, s * (1 + boost))
    v = min(1.0, v * 0.85)   # ligeramente más oscuro para mejor contraste
    r2, g2, b2 = colorsys.hsv_to_rgb(h, s, v)
    return (int(r2 * 255), int(g2 * 255), int(b2 * 255))


def color_texto(bg: Tuple[int, int, int]) -> Tuple[int, int, int]:
    """Blanco u oscuro según luminancia perceptual del fondo."""
    r, g, b = bg
    luminancia = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return (240, 240, 240) if luminancia < 0.5 else (30, 30, 30)


# ─────────────────────────────────────────────
#  Slug para URL de la web
# ─────────────────────────────────────────────

def web_slug(title: str) -> str:
    """Slug simple para usar como anchor en la URL de GitHub Pages."""
    s = re.sub(r"[^\w\s-]", "", title.lower()).replace(" ", "_")
    return s.strip("_")[:60] or "item"


def detectar_estudio(estudios: List[str]) -> Optional[str]:
    """Devuelve la etiqueta del primer estudio reconocido, o None."""
    for nombre in estudios:
        clave = nombre.lower()
        for patron, etiqueta in STUDIO_LABELS.items():
            if patron in clave:
                return etiqueta
    return None


def cargar_logo_estudio(etiqueta: str, height: int) -> Optional[Image.Image]:
    """Carga el SVG del estudio y lo convierte a PIL RGBA con la altura indicada."""
    filename = STUDIO_LOGOS.get(etiqueta)
    if not filename:
        return None
    svg_path = LOGOS_DIR / filename
    if not svg_path.exists():
        logger.warning(f"Logo no encontrado: {svg_path}")
        return None
    try:
        png_bytes = cairosvg.svg2png(url=str(svg_path), output_height=height)
        return Image.open(BytesIO(png_bytes)).convert("RGBA")
    except Exception as e:
        logger.warning(f"Error cargando logo {filename}: {e}")
        return None


# ─────────────────────────────────────────────
#  Modelo de datos de la tarjeta
# ─────────────────────────────────────────────

class VideoInfo:
    def __init__(self):
        self.title:        str = ""
        self.media_type:   str = "movie"   # "movie" | "series"
        self.year:         str = ""
        self.tmdb_url:     str = ""        # enlace TMDB (guardado en JSON)
        self.web_url:      str = ""        # URL GitHub Pages → QR cara B
        self.tmdb_datos:   Dict = {}       # datos completos de TMDB para el JSON
        self.poster_image: Optional[Image.Image] = None

    def tipo_label(self) -> str:
        return "SERIE" if self.media_type == "series" else "PELÍCULA"

    def qr_label(self) -> str:
        return ""

    def fallback_bg(self) -> Tuple[int, int, int]:
        return BG_SERIES if self.media_type == "series" else BG_MOVIE


# ─────────────────────────────────────────────
#  Descarga de póster
# ─────────────────────────────────────────────

def descargar_poster(url: str) -> Optional[Image.Image]:
    """Descarga una imagen desde una URL y la devuelve como objeto PIL."""
    try:
        logger.info(f"Descargando póster…")
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        return Image.open(BytesIO(resp.content)).convert("RGB")
    except Exception as e:
        logger.warning(f"No se pudo descargar el póster: {e}")
        return None


# ─────────────────────────────────────────────
#  Generador de QR
# ─────────────────────────────────────────────

class QRCodeGenerator:

    @staticmethod
    def create(
        url: str, size: int,
        bg: Tuple[int, int, int],
        fg: Tuple[int, int, int],
    ) -> Optional[Image.Image]:
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=10, border=2,
            )
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(
                fill_color=fg, back_color=bg,
                image_factory=StyledPilImage,
                module_drawer=RoundedModuleDrawer(),
            )
            return img.resize((size, size), Image.Resampling.LANCZOS)
        except Exception as e:
            logger.warning(f"Error creando QR: {e}")
            return None


# ─────────────────────────────────────────────
#  Generador de tarjetas
# ─────────────────────────────────────────────

class VideoCardGenerator:

    def __init__(self, font_path: str = None):
        self._load_fonts(font_path)

    # Tamaños de fuente y alturas de línea
    # Tarjeta física: 52×82mm → 613×969px a 300 DPI
    # _SZ en px; dividido entre 300 y por 25.4 da mm de altura de letra
    _TITLE_SZ    = 85   # 14.8 mm → título grande y legible
    _LABEL_SZ    = 40    #  6.1 mm → tipo + año
    _SYNOPSIS_SZ = 65    #  4.6 mm → sinopsis
    _TITLE_LH    = int(_TITLE_SZ    * 1.10)   # 192 — interlineado ajustado
    _LABEL_LH    = int(_LABEL_SZ    * 1.25)   # 90
    _SYNOPSIS_LH = int(_SYNOPSIS_SZ * 1.35)   # 73

    # NotoColorEmoji solo acepta tamaños bitmap fijos; 109 es el más pequeño disponible
    _EMOJI_NATIVE_SZ = 109

    def _load_fonts(self, custom: str = None):
        candidates = []
        if custom and Path(custom).exists():
            candidates.append(custom)
        candidates += [
            "/usr/share/fonts/TTF/DejaVuSans.ttf",
            "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/TTF/FiraCode-Bold.ttf",
        ]
        loaded = False
        for fp in candidates:
            if Path(fp).exists():
                try:
                    self.fonts = {
                        "title":    ImageFont.truetype(fp, self._TITLE_SZ),
                        "label":    ImageFont.truetype(fp, self._LABEL_SZ),
                        "synopsis": ImageFont.truetype(fp, self._SYNOPSIS_SZ),
                    }
                    logger.info(f"Fuente: {fp}")
                    loaded = True
                    break
                except Exception:
                    continue
        if not loaded:
            logger.error(
                "No se encontró ninguna fuente TTF. Instala DejaVu o Liberation:\n"
                "  sudo apt install fonts-dejavu-core"
            )
            sys.exit(1)

        # Fuente de emojis en color (opcional)
        emoji_path = "/usr/share/fonts/noto/NotoColorEmoji.ttf"
        try:
            self.fonts["emoji"] = ImageFont.truetype(emoji_path, self._EMOJI_NATIVE_SZ)
            logger.info("Fuente emoji: NotoColorEmoji")
        except Exception:
            self.fonts["emoji"] = None
            logger.warning("NotoColorEmoji no encontrada; se usarán puntos de color para géneros")

    # ── Cara A: póster a sangre ──────────────────────────────
    def generate_front(self, info: VideoInfo) -> Image.Image:
        card = Image.new("RGB", (CARD_WIDTH, CARD_HEIGHT), info.fallback_bg())
        if info.poster_image:
            img  = info.poster_image
            ow, oh = img.size
            scale  = CARD_HEIGHT / oh
            new_w  = int(ow * scale)
            img    = img.resize((new_w, CARD_HEIGHT), Image.Resampling.LANCZOS)
            paste_x = (CARD_WIDTH - new_w) // 2
            card.paste(img, (paste_x, 0))
        return card

    # Tamaño real del glyph emoji (136×128 en NotoColorEmoji@109)
    _EMOJI_GLYPH_W = 136
    _EMOJI_GLYPH_H = 128

    def _render_emoji(self, char: str, size: int) -> Optional[Image.Image]:
        """Renderiza un emoji en color a PIL RGBA escalado a `size` px."""
        if not self.fonts.get("emoji"):
            return None
        try:
            # Canvas del tamaño real del glyph para evitar recortes
            tmp = Image.new("RGBA", (self._EMOJI_GLYPH_W, self._EMOJI_GLYPH_H), (0, 0, 0, 0))
            ImageDraw.Draw(tmp).text((0, 0), char, font=self.fonts["emoji"], embedded_color=True)
            return tmp.resize((size, size), Image.Resampling.LANCZOS)
        except Exception:
            return None

    # ── Cara B: fondo + título + director + géneros + logo/QR ──
    def generate_back(self, info: VideoInfo) -> Image.Image:
        if info.poster_image:
            bg = realzar_color(color_dominante(info.poster_image))
        else:
            bg = info.fallback_bg()
        fg = color_texto(bg)
        card = Image.new("RGB", (CARD_WIDTH, CARD_HEIGHT), bg)
        draw = ImageDraw.Draw(card)

        margin    = 28
        content_w = CARD_WIDTH - 2 * margin
        y         = margin

        # ── Zona inferior: QR + logo de estudio ───────────
        QR_MM    = 20
        qr_size  = int(QR_MM * DPI / 25.4)   # ~142 px
        qr_y     = CARD_HEIGHT - qr_size - margin
        qr_lbl_y = qr_y - self._LABEL_LH - 8

        estudio  = detectar_estudio(info.tmdb_datos.get("estudios", []))
        logo_img = cargar_logo_estudio(estudio, qr_size) if estudio else None

        # ── Header: TIPO  ·  AÑO ──────────────────────────
        header = info.tipo_label()
        if info.year:
            header += f"  ·  {info.year}"
        draw.text((margin, y), header, fill=fg, font=self.fonts["label"])
        y += self._LABEL_LH
        draw.line([(margin, y), (CARD_WIDTH - margin, y)], fill=fg, width=3)
        y += 14

        # ── Título ────────────────────────────────────────
        for line in self._wrap(draw, info.title, self.fonts["title"], content_w):
            draw.text((margin, y), line, fill=fg, font=self.fonts["title"])
            y += self._TITLE_LH
        y += 14

        # ── Director ──────────────────────────────────────
        director = info.tmdb_datos.get("director", "")
        if director:
            icon_size = self._LABEL_SZ
            dir_emoji = self._render_emoji("🎬", icon_size)
            if dir_emoji:
                card.paste(dir_emoji, (margin, y), mask=dir_emoji)
                dir_x = margin + icon_size + 8
            else:
                draw.text((margin, y), "▶", fill=fg, font=self.fonts["label"])
                dir_x = margin + int(draw.textlength("▶ ", font=self.fonts["label"]))
            draw.text((dir_x, y), director, fill=fg, font=self.fonts["label"])
            y += self._LABEL_LH + 6

        # ── Géneros con emoji de color ─────────────────────
        generos   = info.tmdb_datos.get("generos", [])
        icon_size = self._SYNOPSIS_SZ           # emoji escalado al tamaño del texto
        dot_r     = max(5, icon_size // 5)      # radio del punto fallback
        text_x    = margin + icon_size + 8

        for genero in generos[:5]:
            if y + self._SYNOPSIS_LH > qr_lbl_y - 8:
                break
            emoji_char = GENRES_ICONS.get(genero.lower())
            emoji_img  = self._render_emoji(emoji_char, icon_size) if emoji_char else None
            if emoji_img:
                card.paste(emoji_img, (margin, y), mask=emoji_img)
            else:
                # Fallback: punto de color
                dot_color = GENRE_COLORS.get(genero.lower(), fg)
                cx = margin + dot_r
                cy = y + self._SYNOPSIS_SZ // 2
                draw.ellipse([(cx - dot_r, cy - dot_r), (cx + dot_r, cy + dot_r)],
                             fill=dot_color)
            draw.text((text_x, y), genero, fill=fg, font=self.fonts["synopsis"])
            y += self._SYNOPSIS_LH + 4

        # ── Logo estudio (izq) + QR (der) en la zona inferior ──
        qr_target = info.web_url or info.tmdb_url
        if qr_target:
            qr_img = QRCodeGenerator.create(qr_target, size=qr_size, bg=bg, fg=fg)
            if qr_img:
                if qr_img.mode != "RGB":
                    base = Image.new("RGB", qr_img.size, bg)
                    mask = qr_img.split()[3] if qr_img.mode == "RGBA" else None
                    base.paste(qr_img, mask=mask)
                    qr_img = base

                if logo_img:
                    # Logo a la izquierda, QR a la derecha
                    logo_w = logo_img.width
                    qr_x   = CARD_WIDTH - qr_size - margin
                    logo_x = margin
                    logo_y = qr_y + (qr_size - logo_img.height) // 2
                    card.paste(logo_img, (logo_x, logo_y),
                               mask=logo_img if logo_img.mode == "RGBA" else None)
                    card.paste(qr_img, (qr_x, qr_y))
                    # Etiqueta centrada sobre el QR
                    lbl = info.qr_label()
                    lw  = draw.textbbox((0, 0), lbl, font=self.fonts["label"])[2]
                    lbl_x = qr_x + (qr_size - lw) // 2
                    draw.text((lbl_x, qr_lbl_y), lbl, fill=fg, font=self.fonts["label"])
                else:
                    # Sin logo: QR centrado
                    qr_x = (CARD_WIDTH - qr_size) // 2
                    card.paste(qr_img, (qr_x, qr_y))
                    lbl = info.qr_label()
                    lw  = draw.textbbox((0, 0), lbl, font=self.fonts["label"])[2]
                    draw.text(((CARD_WIDTH - lw) // 2, qr_lbl_y), lbl, fill=fg, font=self.fonts["label"])

        return card

    def _wrap(self, draw, text: str, font, max_w: int) -> List[str]:
        """Ajusta texto a max_w px. O(n) usando anchos individuales por palabra."""
        space_w = draw.textlength(" ", font=font)
        word_ws = [(w, draw.textlength(w, font=font)) for w in text.split()]
        lines: List[str] = []
        cur: List[str] = []
        cur_w = 0.0
        for word, ww in word_ws:
            add_w = (space_w + ww) if cur else ww
            if cur and cur_w + add_w > max_w:
                lines.append(" ".join(cur))
                cur, cur_w = [word], ww
            else:
                cur.append(word)
                cur_w += add_w
        if cur:
            lines.append(" ".join(cur))
        return lines or [""]


# ─────────────────────────────────────────────
#  Interacción con TMDB
# ─────────────────────────────────────────────

def buscar_en_tmdb(cliente: TmdbClient) -> Optional[VideoInfo]:
    """Pide título y tipo, busca en TMDB, devuelve un VideoInfo listo."""
    print(f"\n{'─' * 52}")
    title = input("  Título (Enter para terminar): ").strip()
    if not title:
        return None

    while True:
        t = input("  Tipo — (p)elícula / (s)erie [p]: ").strip().lower()
        if t in ("", "p", "pelicula", "película"):
            tipo = "movie"; break
        if t in ("s", "serie", "series"):
            tipo = "series"; break
        print("  Introduce 'p' o 's'")

    query = normalizar_busqueda(title)
    print(f"  Buscando '{query}' en TMDB…")

    try:
        resultados = (
            cliente.buscar_pelicula(query) if tipo == "movie"
            else cliente.buscar_serie(query)
        )
    except requests.RequestException as e:
        logger.error(f"Error de red: {e}")
        return None

    elegido = seleccionar(resultados, tipo)
    if not elegido:
        logger.info("Saltando.")
        return None

    tmdb_id = elegido["id"]
    try:
        detalles = (
            cliente.detalles_pelicula(tmdb_id) if tipo == "movie"
            else cliente.detalles_serie(tmdb_id)
        )
    except requests.RequestException as e:
        logger.error(f"Error obteniendo detalles: {e}")
        return None

    datos = extraer(detalles, tipo)

    info = VideoInfo()
    info.title      = datos.get("tmdb_titulo") or title
    info.media_type = tipo
    info.year       = datos.get("year", "")
    info.tmdb_url   = datos.get("tmdb_url", "")
    info.tmdb_datos = datos

    # Descargar póster (HD si está disponible)
    poster_url = datos.get("tmdb_poster_hd") or datos.get("tmdb_poster")
    if poster_url:
        info.poster_image = descargar_poster(poster_url)
    else:
        logger.warning("TMDB no tiene póster para este título.")

    return info


# ─────────────────────────────────────────────
#  JSON de tarjetas (docs/cine/tarjetas_video_info.json)
# ─────────────────────────────────────────────

def cargar_json_cine(path: Path) -> List[Dict]:
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return []


def actualizar_json_cine(tarjetas: List[Dict], info: VideoInfo, front: Path, back: Path) -> List[Dict]:
    """Inserta o actualiza la entrada de la tarjeta en la lista."""
    nueva = {
        "title":    info.title,
        "type":     info.media_type,
        "year":     info.year,
        "slug":     web_slug(info.title),
        "web_url":  info.web_url,
        "tmdb_url": info.tmdb_url,
        "front":    str(front.relative_to(PROYECTO_ROOT)),
        "back":     str(back.relative_to(PROYECTO_ROOT)),
        **info.tmdb_datos,
    }
    for i, t in enumerate(tarjetas):
        if t.get("title", "").strip().lower() == info.title.strip().lower():
            tarjetas[i] = nueva
            return tarjetas
    tarjetas.append(nueva)
    return tarjetas


# ─────────────────────────────────────────────
#  Validación contra nfc_playlist.json
# ─────────────────────────────────────────────

def verificar_nfc_playlist(titulos_generados: List[str]) -> None:
    """
    Comprueba qué tarjetas generadas tienen entrada en nfc_playlist.json
    (necesaria para que nfc_reaccionar.py las reconozca).
    """
    print(f"\n{'═' * 52}")
    print("  Verificación de compatibilidad con nfc_reaccionar.py")
    print(f"{'─' * 52}")

    if not NFC_PLAYLIST.exists():
        print(f"  ⚠  No se encontró '{NFC_PLAYLIST.name}'.")
        print("  → Ejecuta 'nfc/nfc_config_gen.py' para asociar cada tarjeta física.")
        return

    try:
        with open(NFC_PLAYLIST, encoding="utf-8") as f:
            playlist = json.load(f)
    except (json.JSONDecodeError, ValueError):
        print(f"  ⚠  '{NFC_PLAYLIST.name}' está vacío o malformado.")
        print("  → Ejecuta 'nfc/nfc_config_gen.py' para inicializarlo.")
        return

    # Los nombres en nfc_playlist.json se guardan en el campo "nombre"
    nombres_registrados = {
        v.get("nombre", "").lower()
        for k, v in playlist.items()
        if not k.startswith("_")   # ignorar claves de config (_kodi, _moode…)
    }

    ok, pendientes = [], []
    for titulo in titulos_generados:
        if titulo.lower() in nombres_registrados:
            ok.append(titulo)
        else:
            pendientes.append(titulo)

    for t in ok:
        print(f"  ✓  '{t}' — registrada en nfc_playlist.json")

    for t in pendientes:
        print(f"  ✗  '{t}' — pendiente de asociar con una tarjeta NFC física")

    if pendientes:
        print()
        print("  Para registrar las tarjetas pendientes:")
        print("    python nfc/nfc_config_gen.py")
        print("  y acerca cada tarjeta al lector cuando se te pida.")


# ─────────────────────────────────────────────
#  CLI principal
# ─────────────────────────────────────────────

def safe_name(title: str) -> str:
    """Nombre seguro para fichero: título + fecha de hoy."""
    s    = re.sub(r"[^\w\s\-]", "", title).replace(" ", "_")
    base = s[:50].strip("_") or "tarjeta"
    return f"{base}_{date.today():%Y%m%d}"


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Genera tarjetas NFC de cine usando datos de TMDB"
    )
    parser.add_argument("-o", "--output",   help="Carpeta de salida (por defecto: docs/cine/)")
    parser.add_argument("-f", "--font",     help="Ruta a fuente TTF personalizada")
    parser.add_argument("--secretos",       default="secrets.enc.yaml",
                        help="Archivo SOPS de secretos")
    parser.add_argument("-v", "--verbose",  action="store_true")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # ── Credenciales ──
    secretos_path = PROYECTO_ROOT / args.secretos
    try:
        secretos = cargar_secretos(secretos_path)
    except Exception as e:
        logger.error(f"No se pudieron cargar los secretos:\n  {e}")
        sys.exit(1)

    api_key = secretos.get("TMDB_API_KEY", "")
    token   = secretos.get("TMDB_TOKEN", "")
    if not api_key and not token:
        logger.error(
            "Faltan credenciales TMDB. Añade TMDB_TOKEN o TMDB_API_KEY a los secretos.\n"
            "Obtén tus credenciales en https://www.themoviedb.org/settings/api"
        )
        sys.exit(1)

    try:
        cliente = TmdbClient(api_key=api_key, token=token)
    except ValueError as e:
        logger.error(e); sys.exit(1)

    # ── Carpeta de salida ──
    output = Path(args.output) if args.output else PROYECTO_ROOT / "docs" / "cine"
    output.mkdir(parents=True, exist_ok=True)

    generator  = VideoCardGenerator(font_path=args.font)
    tarjetas   = cargar_json_cine(JSON_CINE)
    generadas: List[str] = []

    print("Generador de Tarjetas NFC de Cine")
    print("Introduce un título por línea. Deja en blanco para terminar.\n")

    try:
        while True:
            info = buscar_en_tmdb(cliente)
            if info is None:
                break

            n  = safe_name(info.title)
            info.web_url = f"{WEB_BASE}cine.html#{web_slug(info.title)}"

            front_img = generator.generate_front(info)
            back_img  = generator.generate_back(info)
            fp = output / f"{n}_cara_A.png"
            bp = output / f"{n}_cara_B.png"
            front_img.save(fp, dpi=(DPI, DPI))
            back_img.save(bp, dpi=(DPI, DPI))

            tarjetas = actualizar_json_cine(tarjetas, info, fp, bp)
            generadas.append(info.title)

            print(f"  ✓ {fp.name}  |  {bp.name}")

    except KeyboardInterrupt:
        print("\nInterrumpido.")

    if not generadas:
        print("No se generó ninguna tarjeta.")
        return

    # ── Guardar JSON ──
    JSON_CINE.parent.mkdir(parents=True, exist_ok=True)
    with open(JSON_CINE, "w", encoding="utf-8") as f:
        json.dump(tarjetas, f, indent=2, ensure_ascii=False)
    logger.info(f"JSON actualizado: {JSON_CINE}")

    # ── Verificar compatibilidad con nfc_reaccionar.py ──
    verificar_nfc_playlist(generadas)

    print(f"\n  {len(generadas)} tarjeta(s) generada(s) en '{output}'")


if __name__ == "__main__":
    main()
