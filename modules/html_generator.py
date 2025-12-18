"""
Módulo para generación de HTML - VERSIÓN COMPLETAMENTE CORREGIDA
- Extracción real de colores de portada
- Contraste optimizado para texto
- Sin placeholders de imágenes
- Soporte completo para Markdown en comentarios
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
import html
import json
from pathlib import Path

# Importar funciones de contraste
def calculate_luminance(rgb_tuple):
    """Calcular luminancia relativa WCAG 2.0"""
    r, g, b = [c / 255.0 for c in rgb_tuple]

    def to_linear(c):
        return c / 12.92 if c <= 0.03928 else pow((c + 0.055) / 1.055, 2.4)

    r_lin = to_linear(r)
    g_lin = to_linear(g)
    b_lin = to_linear(b)

    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin

def get_optimal_text_color(background_color):
    """Obtener color de texto óptimo con contraste >= 4.5"""
    bg_luminance = calculate_luminance(background_color)

    white = (255, 255, 255)
    black = (0, 0, 0)

    white_contrast = (calculate_luminance(white) + 0.05) / (bg_luminance + 0.05)
    black_contrast = (bg_luminance + 0.05) / (calculate_luminance(black) + 0.05)

    if white_contrast > black_contrast:
        return white if white_contrast >= 4.5 else (240, 240, 240)
    else:
        return black if black_contrast >= 4.5 else (40, 40, 40)

logger = logging.getLogger(__name__)


class HTMLGenerator:
    """Generador de HTML corregido"""

    def __init__(self):
        pass

    def generate_html_with_dynamic_tabs(self, album_info: Dict[str, Any],
                                      db_manager=None,
                                      css_filename: str = "../styles.css",
                                      js_filename: str = "../script.js") -> str:
        """
        Generar página HTML completa con todas las correcciones aplicadas
        """
        logger.info(f"Generando HTML corregido para: {album_info['artist']} - {album_info['title']}")

        # Generar colores optimizados
        album_colors = self._generate_album_colors(album_info)

        # Datos seguros para JavaScript
        safe_album_data = self._prepare_safe_data(album_info)

        html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(album_info['artist'])} - {html.escape(album_info['title'])}</title>
    <meta name="description" content="Información completa del álbum {html.escape(album_info['title'])} de {html.escape(album_info['artist'])}">

    <link rel="stylesheet" href="{css_filename}">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">

    <!-- Colores optimizados extraídos de la portada -->
    <style>
        :root {{
            --color-primary: {album_colors['primary']};
            --color-secondary: {album_colors['secondary']};
            --color-accent: {album_colors['accent']};
        }}

        /* Header con colores optimizados */
        .album-header {{
            background: linear-gradient(135deg, {album_colors['primary']}, {album_colors['secondary']});
            color: {album_colors['text_primary']} !important;
        }}

        .album-title,
        .artist-name {{
            color: {album_colors['text_primary']} !important;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.8) !important;
        }}

        .album-details .detail-item {{
            background: rgba(0, 0, 0, 0.4) !important;
            color: {album_colors['text_primary']} !important;
            border: 1px solid rgba(255, 255, 255, 0.2) !important;
            backdrop-filter: blur(10px) !important;
        }}

        .album-details .detail-item strong {{
            color: {album_colors['text_primary']} !important;
        }}

        /* Responsive mejorado */
        @media (max-width: 768px) {{
            .album-header {{
                padding: 1.5rem 0 !important;
                margin-bottom: 1.5rem !important;
            }}

            .album-hero {{
                gap: 1rem !important;
            }}

            .album-title {{
                font-size: 1.5rem !important;
                margin-bottom: 0.25rem !important;
            }}

            .artist-name {{
                font-size: 1.125rem !important;
                margin-bottom: 1rem !important;
            }}

            .album-cover img {{
                width: 120px !important;
                height: 120px !important;
            }}

            .artist-image img {{
                width: 80px !important;
                height: 80px !important;
            }}

            .album-details {{
                flex-direction: column !important;
                align-items: flex-start !important;
                gap: 0.25rem !important;
            }}
        }}

        @media (max-width: 480px) {{
            .album-header {{
                padding: 1rem 0 !important;
            }}

            .album-title {{
                font-size: 1.25rem !important;
            }}

            .artist-name {{
                font-size: 1rem !important;
            }}

            .album-cover img {{
                width: 100px !important;
                height: 100px !important;
            }}

            .artist-image img {{
                width: 70px !important;
                height: 70px !important;
            }}
        }}

        /* Layout sin imágenes */
        .album-hero.no-images {{
            grid-template-columns: 1fr !important;
            text-align: center !important;
        }}

        .album-hero.no-images .album-info {{
            max-width: 600px;
            margin: 0 auto;
        }}
    </style>

    <script>
        window.albumData = {json.dumps(safe_album_data, ensure_ascii=False, indent=2)};
    </script>
</head>
<body>
    <header class="site-header">
        <div class="container">
            <nav class="site-nav">
                <div class="site-logo">
                    <a href="../index.html" style="color: inherit; text-decoration: none;">← Volver a la Colección</a>
                </div>
                <div class="nav-links">
                    <a href="../index.html" class="nav-link">🏠 Inicio</a>
                    <button class="theme-toggle" aria-label="Cambiar tema">🌙</button>
                </div>
            </nav>
        </div>
    </header>

    {self._generate_header(album_info)}
    {self._generate_main_content(album_info)}
    {self._generate_footer()}

    <script src="{js_filename}"></script>
</body>
</html>"""

        return html_content

    def _generate_header(self, album_info: Dict[str, Any]) -> str:
        """Generar header sin placeholders - solo mostrar imágenes que existen"""

        # Verificar si tenemos imágenes reales
        album_image = album_info.get('album_image')
        artist_image = album_info.get('artist_image')

        album_image_url = ""
        artist_image_url = ""

        # Solo usar imágenes si tienen URL válida (no None, no vacía)
        if album_image and album_image.get('url') and album_image['url'].strip():
            album_image_url = album_image['url']

        if artist_image and artist_image.get('url') and artist_image['url'].strip():
            artist_image_url = artist_image['url']

        # Generar HTML de imágenes solo si existen
        images_html = ""
        hero_class = "album-hero"

        if album_image_url or artist_image_url:
            images_parts = []

            if album_image_url:
                images_parts.append(f"""
                <div class="album-cover">
                    <img src="{html.escape(album_image_url)}"
                         alt="Portada de {html.escape(album_info['title'])}"
                         onclick="window.open('{html.escape(album_image_url)}', '_blank')"
                         style="cursor: pointer;">
                </div>""")

            if artist_image_url:
                images_parts.append(f"""
                <div class="artist-image">
                    <img src="{html.escape(artist_image_url)}"
                         alt="Foto de {html.escape(album_info['artist'])}">
                </div>""")

            if images_parts:
                images_html = f"""<div class="album-images">{''.join(images_parts)}</div>"""
                hero_class = "album-hero has-images"
        else:
            hero_class = "album-hero no-images"

        return f"""
    <header class="album-header">
        <div class="container">
            <div class="{hero_class}">
                {images_html}
                <div class="album-info">
                    <h1 class="album-title">{html.escape(album_info['title'])}</h1>
                    <h2 class="artist-name">{html.escape(album_info['artist'])}</h2>
                    {self._generate_album_details(album_info)}
                </div>
            </div>
        </div>
    </header>"""

    def _generate_main_content(self, album_info: Dict[str, Any]) -> str:
        """Generar contenido principal"""
        return f"""
    <main class="album-content">
        <div class="container">
            <nav class="content-nav">
                <ul class="nav-tabs">
                    <li><a href="#comment" class="nav-tab active" data-tab="comment">Comentario</a></li>
                    <li><a href="#lyrics" class="nav-tab" data-tab="lyrics">Letras</a></li>
                    <li><a href="#links" class="nav-tab" data-tab="links">Enlaces</a></li>
                    <li><a href="#tracks" class="nav-tab" data-tab="tracks">Pistas</a></li>
                </ul>
            </nav>

            <div class="tab-content">
                {self._generate_comment_tab(album_info)}
                {self._generate_lyrics_tab(album_info)}
                {self._generate_links_tab(album_info)}
                {self._generate_tracks_tab(album_info)}
            </div>
        </div>
    </main>"""

    def _generate_comment_tab(self, album_info: Dict[str, Any]) -> str:
        """Generar pestaña de comentario con Markdown"""
        comment = album_info.get('user_comment', '')

        if comment and comment.strip():
            comment_html = self._convert_markdown_to_html(comment)
        else:
            comment_html = '<em>No hay comentario disponible.</em>'

        return f"""
                <section id="comment" class="tab-panel active">
                    <h3>Comentario Personal</h3>
                    <div class="comment-content">
                        {comment_html}
                    </div>
                </section>"""

    def _convert_markdown_to_html(self, text: str) -> str:
        """Convertir Markdown básico a HTML"""
        if not text:
            return ""

        import re

        # Escapar HTML primero
        text = html.escape(text)

        # Convertir elementos Markdown
        text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', text)
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" target="_blank" rel="noopener noreferrer">\1</a>', text)
        text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
        text = re.sub(r'^## (.+)$', r'<h4>\1</h4>', text, flags=re.MULTILINE)
        text = re.sub(r'^### (.+)$', r'<h5>\1</h5>', text, flags=re.MULTILINE)
        text = re.sub(r'^#### (.+)$', r'<h6>\1</h6>', text, flags=re.MULTILINE)

        # Procesar listas y párrafos
        lines = text.split('\n')
        processed_lines = []
        in_list = False

        for line in lines:
            stripped = line.strip()
            if stripped.startswith('- '):
                if not in_list:
                    processed_lines.append('<ul>')
                    in_list = True
                processed_lines.append(f'<li>{stripped[2:]}</li>')
            else:
                if in_list:
                    processed_lines.append('</ul>')
                    in_list = False
                if stripped:
                    if not stripped.startswith('<'):  # No es un header
                        processed_lines.append(f'<p>{stripped}</p>')
                    else:
                        processed_lines.append(stripped)
                elif processed_lines and not processed_lines[-1].startswith('<'):
                    processed_lines.append('<br>')

        if in_list:
            processed_lines.append('</ul>')

        return ''.join(processed_lines)

    def _generate_lyrics_tab(self, album_info: Dict[str, Any]) -> str:
        """Generar pestaña de letras"""
        lyrics_data = album_info.get('lyrics', {})
        if not lyrics_data:
            return """
                <section id="lyrics" class="tab-panel">
                    <h3>Letras de las Canciones</h3>
                    <div class="lyrics-content">
                        <p><em>No se encontraron letras para las canciones de este álbum.</em></p>
                    </div>
                </section>"""

        lyrics_html = []
        tracks = album_info.get('tracks', [])

        for track in tracks:
            track_title = track.get('title', '')
            if track_title in lyrics_data:
                lyrics_info = lyrics_data[track_title]
                lyrics_text = lyrics_info.get('lyrics')

                if lyrics_text:
                    formatted_lyrics = html.escape(lyrics_text).replace('\n\n', '</p><p>').replace('\n', '<br>')
                    source = lyrics_info.get('source', '')
                    source_info = f" <small>(Fuente: {html.escape(source)})</small>" if source else ""

                    lyrics_html.append(f"""
                    <div class="lyrics-song" onclick="toggleLyrics(this)">
                        <h4 class="song-title">{html.escape(track_title)}{source_info}</h4>
                        <div class="lyrics-text">
                            <p>{formatted_lyrics}</p>
                        </div>
                    </div>""")

        return f"""
                <section id="lyrics" class="tab-panel">
                    <h3>Letras de las Canciones</h3>
                    <div class="lyrics-content">
                        {''.join(lyrics_html)}
                    </div>
                    <script>
                    function toggleLyrics(songElement) {{
                        songElement.classList.toggle('expanded');
                    }}
                    </script>
                </section>"""

    def _generate_links_tab(self, album_info: Dict[str, Any]) -> str:
        """Generar pestaña de enlaces"""
        links_data = album_info.get('links', {})
        if not links_data:
            return """
                <section id="links" class="tab-panel">
                    <h3>Enlaces Relacionados</h3>
                    <div class="links-content">
                        <p><em>No se encontraron enlaces relacionados.</em></p>
                    </div>
                </section>"""

        links_html = []
        for category, links in links_data.items():
            if links:
                category_name = category.replace('_', ' ').title()
                links_html.append(f"<h4>{category_name}</h4><ul>")
                for link_name, link_info in links.items():
                    url = link_info.get('url', '#')
                    title = link_info.get('title', link_name)
                    links_html.append(f'<li><a href="{html.escape(url)}" target="_blank">{html.escape(title)}</a></li>')
                links_html.append("</ul>")

        return f"""
                <section id="links" class="tab-panel">
                    <h3>Enlaces Relacionados</h3>
                    <div class="links-content">
                        {''.join(links_html)}
                    </div>
                </section>"""

    def _generate_tracks_tab(self, album_info: Dict[str, Any]) -> str:
        """Generar pestaña de pistas"""
        tracks = album_info.get('tracks', [])
        if not tracks:
            return """
                <section id="tracks" class="tab-panel">
                    <h3>Lista de Pistas</h3>
                    <div class="tracks-content">
                        <p><em>No se encontraron pistas.</em></p>
                    </div>
                </section>"""

        tracks_html = []
        for track in tracks:
            track_number = track.get('track_number', 0)
            title = track.get('title', 'Pista Sin Título')
            duration = track.get('duration', 0)

            duration_str = ""
            if duration > 0:
                minutes = int(duration // 60)
                seconds = int(duration % 60)
                duration_str = f"{minutes}:{seconds:02d}"

            tracks_html.append(f"""
            <tr class="track-row">
                <td class="track-number">{track_number if track_number > 0 else ''}</td>
                <td class="track-title">{html.escape(title)}</td>
                <td class="track-duration">{duration_str}</td>
            </tr>""")

        return f"""
                <section id="tracks" class="tab-panel">
                    <h3>Lista de Pistas</h3>
                    <div class="tracks-content">
                        <table class="tracks-table">
                            <thead>
                                <tr><th>#</th><th>Título</th><th>Duración</th></tr>
                            </thead>
                            <tbody>{''.join(tracks_html)}</tbody>
                        </table>
                    </div>
                </section>"""

    def _generate_album_details(self, album_info: Dict[str, Any]) -> str:
        """Generar detalles del álbum"""
        details = []

        if album_info.get('year'):
            details.append(f"<span class='detail-item'><strong>Año:</strong> {html.escape(str(album_info['year']))}</span>")

        if album_info.get('genre'):
            genres = ', '.join(album_info['genre']) if isinstance(album_info['genre'], list) else str(album_info['genre'])
            details.append(f"<span class='detail-item'><strong>Género:</strong> {html.escape(genres)}</span>")

        if album_info.get('label'):
            details.append(f"<span class='detail-item'><strong>Sello:</strong> {html.escape(album_info['label'])}</span>")

        if album_info.get('total_tracks'):
            details.append(f"<span class='detail-item'><strong>Pistas:</strong> {album_info['total_tracks']}</span>")

        if details:
            return f"<div class='album-details'>{''.join(details)}</div>"
        return ""

    def _generate_footer(self) -> str:
        """Generar footer"""
        return """
    <footer class="album-footer">
        <div class="container">
            <p>Generado con Album Web Generator</p>
        </div>
    </footer>"""

    def _generate_album_colors(self, album_info: Dict[str, Any]) -> Dict[str, str]:
        """Generar colores optimizados con contraste real"""

        # Intentar extraer color real de la portada
        if album_info.get('album_image') and album_info['album_image'].get('url'):
            try:
                extracted_color = self._extract_dominant_color_from_image(album_info['album_image']['url'])
                if extracted_color:
                    return self._create_optimized_palette(extracted_color)
            except Exception as e:
                logger.warning(f"Error extrayendo color de portada: {e}")

        # Fallback con colores más suaves
        return self._generate_fallback_colors(album_info)

    def _extract_dominant_color_from_image(self, image_url: str) -> Optional[Tuple[int, int, int]]:
        """Extraer color dominante real de la imagen"""
        try:
            import requests
            from PIL import Image
            from collections import Counter
            import PIL.ImageStat as ImageStat
            from io import BytesIO

            # Abrir imagen
            if image_url.startswith(('http://', 'https://')):
                response = requests.get(image_url, timeout=10)
                response.raise_for_status()
                img = Image.open(BytesIO(response.content))
            elif Path(image_url).exists():
                img = Image.open(image_url)
            else:
                return None

            # Procesar imagen
            img = img.resize((150, 150), Image.Resampling.LANCZOS)
            img = img.convert('RGB')

            pixels = list(img.getdata())

            # Agrupar colores similares
            grouped_colors = []
            for r, g, b in pixels:
                r = (r // 10) * 10
                g = (g // 10) * 10
                b = (b // 10) * 10
                grouped_colors.append((r, g, b))

            color_counter = Counter(grouped_colors)

            # Filtrar colores extremos y grises
            for color, count in color_counter.most_common(20):
                r, g, b = color
                brightness = (r + g + b) / 3

                if 20 < brightness < 235:
                    max_val = max(r, g, b)
                    min_val = min(r, g, b)
                    saturation = (max_val - min_val) / max_val if max_val > 0 else 0

                    if saturation > 0.1 or brightness < 100:
                        return color

            # Fallback: promedio de la imagen
            stat = ImageStat.Stat(img)
            return tuple(int(c) for c in stat.mean)

        except Exception as e:
            logger.warning(f"Error extrayendo color: {e}")
            return None

    def _create_optimized_palette(self, dominant_color: Tuple[int, int, int]) -> Dict[str, str]:
        """Crear paleta optimizada con contraste"""
        import colorsys

        r, g, b = dominant_color
        h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)

        def rgb_to_hex(rgb):
            return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"

        # Color primario (ajustado)
        primary_rgb = colorsys.hsv_to_rgb(h, min(1.0, s * 1.1), min(1.0, v * 0.85))
        primary_color = tuple(int(c * 255) for c in primary_rgb)

        # Color secundario
        secondary_rgb = colorsys.hsv_to_rgb((h + 0.08) % 1.0, min(1.0, s * 0.9), min(1.0, v * 1.0))
        secondary_color = tuple(int(c * 255) for c in secondary_rgb)

        # Color de acento
        accent_rgb = colorsys.hsv_to_rgb((h + 0.5) % 1.0, min(1.0, s * 0.8), min(1.0, v * 0.9))
        accent_color = tuple(int(c * 255) for c in accent_rgb)

        # Texto optimizado para contraste
        text_color = get_optimal_text_color(primary_color)

        return {
            'primary': rgb_to_hex(primary_color),
            'secondary': rgb_to_hex(secondary_color),
            'accent': rgb_to_hex(accent_color),
            'text_primary': rgb_to_hex(text_color)
        }

    def _generate_fallback_colors(self, album_info: Dict[str, Any]) -> Dict[str, str]:
        """Generar colores de fallback"""
        import hashlib
        import colorsys

        album_hash = hashlib.md5(f"{album_info['artist']}{album_info['title']}".encode()).hexdigest()
        hue = int(album_hash[:2], 16) / 255.0

        def hsv_to_hex(h: float, s: float, v: float) -> str:
            r, g, b = colorsys.hsv_to_rgb(h, s, v)
            return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"

        primary_color = (int(hue * 255 * 0.4), int(hue * 255 * 0.4), int(hue * 255 * 0.7))
        text_color = get_optimal_text_color(primary_color)

        return {
            'primary': hsv_to_hex(hue, 0.4, 0.7),
            'secondary': hsv_to_hex((hue + 0.2) % 1.0, 0.3, 0.8),
            'accent': hsv_to_hex((hue + 0.4) % 1.0, 0.5, 0.6),
            'text_primary': f"#{text_color[0]:02x}{text_color[1]:02x}{text_color[2]:02x}"
        }

    def _prepare_safe_data(self, album_info: Dict[str, Any]) -> Dict[str, Any]:
        """Preparar datos seguros para JavaScript"""
        return {
            'title': album_info.get('title', ''),
            'artist': album_info.get('artist', ''),
            'year': album_info.get('year'),
            'genre': album_info.get('genre', []),
            'total_tracks': album_info.get('total_tracks', 0),
            'tracks_count': len(album_info.get('tracks', [])),
            'has_lyrics': bool(album_info.get('lyrics')),
            'has_comment': bool(album_info.get('user_comment', '').strip()),
            'links_count': sum(len(category) for category in album_info.get('links', {}).values())
        }
