#!/usr/bin/env python3
"""
Genera un PDF listo para imprimir con todas las tarjetas de cine.

- Evita duplicados: si hay varias versiones del mismo título (fechas distintas),
  usa la más reciente.
- Empaqueta las imágenes en páginas A4 (3 × 3 = 9 tarjetas por página)
  respetando el tamaño físico de 52 × 82 mm a 300 DPI.

Modos:
  Por defecto  – todas las tarjetas en orden (cara A y cara B mezcladas por película).
  --duplex     – cara A en páginas impares, cara B en páginas pares (listo para
                 impresión a doble cara girando por el borde corto).
                 Las páginas de cara B se voltean horizontalmente para que al
                 darle la vuelta al papel coincidan con las caras A.

Uso:
  python nfc/imprimir_tarjetas.py
  python nfc/imprimir_tarjetas.py --duplex
  python nfc/imprimir_tarjetas.py --entrada docs/cine --salida tarjetas.pdf
  python nfc/imprimir_tarjetas.py --marcas          # añade marcas de corte
"""

import argparse
import re
import sys
from datetime import date
from io import BytesIO
from pathlib import Path
from typing import List, Optional, Tuple

# ── Dependencias ──────────────────────────────────────────────────────────────
try:
    from PIL import Image
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.utils import ImageReader
except ImportError as exc:
    sys.exit(
        f"Error: {exc}\n"
        "Activa el entorno virtual:  source ~/Scripts/python_venv/bin/activate"
    )

# ── Constantes ────────────────────────────────────────────────────────────────
CARD_W_MM  = 52.0          # ancho tarjeta en mm
CARD_H_MM  = 82.0          # alto  tarjeta en mm
PAGE_W, PAGE_H = A4        # 595.28 × 841.89 pt  (210 × 297 mm)
COLS = 3
ROWS = 3
CARDS_PER_PAGE = COLS * ROWS

# Márgenes y gaps calculados para centrar exactamente COLS × ROWS tarjetas en A4
# gap_h: (210 - 3*52) / (3+1)  = 54/4 = 13.5 mm  (márgenes laterales iguales a los gaps)
# gap_v: (297 - 3*82) / (3+1)  = 51/4 = 12.75 mm
GAP_H_MM = (210.0 - COLS * CARD_W_MM) / (COLS + 1)   # ≈ 13.5 mm
GAP_V_MM = (297.0 - ROWS * CARD_H_MM) / (ROWS + 1)   # ≈ 12.75 mm

MARK_LEN_MM  = 3.0   # longitud de la marca de corte
MARK_GAP_MM  = 1.0   # separación entre tarjeta y marca
MARK_COLOR   = (0.7, 0.7, 0.7)   # gris claro

# Regex para extraer (titulo_base, fecha, cara) del nombre de fichero
# Ejemplo: "El_rey_león_20260310_cara_A.png"
_RE_CARD = re.compile(
    r"^(?P<titulo>.+?)_(?P<fecha>\d{8})_cara_(?P<cara>[AB])\.png$"
)


# ── Descubrimiento y deduplicación ────────────────────────────────────────────

def _normalizar(titulo: str) -> str:
    """Clave de agrupación: minúsculas, sin espacios múltiples."""
    return titulo.lower().strip()


def descubrir_tarjetas(
    carpeta: Path,
) -> List[Tuple[Optional[Path], Optional[Path]]]:
    """
    Devuelve lista de pares (cara_A, cara_B) para cada título único.
    Si hay varias fechas del mismo título, usa la más reciente.
    El orden es alfabético por título.
    """
    # titulo_normalizado → {fecha → {cara → path}}
    grupos: dict = {}
    for png in sorted(carpeta.glob("*.png")):
        m = _RE_CARD.match(png.name)
        if not m:
            continue
        titulo = _normalizar(m.group("titulo"))
        fecha  = m.group("fecha")
        cara   = m.group("cara")
        grupos.setdefault(titulo, {}).setdefault(fecha, {})[cara] = png

    pares = []
    for titulo in sorted(grupos):
        fechas = grupos[titulo]
        ultima = max(fechas)                   # fecha más reciente (YYYYMMDD)
        caras  = fechas[ultima]
        cara_a = caras.get("A")
        cara_b = caras.get("B")
        if cara_a or cara_b:
            pares.append((cara_a, cara_b))
    return pares


