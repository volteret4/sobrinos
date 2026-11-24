#!/usr/bin/env python3
"""
Generador de Tarjetas para Artistas
Cara A: Foto del artista (pantalla completa) + nombre + estadísticas
Cara B: Collage de portadas de sus discos + QR (Wikipedia / GitHub Pages)

Uso:
    python nfc/nfc_generar_portada_artista.py /ruta/ARTISTA
    python nfc/nfc_generar_portada_artista.py /ruta/ARTISTA -o docs/portadas/musica/
"""

import io
import os
import re
import sys
import argparse
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import quote, urlparse
import logging

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    sys.exit("Error: instala Pillow — pip install Pillow")

try:
    import requests
    requests.packages.urllib3.disable_warnings()
except ImportError:
    sys.exit("Error: instala requests — pip install requests")

try:
    import qrcode
except ImportError:
    sys.exit("Error: instala qrcode — pip install qrcode[pil]")

try:
    from mutagen import File as MutagenFile
except ImportError:
    MutagenFile = None

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ── Dimensiones ──────────────────────────────────────────────────────────────
DPI = 300
CARD_WIDTH  = int(52 * DPI / 25.4)   # 613 px
CARD_HEIGHT = int(82 * DPI / 25.4)   # 969 px

GITHUB_PAGES_BASE = "https://volteret4.github.io/sobrinos"
AUDIO_EXTS = {".flac", ".mp3", ".ogg", ".m4a", ".aac", ".wav", ".ape", ".opus"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
COVER_NAMES = {"cover", "folder", "front", "album", "artwork", "albumart"}


# ── Tipos de datos ────────────────────────────────────────────────────────────
class AlbumEntry:
    def __init__(self, path: Path, title: str, year: str):
        self.path  = path
        self.title = title
        self.year  = year
        self.cover: Optional[Image.Image] = None


class ArtistInfo:
    def __init__(self, name: str):
        self.name       = name
        self.photo: Optional[Image.Image] = None
        self.albums: List[AlbumEntry]     = []
        self.year_range = ""
        self.wikipedia_url = ""


# ── Escaneo de carpeta ────────────────────────────────────────────────────────
_YEAR_RE = re.compile(r"[(\[]?(\d{4})[)\]]?")


def _has_audio(path: Path, depth: int = 2) -> bool:
    for entry in path.iterdir():
        if entry.is_file() and entry.suffix.lower() in AUDIO_EXTS:
            return True
        if entry.is_dir() and depth > 1 and _has_audio(entry, depth - 1):
            return True
    return False


def _find_cover_file(search_dirs: List[Path]) -> Optional[Image.Image]:
    for d in search_dirs:
        if not d.is_dir():
            continue
        try:
            files = list(d.iterdir())
        except PermissionError:
            continue
        # Priority: known cover names
        for f in files:
            if f.is_file() and f.stem.lower() in COVER_NAMES and f.suffix.lower() in IMAGE_EXTS:
                try:
                    return Image.open(f).convert("RGB")
                except Exception:
                    pass
        # Any image
        for f in files:
            if f.is_file() and f.suffix.lower() in IMAGE_EXTS:
                try:
                    return Image.open(f).convert("RGB")
                except Exception:
                    pass
    return None


def _extract_embedded_cover(audio_path: Path) -> Optional[Image.Image]:
    if MutagenFile is None:
        return None
    try:
        tags = MutagenFile(str(audio_path))
        if tags is None:
            return None
        # FLAC
        if hasattr(tags, "pictures") and tags.pictures:
            return Image.open(io.BytesIO(tags.pictures[0].data)).convert("RGB")
        # MP3 ID3
        if hasattr(tags, "tags") and tags.tags:
            for key in tags.tags.keys():
                if key.startswith("APIC"):
                    return Image.open(io.BytesIO(tags.tags[key].data)).convert("RGB")
        # M4A
        if "covr" in tags:
            return Image.open(io.BytesIO(bytes(tags["covr"][0]))).convert("RGB")
    except Exception:
        pass
    return None


def _find_cover(album_path: Path) -> Optional[Image.Image]:
    disc_dirs = [album_path] + [d for d in sorted(album_path.iterdir()) if d.is_dir()]
    cover = _find_cover_file(disc_dirs)
    if cover:
        return cover
    # Try embedded tag from first audio file found
    for d in disc_dirs:
        if not d.is_dir():
            continue
        for f in sorted(d.iterdir()):
            if f.is_file() and f.suffix.lower() in AUDIO_EXTS:
                cover = _extract_embedded_cover(f)
                if cover:
                    return cover
                break
    return None


def scan_artist_folder(artist_path: Path) -> ArtistInfo:
    info = ArtistInfo(artist_path.name)
    album_dirs = []
    for entry in sorted(artist_path.iterdir()):
        if not entry.is_dir():
            continue
        try:
            if _has_audio(entry):
                m = _YEAR_RE.search(entry.name)
                year = m.group(1) if m else ""
                album_dirs.append((year, entry))
        except PermissionError:
            pass

    album_dirs.sort(key=lambda x: x[0] or "9999")

    for year, path in album_dirs:
        # Strip year and bracketed sections from title
        title = re.sub(r"\s*[(\[].*?[)\]]\s*", " ", path.name).strip()
        album = AlbumEntry(path, title, year)
        logger.info(f"  Buscando portada: {path.name}")
        album.cover = _find_cover(path)
        if album.cover:
            logger.info(f"    ✓ Portada encontrada")
        else:
            logger.info(f"    — Sin portada")
        info.albums.append(album)

    years = [a.year for a in info.albums if a.year]
    if years:
        info.year_range = f"{years[0]}–{years[-1]}" if years[0] != years[-1] else years[0]

    return info


# ── Foto del artista ──────────────────────────────────────────────────────────
def fetch_artist_photo(artist_name: str) -> Tuple[Optional[Image.Image], str]:
    """Returns (photo_image, wikipedia_url). Tries Wikipedia search, then Last.fm."""
    logger.info(f"Buscando foto de '{artist_name}' en Wikipedia...")
    photo, wiki_url = _wikipedia_photo(artist_name)
    if photo:
        return photo, wiki_url

    logger.info("No encontrada en Wikipedia. Intentando Last.fm...")
    photo = _lastfm_photo(artist_name)
    if photo:
        return photo, wiki_url

    logger.warning("No se encontró foto automáticamente.")
    return None, wiki_url


def _wikipedia_photo(artist_name: str) -> Tuple[Optional[Image.Image], str]:
    try:
        search_url = (
            "https://en.wikipedia.org/w/api.php"
            f"?action=query&list=search&srsearch={quote(artist_name)}"
            "&srnamespace=0&srlimit=1&format=json&utf8=1"
        )
        resp = requests.get(search_url, timeout=8, headers={"User-Agent": "SobrinosNFC/1.0"})
        resp.raise_for_status()
        hits = resp.json().get("query", {}).get("search", [])
        if not hits:
            return None, ""

        title = hits[0]["title"]
        wiki_url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
        summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(title)}"
        resp2 = requests.get(summary_url, timeout=8, headers={"User-Agent": "SobrinosNFC/1.0"})
        resp2.raise_for_status()
        data = resp2.json()
        thumb = data.get("thumbnail", {}).get("source")
        if not thumb:
            return None, wiki_url

        img_resp = requests.get(thumb, timeout=8)
        img_resp.raise_for_status()
        photo = Image.open(io.BytesIO(img_resp.content)).convert("RGB")
        logger.info(f"✓ Foto del artista desde Wikipedia: {title}")
        return photo, wiki_url
    except Exception as e:
        logger.debug(f"Wikipedia artist photo failed: {e}")
        return None, ""


