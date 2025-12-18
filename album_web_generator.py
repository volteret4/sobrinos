#!/usr/bin/env python3
"""
Generador de Páginas Web de Álbumes - VERSIÓN SIMPLE PERO FUNCIONAL
"""

import os
import sys
import argparse
import tkinter as tk
from tkinter import scrolledtext, simpledialog, messagebox
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import logging
import json
import urllib.parse

# Importar módulos del proyecto
from modules.database_manager import DatabaseManager
from modules.image_finder import ImageFinder
from modules.lyrics_finder import LyricsFinder
from modules.link_finder import LinkFinder
from modules.html_generator import HTMLGenerator
from modules.album_processor import AlbumProcessor

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class AlbumWebGenerator:
    """Generador simple pero funcional"""

    def __init__(self, db_path: Optional[str] = None):
        self.db_manager = DatabaseManager(db_path) if db_path else None
        self.image_finder = ImageFinder()
        self.lyrics_finder = LyricsFinder()
        self.link_finder = LinkFinder(self.db_manager)
        self.html_generator = HTMLGenerator()
        self.album_processor = AlbumProcessor()

    def get_user_comment(self, album_title: str, artist: str) -> str:
        """Diálogo simple pero funcional para comentarios"""

        try:
            logger.info("Abriendo diálogo de comentario...")

            # Crear ventana root
            root = tk.Tk()
            root.title("Comentario del Álbum")
            root.geometry("800x600")

            # Centrar ventana
            root.update_idletasks()
            x = (root.winfo_screenwidth() - root.winfo_width()) // 2
            y = (root.winfo_screenheight() - root.winfo_height()) // 2
            root.geometry(f"+{x}+{y}")

            result = ""

            def save_comment():
                nonlocal result
                result = text_widget.get("1.0", tk.END).strip()
                logger.info(f"Comentario guardado ({len(result)} caracteres)")
                root.quit()

            def cancel_comment():
                nonlocal result
                result = ""
                logger.info("Comentario cancelado")
                root.quit()

            # Frame principal
            main_frame = tk.Frame(root, padx=20, pady=20)
            main_frame.pack(fill=tk.BOTH, expand=True)

            # Título
            title_text = f"Comentario para: {artist} - {album_title}"
            title_label = tk.Label(
                main_frame,
                text=title_text,
                font=("Arial", 12, "bold"),
                wraplength=700
            )
            title_label.pack(pady=(0, 10), anchor="w")

            # Instrucciones
            instructions = tk.Label(
                main_frame,
                text="Puedes usar Markdown: **negrita**, *cursiva*, `código`, ## título, - lista, [enlace](url)",
                font=("Arial", 9),
                fg="gray",
                wraplength=700
            )
            instructions.pack(pady=(0, 10), anchor="w")

            # Área de texto
            text_frame = tk.Frame(main_frame)
            text_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

            text_widget = scrolledtext.ScrolledText(
                text_frame,
                wrap=tk.WORD,
                width=80,
                height=25,
                font=("Consolas", 11)
            )
            text_widget.pack(fill=tk.BOTH, expand=True)

            # Frame de botones
            button_frame = tk.Frame(main_frame)
            button_frame.pack(fill=tk.X)

            # Botones
            cancel_btn = tk.Button(
                button_frame,
                text="Cancelar",
                command=cancel_comment,
                padx=20,
                pady=8
            )
            cancel_btn.pack(side=tk.RIGHT, padx=(5, 0))

            save_btn = tk.Button(
                button_frame,
                text="Guardar",
                command=save_comment,
                padx=20,
                pady=8,
                bg="#4CAF50",
                fg="white",
                font=("Arial", 9, "bold")
            )
            save_btn.pack(side=tk.RIGHT)

            # Atajos de teclado
            root.bind('<Control-Return>', lambda e: save_comment())
            root.bind('<Escape>', lambda e: cancel_comment())

            # Configurar cierre de ventana
            root.protocol("WM_DELETE_WINDOW", cancel_comment)

            # Foco en el área de texto
            text_widget.focus_set()

            logger.info("Diálogo abierto correctamente")

            # Ejecutar bucle principal
            root.mainloop()

            # Limpiar
            try:
                root.destroy()
            except:
                pass

            return result

        except Exception as e:
            logger.error(f"Error en diálogo: {e}")

            # Fallback ultra simple
            try:
                root = tk.Tk()
                root.withdraw()
                comment = simpledialog.askstring(
                    "Comentario",
                    f"Comentario para {artist} - {album_title}:",
                    parent=root
                )
                root.destroy()
                return comment or ""
            except Exception as e2:
                logger.error(f"Error en fallback: {e2}")
                return ""

    def process_album(self, folder_path: str, output_dir: str) -> Dict[str, Any]:
        """Procesar álbum"""
        logger.info(f"🎵 Procesando álbum: {folder_path}")

        # 1. Extraer información básica
        album_info = self.album_processor.extract_album_info(folder_path)
        logger.info(f"📀 Álbum encontrado: {album_info['artist']} - {album_info['title']}")

        # 2. Obtener comentario del usuario
        logger.info("💬 Solicitando comentario del usuario...")
        try:
            album_info['user_comment'] = self.get_user_comment(
                album_info['title'],
                album_info['artist']
            )

            if album_info['user_comment']:
                logger.info(f"✅ Comentario recibido ({len(album_info['user_comment'])} caracteres)")
            else:
                logger.info("ℹ️ Sin comentario")
        except Exception as e:
            logger.error(f"Error obteniendo comentario: {e}")
            album_info['user_comment'] = ""

        # 3. Buscar imágenes
        logger.info("🖼️ Buscando imágenes...")
        try:
            album_info['album_image'] = self.image_finder.find_album_image(
                album_info['artist'],
                album_info['title']
            )

            if album_info['album_image']:
                logger.info(f"✅ Imagen de álbum: {album_info['album_image'].get('source', 'desconocido')}")
            else:
                logger.info("ℹ️ Sin imagen de álbum")

            album_info['artist_image'] = self.image_finder.find_artist_image(
                album_info['artist'],
                self.db_manager
            )

            if album_info['artist_image']:
                logger.info(f"✅ Imagen de artista: {album_info['artist_image'].get('source', 'desconocido')}")
            else:
                logger.info("ℹ️ Sin imagen de artista")
        except Exception as e:
            logger.error(f"Error buscando imágenes: {e}")

        # 4. Buscar letras
        logger.info("🎤 Buscando letras...")
        try:
            album_info['lyrics'] = self.lyrics_finder.find_lyrics(
                album_info['artist'],
                album_info['tracks']
            )

            lyrics_found = len([l for l in album_info['lyrics'].values() if l.get('lyrics')]) if album_info['lyrics'] else 0
            logger.info(f"🎵 Letras encontradas: {lyrics_found}/{len(album_info.get('tracks', []))}")
        except Exception as e:
            logger.error(f"Error buscando letras: {e}")

        # 5. Buscar enlaces
        logger.info("🔗 Buscando enlaces...")
        try:
            album_info['links'] = self.link_finder.find_links(
                album_info['artist'],
                album_info['title'],
                album_info.get('mbid')
            )

            total_links = sum(len(category) for category in album_info.get('links', {}).values())
            logger.info(f"🌐 Enlaces encontrados: {total_links}")
        except Exception as e:
            logger.error(f"Error buscando enlaces: {e}")

        # 6. Generar archivos web
        logger.info("📄 Generando HTML...")
        try:
            self._generate_web_files(album_info, output_dir)
            logger.info("🎉 ¡Álbum procesado exitosamente!")
        except Exception as e:
            logger.error(f"Error generando archivos: {e}")
            raise

        return album_info

    def _generate_web_files(self, album_info: Dict[str, Any], output_dir: str):
        """Generar archivos web"""
        docs_dir = Path(output_dir) / "docs"
        albums_dir = docs_dir / "albums"
        imgs_dir = docs_dir / "imgs"
        thumbnails_dir = docs_dir / "thumbnails"

        albums_dir.mkdir(parents=True, exist_ok=True)
        imgs_dir.mkdir(parents=True, exist_ok=True)
        thumbnails_dir.mkdir(parents=True, exist_ok=True)

        safe_name = self._get_safe_filename(
            f"{album_info['artist']} - {album_info['title']}"
        )

        # Procesar imágenes
        album_info = self._process_album_images(album_info, safe_name, imgs_dir, thumbnails_dir)

        # Generar HTML usando el generador original
        html_content = self.html_generator.generate_html_with_dynamic_tabs(
            album_info, self.db_manager
        )

        # Aplicar modificaciones CSS para las mejoras
        html_content = self._apply_css_fixes(html_content, album_info)

        html_path = albums_dir / f"{safe_name}.html"
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        # Guardar JSON
        json_path = albums_dir / f"{safe_name}_data.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(album_info, f, indent=2, ensure_ascii=False)

        # Actualizar índice
        self._update_albums_index(album_info, safe_name, docs_dir)

        logger.info(f"📁 Archivos generados: {html_path.name}, {json_path.name}")

    def _apply_css_fixes(self, html_content: str, album_info: Dict[str, Any]) -> str:
        """Aplicar correcciones CSS al HTML generado"""

        # CSS mejorado para móvil y sin placeholders
        css_fixes = """
        /* Mejoras responsive */
        @media (max-width: 768px) {
            .album-header {
                padding: 1.5rem 0 !important;
                margin-bottom: 1.5rem !important;
            }

            .album-hero {
                gap: 1rem !important;
            }

            .album-title {
                font-size: 1.5rem !important;
                margin-bottom: 0.25rem !important;
            }

            .artist-name {
                font-size: 1.125rem !important;
                margin-bottom: 1rem !important;
            }

            .album-cover img {
                width: 120px !important;
                height: 120px !important;
            }

            .artist-image img {
                width: 80px !important;
                height: 80px !important;
            }

            .album-details {
                flex-direction: column !important;
                align-items: flex-start !important;
                gap: 0.25rem !important;
            }
        }

        @media (max-width: 480px) {
            .album-header {
                padding: 1rem 0 !important;
            }

            .album-title {
                font-size: 1.25rem !important;
            }

            .artist-name {
                font-size: 1rem !important;
            }

            .album-cover img {
                width: 100px !important;
                height: 100px !important;
            }

            .artist-image img {
                width: 70px !important;
                height: 70px !important;
            }
        }

        /* Texto con mejor contraste */
        .album-title,
        .artist-name {
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.8) !important;
        }

        .album-details .detail-item {
            background: rgba(0, 0, 0, 0.4) !important;
            backdrop-filter: blur(10px) !important;
            border: 1px solid rgba(255, 255, 255, 0.2) !important;
        }
        """

        # Insertar CSS antes del cierre de </head>
        if "</head>" in html_content:
            css_insert = f"\n    <style>\n{css_fixes}\n    </style>\n</head>"
            html_content = html_content.replace("</head>", css_insert)

        return html_content

    def _process_album_images(self, album_info: Dict[str, Any], safe_name: str,
                             imgs_dir: Path, thumbnails_dir: Path) -> Dict[str, Any]:
        """Procesar imágenes solo si existen"""
        try:
            from PIL import Image
            import requests
            from io import BytesIO

            # Solo procesar si las imágenes tienen URLs válidas
            if (album_info.get('album_image') and
                album_info['album_image'].get('url') and
                album_info['album_image']['url'].strip()):

                album_info['album_image'] = self._copy_and_process_image(
                    album_info['album_image'],
                    f"{safe_name}_album",
                    imgs_dir,
                    thumbnails_dir,
                    'album'
                )

            if (album_info.get('artist_image') and
                album_info['artist_image'].get('url') and
                album_info['artist_image']['url'].strip()):

                album_info['artist_image'] = self._copy_and_process_image(
                    album_info['artist_image'],
                    f"{safe_name}_artist",
                    imgs_dir,
                    thumbnails_dir,
                    'artist'
                )

            return album_info

        except ImportError:
            logger.warning("⚠️ Pillow no está instalado.")
            return album_info
        except Exception as e:
            logger.error(f"❌ Error procesando imágenes: {e}")
            return album_info

    def _copy_and_process_image(self, image_info: Dict[str, Any], base_name: str,
                               imgs_dir: Path, thumbnails_dir: Path,
                               image_type: str) -> Dict[str, Any]:
        """Copiar y procesar imagen"""
        try:
            from PIL import Image
            import requests
            from io import BytesIO

            original_url = image_info['url']
            img_filename = f"{base_name}.jpg"
            thumb_filename = f"{base_name}_thumb.jpg"

            img_path = imgs_dir / img_filename
            thumb_path = thumbnails_dir / thumb_filename

            if img_path.exists() and thumb_path.exists():
                return {
                    'url': f"../imgs/{img_filename}",
                    'thumbnail_url': f"../thumbnails/{thumb_filename}",
                    'source': image_info.get('source', 'processed'),
                    'type': image_type
                }

            # Abrir imagen
            if original_url.startswith(('http://', 'https://')):
                response = requests.get(original_url, timeout=10)
                response.raise_for_status()
                image = Image.open(BytesIO(response.content))
            elif Path(original_url).exists():
                image = Image.open(original_url)
            else:
                logger.warning(f"⚠️ Imagen no accesible: {original_url}")
                return image_info

            if image.mode != 'RGB':
                image = image.convert('RGB')

            # Guardar imagen (800x800 máx)
            img_copy = image.copy()
            img_copy.thumbnail((800, 800), Image.Resampling.LANCZOS)
            img_copy.save(img_path, 'JPEG', quality=90, optimize=True)

            # Thumbnail (300x300)
            thumb_copy = image.copy()
            thumb_copy.thumbnail((300, 300), Image.Resampling.LANCZOS)
            thumb_copy.save(thumb_path, 'JPEG', quality=85, optimize=True)

            logger.info(f"🖼️ Procesadas: {img_filename} y {thumb_filename}")

            return {
                'url': f"../imgs/{img_filename}",
                'thumbnail_url': f"../thumbnails/{thumb_filename}",
                'source': image_info.get('source', 'processed'),
                'type': image_type
            }

        except Exception as e:
            logger.error(f"❌ Error procesando imagen {base_name}: {e}")
            return image_info

    def _update_albums_index(self, album_info: Dict[str, Any], filename: str, docs_dir: Path):
        """Actualizar índice de álbumes"""
        albums_data_file = docs_dir / "albums-data.json"

        if albums_data_file.exists():
            with open(albums_data_file, 'r', encoding='utf-8') as f:
                albums_data = json.load(f)
        else:
            albums_data = []

        album_entry = {
            'filename': f"{filename}.html",
            'title': album_info.get('title', 'Álbum Desconocido'),
            'artist': album_info.get('artist', 'Artista Desconocido'),
            'year': album_info.get('year'),
            'genre': album_info.get('genre', []),
            'cover_image': self._get_web_image_path(album_info, 'album_image'),
            'thumbnail_image': self._get_web_image_path(album_info, 'album_image', thumbnail=True),
            'tracks_count': len(album_info.get('tracks', [])),
            'has_lyrics': bool(album_info.get('lyrics')),
            'has_comment': bool(album_info.get('user_comment', '').strip()),
            'date_added': str(datetime.now().isoformat())
        }

        # Verificar si existe
        existing_index = None
        for i, existing in enumerate(albums_data):
            if (existing.get('artist') == album_entry['artist'] and
                existing.get('title') == album_entry['title']):
                existing_index = i
                break

        if existing_index is not None:
            albums_data[existing_index] = album_entry
        else:
            albums_data.append(album_entry)

        with open(albums_data_file, 'w', encoding='utf-8') as f:
            json.dump(albums_data, f, indent=2, ensure_ascii=False)

        logger.info(f"📊 Total álbumes: {len(albums_data)}")

    def _get_web_image_path(self, album_info: Dict[str, Any], image_key: str, thumbnail: bool = False) -> Optional[str]:
        """Obtener ruta web de imagen"""
        image_info = album_info.get(image_key)
        if not image_info:
            return None

        if thumbnail and 'thumbnail_url' in image_info:
            return image_info['thumbnail_url']
        elif 'url' in image_info:
            return image_info['url']

        return None

    def _get_safe_filename(self, name: str) -> str:
        """Nombre seguro para archivos"""
        safe_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_. "
        safe_name = "".join(c if c in safe_chars else "_" for c in name)

        while "  " in safe_name:
            safe_name = safe_name.replace("  ", " ")
        while "__" in safe_name:
            safe_name = safe_name.replace("__", "_")

        return safe_name.strip(" -_")


def main():
    """Función principal"""
    print("🎵 Album Web Generator - VERSIÓN SIMPLE")
    print("=" * 50)

    parser = argparse.ArgumentParser(description="Generador de Páginas Web de Álbumes")
    parser.add_argument("folder", help="Carpeta que contiene los archivos del álbum")
    parser.add_argument("-o", "--output", help="Carpeta de salida (por defecto: ./web_output)")
    parser.add_argument("--db", help="Ruta a la base de datos SQLite")
    parser.add_argument("-v", "--verbose", action="store_true", help="Modo verboso")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    folder_path = Path(args.folder)
    if not folder_path.exists():
        logger.error(f"❌ La carpeta {folder_path} no existe")
        sys.exit(1)

    output_dir = args.output or "."

    try:
        generator = AlbumWebGenerator(args.db)
        album_info = generator.process_album(str(folder_path), output_dir)

        print("\n🎉 ¡GENERACIÓN COMPLETADA!")

    except Exception as e:
        logger.error(f"❌ Error procesando álbum: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