# ── Dibujo de una página ──────────────────────────────────────────────────────

def _coord(col: int, row: int) -> Tuple[float, float]:
    """
    Devuelve (x, y) en puntos reportlab de la esquina inferior-izquierda
    de la celda (col, row). row=0 es la fila superior.
    """
    x = (GAP_H_MM + col * (CARD_W_MM + GAP_H_MM)) * mm
    # reportlab: y=0 abajo. row=0 → parte superior → y más alta
    y_top = PAGE_H - (GAP_V_MM + row * (CARD_H_MM + GAP_V_MM)) * mm
    y = y_top - CARD_H_MM * mm
    return x, y


def _draw_image(c: rl_canvas.Canvas, img_path: Path, x: float, y: float) -> None:
    img = Image.open(img_path).convert("RGB")
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    c.drawImage(
        ImageReader(buf),
        x, y,
        width=CARD_W_MM * mm,
        height=CARD_H_MM * mm,
        preserveAspectRatio=True,
        anchor="c",
    )


def _draw_cut_marks(c: rl_canvas.Canvas, x: float, y: float) -> None:
    """Marca de corte en las cuatro esquinas de una tarjeta."""
    c.setStrokeColorRGB(*MARK_COLOR)
    c.setLineWidth(0.3)
    g  = MARK_GAP_MM  * mm
    ln = MARK_LEN_MM  * mm
    w  = CARD_W_MM * mm
    h  = CARD_H_MM * mm
    # Esquinas: (cx, cy) = posición de la esquina, (dx_h, dx_v) = dirección
    corners = [
        (x,     y,     +1, +1),   # inferior-izquierda
        (x + w, y,     -1, +1),   # inferior-derecha
        (x,     y + h, +1, -1),   # superior-izquierda
        (x + w, y + h, -1, -1),   # superior-derecha
    ]
    for cx, cy, dh, dv in corners:
        # horizontal
        c.line(cx + dh * g, cy, cx + dh * (g + ln), cy)
        # vertical
        c.line(cx, cy + dv * g, cx, cy + dv * (g + ln))


def _draw_page(
    c: rl_canvas.Canvas,
    imagenes: List[Optional[Path]],
    marcas: bool,
) -> None:
    """Dibuja hasta CARDS_PER_PAGE imágenes en una página A4."""
    for idx, img_path in enumerate(imagenes[:CARDS_PER_PAGE]):
        col = idx % COLS
        row = idx // COLS
        x, y = _coord(col, row)
        if img_path and img_path.exists():
            _draw_image(c, img_path, x, y)
        if marcas:
            _draw_cut_marks(c, x, y)


# ── Modo normal ───────────────────────────────────────────────────────────────

def generar_normal(
    c: rl_canvas.Canvas,
    pares: List[Tuple[Optional[Path], Optional[Path]]],
    marcas: bool,
) -> None:
    """
    Intercala cara A y cara B de cada película:
      película 1 cara A, película 1 cara B, película 2 cara A, …
    Las agrupa de 9 en 9 por página.
    """
    todas: List[Optional[Path]] = []
    for cara_a, cara_b in pares:
        todas.append(cara_a)
        todas.append(cara_b)

    paginas = _paginar(todas)
    for i, pagina in enumerate(paginas):
        if i > 0:
            c.showPage()
        _draw_page(c, pagina, marcas)


# ── Modo duplex ───────────────────────────────────────────────────────────────

def _voltear_horizontalmente(img_path: Path) -> BytesIO:
    """Devuelve la imagen volteada horizontalmente como BytesIO."""
    img = Image.open(img_path).convert("RGB").transpose(Image.FLIP_LEFT_RIGHT)
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def _draw_image_buf(
    c: rl_canvas.Canvas, buf: BytesIO, x: float, y: float
) -> None:
    c.drawImage(
        ImageReader(buf),
        x, y,
        width=CARD_W_MM * mm,
        height=CARD_H_MM * mm,
        preserveAspectRatio=True,
        anchor="c",
    )


