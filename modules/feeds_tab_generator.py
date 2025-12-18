"""
Módulo para generar pestaña de feeds del artista
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class FeedsTabGenerator:
    """Generador de pestaña de feeds del artista"""

    def __init__(self, db_manager=None):
        """
        Inicializar generador de feeds

        Args:
            db_manager: Manager de base de datos
        """
        self.db_manager = db_manager

    def should_create_tab(self, artist_name: str) -> bool:
        """
        Determinar si se debe crear la pestaña de feeds

        Args:
            artist_name: Nombre del artista

        Returns:
            True si hay información de feeds disponible
        """
        if not self.db_manager:
            return False

        try:
            cursor = self.db_manager.connection.cursor()

            # Buscar información de feeds del artista
            cursor.execute("""
                SELECT rss_feed, news_feed, twitter_feed, instagram_feed,
                       youtube_feed, spotify_updates, bandcamp_feed
                FROM artists
                WHERE LOWER(REPLACE(REPLACE(REPLACE(name, 'á', 'a'), 'é', 'e'), 'í', 'i')) = ?
            """, (self.db_manager._normalize_for_search(artist_name),))

            result = cursor.fetchone()

            if result:
                # Verificar si al menos un feed tiene datos
                feed_fields = ['rss_feed', 'news_feed', 'twitter_feed', 'instagram_feed',
                              'youtube_feed', 'spotify_updates', 'bandcamp_feed']

                for field in feed_fields:
                    if result[field] and result[field].strip():
                        return True

            return False

        except Exception as e:
            logger.error(f"Error verificando feeds: {e}")
            return False

    def generate_feeds_tab_html(self, artist_name: str) -> str:
        """
        Generar HTML para la pestaña de feeds

        Args:
            artist_name: Nombre del artista

        Returns:
            HTML de la pestaña de feeds
        """
        if not self.should_create_tab(artist_name):
            return ""

        try:
            cursor = self.db_manager.connection.cursor()

            cursor.execute("""
                SELECT name, rss_feed, news_feed, twitter_feed, instagram_feed,
                       youtube_feed, spotify_updates, bandcamp_feed,
                       feed_last_updated, feed_description
                FROM artists
                WHERE LOWER(REPLACE(REPLACE(REPLACE(name, 'á', 'a'), 'é', 'e'), 'í', 'i')) = ?
            """, (self.db_manager._normalize_for_search(artist_name),))

            result = cursor.fetchone()

            if not result:
                return ""

            feeds_html = []

            # Configuración de feeds
            feed_configs = {
                'rss_feed': {'name': 'RSS Feed', 'icon': '📡', 'description': 'Feed RSS oficial'},
                'news_feed': {'name': 'Noticias', 'icon': '📰', 'description': 'Feed de noticias'},
                'twitter_feed': {'name': 'Twitter', 'icon': '🐦', 'description': 'Timeline de Twitter'},
                'instagram_feed': {'name': 'Instagram', 'icon': '📷', 'description': 'Posts de Instagram'},
                'youtube_feed': {'name': 'YouTube', 'icon': '📺', 'description': 'Últimos videos'},
                'spotify_updates': {'name': 'Spotify', 'icon': '🎵', 'description': 'Actualizaciones de Spotify'},
                'bandcamp_feed': {'name': 'Bandcamp', 'icon': '🎶', 'description': 'Novedades en Bandcamp'}
            }

            # Generar secciones de feeds
            for field, config in feed_configs.items():
                feed_url = result[field]
                if feed_url and feed_url.strip():
                    feeds_html.append(f"""
                    <div class="feed-section">
                        <h4 class="feed-title">
                            <span class="feed-icon">{config['icon']}</span>
                            {config['name']}
                        </h4>
                        <p class="feed-description">{config['description']}</p>
                        <div class="feed-url">
                            <a href="{feed_url.strip()}" target="_blank" rel="noopener noreferrer">
                                {feed_url.strip()}
                            </a>
                        </div>
                        <button class="feed-refresh-btn" onclick="refreshFeed('{field}', '{feed_url.strip()}')">
                            🔄 Actualizar
                        </button>
                        <div id="feed-{field}" class="feed-content">
                            <p><em>Haz click en "Actualizar" para cargar el contenido del feed</em></p>
                        </div>
                    </div>""")

            last_updated = result['feed_last_updated'] or 'Nunca'
            feed_description = result['feed_description'] or f'Feeds y actualizaciones de {result["name"]}'

            return f"""
                <section id="feeds" class="tab-panel">
                    <h3>Feeds y Actualizaciones</h3>
                    <div class="feeds-info">
                        <p class="feeds-description">{feed_description}</p>
                        <p class="feeds-updated"><strong>Última actualización:</strong> {last_updated}</p>
                    </div>
                    <div class="feeds-content">
                        {''.join(feeds_html)}
                    </div>
                    <script>
                    function refreshFeed(feedType, feedUrl) {{
                        const contentDiv = document.getElementById('feed-' + feedType);
                        contentDiv.innerHTML = '<p><em>Cargando feed...</em></p>';

                        // Simular carga de feed (en implementación real, harías fetch al feed)
                        setTimeout(() => {{
                            contentDiv.innerHTML = `
                                <div class="feed-item">
                                    <h5>Último elemento del feed</h5>
                                    <p>Este sería el contenido más reciente del feed.</p>
                                    <small>Fecha: ${{new Date().toLocaleDateString()}}</small>
                                </div>
                                <p><small><a href="${{feedUrl}}" target="_blank">Ver feed completo →</a></small></p>
                            `;
                        }}, 1500);
                    }}
                    </script>
                </section>"""

        except Exception as e:
            logger.error(f"Error generando pestaña de feeds: {e}")
            return ""

    def get_tab_info(self) -> Dict[str, str]:
        """
        Obtener información de la pestaña

        Returns:
            Información de la pestaña (id, nombre, icono)
        """
        return {
            'id': 'feeds',
            'name': 'Feeds',
            'icon': '📡'
        }