def _lastfm_photo(artist_name: str) -> Optional[Image.Image]:
    api_key = os.environ.get("LASTFM_API_KEY", "")
    if not api_key:
        return None
    try:
        url = (
            "https://ws.audioscrobbler.com/2.0/"
            f"?method=artist.getinfo&artist={quote(artist_name)}"
            f"&api_key={api_key}&format=json"
        )
        resp = requests.get(url, timeout=8)
        resp.raise_for_status()
        images = resp.json().get("artist", {}).get("image", [])
        for img in reversed(images):
            src = img.get("#text", "")
            if src and "2a96cbd8b46e442fc41c2b86b821562f" not in src:
                ir = requests.get(src, timeout=8)
                ir.raise_for_status()
                logger.info("✓ Foto del artista desde Last.fm")
                return Image.open(io.BytesIO(ir.content)).convert("RGB")
    except Exception as e:
        logger.debug(f"Last.fm artist photo failed: {e}")
    return None


# ── Fuentes ───────────────────────────────────────────────────────────────────
def load_fonts(custom_path: str = None) -> dict:
    candidates = []
    if custom_path and os.path.exists(custom_path):
        candidates.append(custom_path)
    candidates.extend([
        # Debian / Raspberry Pi OS
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        # Arch Linux
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/usr/share/fonts/liberation/LiberationSans-Bold.ttf",
        # macOS
        "/Library/Fonts/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ])
    try:
        out = subprocess.check_output(["fc-list", "--format=%{file}\n"], timeout=5).decode()
        for line in out.splitlines():
            line = line.strip()
            if line.lower().endswith((".ttf", ".otf")):
                candidates.append(line)
    except Exception:
        pass

    sizes = {"name": 76, "subtitle": 50, "info": 44, "small": 36}
    for path in candidates:
        if os.path.exists(path):
            try:
                fonts = {k: ImageFont.truetype(path, v) for k, v in sizes.items()}
                logger.info(f"✓ Fuentes desde: {path}")
                return fonts
            except Exception:
                continue

    logger.warning("⚠️  Sin fuente TTF — texto con fuente de sistema (pequeño)")
    d = ImageFont.load_default()
    return {k: d for k in sizes}


# ── Collage ───────────────────────────────────────────────────────────────────
def make_collage(covers: List[Image.Image], width: int, height: int,
                 gap: int = 3) -> Image.Image:
    n = len(covers)
    if n == 0:
        return Image.new("RGB", (width, height), (20, 20, 20))

    if n <= 2:
        cols = 1 if n == 1 else 2
    elif n <= 4:
        cols = 2
    elif n <= 9:
        cols = 3
    else:
        cols = 4

    cell = (width - gap * (cols - 1)) // cols
    rows_available = (height - gap * 10) // (cell + gap)
    max_show = cols * rows_available

    canvas = Image.new("RGB", (width, height), (15, 15, 15))
    for i, cover in enumerate(covers[:max_show]):
        col = i % cols
        row = i // cols
        x = col * (cell + gap)
        y = row * (cell + gap)
        thumb = cover.resize((cell, cell), Image.Resampling.LANCZOS)
        canvas.paste(thumb, (x, y))

    return canvas


# ── QR ────────────────────────────────────────────────────────────────────────
def make_qr(url: str, size: int,
            fg: tuple = (220, 220, 220),
            bg: tuple = (20, 20, 20)) -> Optional[Image.Image]:
    try:
        qr = qrcode.QRCode(version=1,
                           error_correction=qrcode.constants.ERROR_CORRECT_M,
                           box_size=10, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color=fg, back_color=bg)
        return img.get_image().resize((size, size), Image.Resampling.LANCZOS)
    except Exception as e:
        logger.warning(f"QR fallido: {e}")
        return None


# ── Generación de tarjetas ────────────────────────────────────────────────────
def _fit_text(draw, text: str, font, max_width: int) -> "ImageFont":
    """Return a font small enough to render text within max_width (single line)."""
    try:
        path = font.path
    except AttributeError:
        return font  # bitmap font — nothing we can do
    size = font.size
    while size > 20:
        bbox = draw.textbbox((0, 0), text, font=font)
        if bbox[2] - bbox[0] <= max_width:
            return font
        size = max(20, int(size * 0.90))
        font = ImageFont.truetype(path, size)
    return font


def generate_front_card(info: ArtistInfo, fonts: dict) -> Image.Image:
    """Foto completa (sin recorte) + overlay inferior con nombre y estadísticas."""
    bg = (25, 25, 25)
    image = Image.new("RGB", (CARD_WIDTH, CARD_HEIGHT), bg)

    if info.photo:
        photo = info.photo
        # Scale to fit entirely inside the card — no cropping
        ratio = min(CARD_WIDTH / photo.width, CARD_HEIGHT / photo.height)
        new_w = int(photo.width * ratio)
        new_h = int(photo.height * ratio)
        photo = photo.resize((new_w, new_h), Image.Resampling.LANCZOS)
        ox = (CARD_WIDTH - new_w) // 2
        oy = (CARD_HEIGHT - new_h) // 2
        image.paste(photo, (ox, oy))

    draw = ImageDraw.Draw(image)

    # Solid strip at bottom for text readability
    strip_h = 210
    draw.rectangle([(0, CARD_HEIGHT - strip_h), (CARD_WIDTH, CARD_HEIGHT)], fill=(0, 0, 0))

    margin = 18
    max_w = CARD_WIDTH - 2 * margin
    text_y = CARD_HEIGHT - strip_h + 12

    # Artist name — shrink font if the name is wider than the card
    name_text = info.name.upper()
    name_font = _fit_text(draw, name_text, fonts["name"], max_w)
    name_h = name_font.size + 10
    draw.text((margin, text_y), name_text, fill=(255, 255, 255), font=name_font)
    text_y += name_h + 8

    # Stats line
    parts = []
    if info.year_range:
        parts.append(info.year_range)
    n = len(info.albums)
    if n:
        parts.append(f"{n} disco{'s' if n != 1 else ''}")
    if parts:
        draw.text((margin, text_y), "  ·  ".join(parts),
                  fill=(180, 180, 180), font=fonts["info"])

    draw.rectangle([0, 0, CARD_WIDTH - 1, CARD_HEIGHT - 1], outline=(70, 70, 70), width=2)
    return image


def generate_back_card(info: ArtistInfo, fonts: dict,
                       custom_url: str = None) -> Image.Image:
    """Collage de portadas arriba + QR abajo."""
    qr_h = 180
    collage_h = CARD_HEIGHT - qr_h

    covers = [a.cover for a in info.albums if a.cover]
    collage = make_collage(covers, CARD_WIDTH, collage_h)

    image = Image.new("RGB", (CARD_WIDTH, CARD_HEIGHT), (15, 15, 15))
    image.paste(collage, (0, 0))

    draw = ImageDraw.Draw(image)
    draw.line([(0, collage_h), (CARD_WIDTH, collage_h)], fill=(50, 50, 50), width=2)

    url = custom_url or info.wikipedia_url or GITHUB_PAGES_BASE
    qr_size = 140
    qr_img = make_qr(url, qr_size)
    if qr_img:
        x = (CARD_WIDTH - qr_size) // 2
        y = collage_h + (qr_h - qr_size) // 2 - 12
        image.paste(qr_img, (x, y))

    draw.rectangle([0, 0, CARD_WIDTH - 1, CARD_HEIGHT - 1], outline=(70, 70, 70), width=2)
    return image


def _wrap_text(draw, text: str, font, max_width: int) -> List[str]:
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
    return lines


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    PROJECT_ROOT = Path(__file__).parent.parent
    default_out  = PROJECT_ROOT / "docs" / "portadas" / "musica"

    parser = argparse.ArgumentParser(description="Tarjeta NFC para artista musical")
    parser.add_argument("folder", help="Carpeta raíz del artista")
    parser.add_argument("-o", "--output", default=str(default_out),
                        help=f"Carpeta de salida (por defecto: {default_out})")
    parser.add_argument("--custom-url", help="URL personalizada para el QR")
    parser.add_argument("-f", "--font", help="Ruta a fuente TTF personalizada")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    artist_path = Path(args.folder)
    if not artist_path.is_dir():
        sys.exit(f"Error: {artist_path} no es una carpeta")

    output_path = Path(args.output)
    output_path.mkdir(parents=True, exist_ok=True)

    fonts = load_fonts(args.font)

    logger.info(f"Escaneando carpeta: {artist_path}")
    info = scan_artist_folder(artist_path)
    logger.info(f"Artista: {info.name} — {len(info.albums)} álbumes ({info.year_range})")

    info.photo, info.wikipedia_url = fetch_artist_photo(info.name)
    if not info.photo:
        path_input = input("Ruta a imagen del artista (Enter para omitir): ").strip()
        if path_input:
            try:
                info.photo = Image.open(path_input).convert("RGB")
                logger.info(f"✓ Imagen cargada: {path_input}")
            except Exception as e:
                logger.warning(f"No se pudo cargar la imagen: {e}")

    logger.info("Generando tarjetas...")
    front = generate_front_card(info, fonts)
    back  = generate_back_card(info, fonts, custom_url=args.custom_url)

    safe = re.sub(r'[^\w\s\-]', '_', info.name).strip()
    front_path = output_path / f"{safe}_artista_cara_A.png"
    back_path  = output_path / f"{safe}_artista_cara_B.png"

    front.save(front_path, dpi=(DPI, DPI))
    back.save(back_path,   dpi=(DPI, DPI))

    logger.info(f"Cara A → {front_path}")
    logger.info(f"Cara B → {back_path}")

    covers_found = sum(1 for a in info.albums if a.cover)
    logger.info(f"Portadas en collage: {covers_found}/{len(info.albums)}")


if __name__ == "__main__":
    main()