def generar_duplex(
    c: rl_canvas.Canvas,
    pares: List[Tuple[Optional[Path], Optional[Path]]],
    marcas: bool,
) -> None:
    """
    Páginas impares → cara A.
    Páginas pares   → cara B volteada horizontalmente.
    Las caras B se voltean para que al imprimir a doble cara
    (girando por el borde corto) coincidan con las caras A.
    """
    caras_a: List[Optional[Path]] = [p[0] for p in pares]
    caras_b: List[Optional[Path]] = [p[1] for p in pares]

    pags_a = _paginar(caras_a)
    pags_b = _paginar(caras_b)

    # Intercalar página frontal y página trasera
    num_pags = max(len(pags_a), len(pags_b))
    for i in range(num_pags):
        # Cara A
        if i > 0:
            c.showPage()
        pag_a = pags_a[i] if i < len(pags_a) else []
        _draw_page(c, pag_a, marcas)

        # Cara B (volteada)
        c.showPage()
        pag_b = pags_b[i] if i < len(pags_b) else []
        # Dibujar volteadas
        for idx, img_path in enumerate(pag_b[:CARDS_PER_PAGE]):
            col = idx % COLS
            row = idx // COLS
            x, y = _coord(col, row)
            if img_path and img_path.exists():
                buf = _voltear_horizontalmente(img_path)
                _draw_image_buf(c, buf, x, y)
            if marcas:
                _draw_cut_marks(c, x, y)


# ── Utilidades ────────────────────────────────────────────────────────────────

def _paginar(items: list) -> List[list]:
    return [items[i : i + CARDS_PER_PAGE] for i in range(0, len(items), CARDS_PER_PAGE)]


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Genera PDF de tarjetas de cine para imprimir"
    )
    parser.add_argument(
        "--entrada", "-i",
        default="docs/cine",
        help="Carpeta con los PNG de las tarjetas (por defecto: docs/cine)",
    )
    parser.add_argument(
        "--salida", "-o",
        default=f"tarjetas_cine_{date.today().strftime('%Y%m%d')}.pdf",
        help="Ruta del PDF de salida",
    )
    parser.add_argument(
        "--duplex", action="store_true",
        help="Modo duplex: cara A en páginas impares, cara B en pares (volteada)",
    )
    parser.add_argument(
        "--marcas", action="store_true",
        help="Añadir marcas de corte en las esquinas de cada tarjeta",
    )
    args = parser.parse_args()

    carpeta = Path(args.entrada)
    if not carpeta.exists():
        sys.exit(f"Error: no se encontró la carpeta '{carpeta}'")

    pares = descubrir_tarjetas(carpeta)
    if not pares:
        sys.exit(f"No se encontraron tarjetas en '{carpeta}'")

    print(f"Tarjetas encontradas: {len(pares)}")
    for cara_a, cara_b in pares:
        nombre = (cara_a or cara_b).stem.rsplit("_cara_", 1)[0]
        a = "✓" if cara_a else "✗"
        b = "✓" if cara_b else "✗"
        print(f"  [{a}A {b}B] {nombre}")

    tarjetas_totales = sum(bool(a) + bool(b) for a, b in pares)
    if args.duplex:
        paginas = 2 * -(-len(pares) // CARDS_PER_PAGE)   # ceil * 2 (A+B)
    else:
        paginas = -(-tarjetas_totales // CARDS_PER_PAGE)  # ceil
    print(f"\nTotal imágenes: {tarjetas_totales}  →  {paginas} página(s) A4")

    salida = Path(args.salida)
    c = rl_canvas.Canvas(str(salida), pagesize=A4)
    c.setTitle("Tarjetas de cine")
    c.setAuthor("sobrinos")

    if args.duplex:
        generar_duplex(c, pares, args.marcas)
    else:
        generar_normal(c, pares, args.marcas)

    c.save()
    print(f"\n✓ PDF guardado en '{salida}'")
    if args.duplex:
        print("  Imprime a doble cara girando por el borde CORTO.")


if __name__ == "__main__":
    main()
