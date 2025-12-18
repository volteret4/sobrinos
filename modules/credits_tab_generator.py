"""
Módulo para generar pestaña de créditos y colaboradores de Discogs
"""

import logging
from typing import Dict, Any, Optional
import json

logger = logging.getLogger(__name__)


class CreditsTabGenerator:
    """Generador de pestaña de créditos y colaboradores"""

    def __init__(self, db_manager=None):
        """
        Inicializar generador de créditos

        Args:
            db_manager: Manager de base de datos
        """
        self.db_manager = db_manager

    def should_create_tab(self, artist_name: str, album_title: str) -> bool:
        """
        Determinar si se debe crear la pestaña de créditos

        Args:
            artist_name: Nombre del artista
            album_title: Título del álbum

        Returns:
            True si hay información de créditos disponible
        """
        if not self.db_manager:
            return False

        try:
            cursor = self.db_manager.connection.cursor()

            # Buscar información de créditos del álbum
            cursor.execute("""
                SELECT a.discogs_credits, a.producers, a.engineers, a.musicians,
                       a.collaborators, a.recording_info, a.studio_info
                FROM albums a
                JOIN artists ar ON a.artist_id = ar.id
                WHERE LOWER(REPLACE(REPLACE(REPLACE(ar.name, 'á', 'a'), 'é', 'e'), 'í', 'i')) = ?
                AND LOWER(REPLACE(REPLACE(REPLACE(a.name, 'á', 'a'), 'é', 'e'), 'í', 'i')) = ?
            """, (
                self.db_manager._normalize_for_search(artist_name),
                self.db_manager._normalize_for_search(album_title)
            ))

            result = cursor.fetchone()

            if result:
                # Verificar si al menos un campo de créditos tiene datos
                credit_fields = ['discogs_credits', 'producers', 'engineers', 'musicians',
                               'collaborators', 'recording_info', 'studio_info']

                for field in credit_fields:
                    if result[field] and result[field].strip():
                        return True

            return False

        except Exception as e:
            logger.error(f"Error verificando créditos: {e}")
            return False

    def generate_credits_tab_html(self, artist_name: str, album_title: str) -> str:
        """
        Generar HTML para la pestaña de créditos

        Args:
            artist_name: Nombre del artista
            album_title: Título del álbum

        Returns:
            HTML de la pestaña de créditos
        """
        if not self.should_create_tab(artist_name, album_title):
            return ""

        try:
            cursor = self.db_manager.connection.cursor()

            cursor.execute("""
                SELECT a.name as album_name, ar.name as artist_name,
                       a.discogs_credits, a.producers, a.engineers, a.musicians,
                       a.collaborators, a.recording_info, a.studio_info,
                       a.recording_date, a.label, a.catalog_number
                FROM albums a
                JOIN artists ar ON a.artist_id = ar.id
                WHERE LOWER(REPLACE(REPLACE(REPLACE(ar.name, 'á', 'a'), 'é', 'e'), 'í', 'i')) = ?
                AND LOWER(REPLACE(REPLACE(REPLACE(a.name, 'á', 'a'), 'é', 'e'), 'í', 'i')) = ?
            """, (
                self.db_manager._normalize_for_search(artist_name),
                self.db_manager._normalize_for_search(album_title)
            ))

            result = cursor.fetchone()

            if not result:
                return ""

            credits_sections = []

            # Productores
            if result['producers'] and result['producers'].strip():
                producers = self._parse_credits_field(result['producers'])
                credits_sections.append(self._generate_credit_section(
                    "Productores", "🎛️", producers
                ))

            # Ingenieros
            if result['engineers'] and result['engineers'].strip():
                engineers = self._parse_credits_field(result['engineers'])
                credits_sections.append(self._generate_credit_section(
                    "Ingenieros", "🔧", engineers
                ))

            # Músicos
            if result['musicians'] and result['musicians'].strip():
                musicians = self._parse_credits_field(result['musicians'])
                credits_sections.append(self._generate_credit_section(
                    "Músicos", "🎸", musicians
                ))

            # Colaboradores
            if result['collaborators'] and result['collaborators'].strip():
                collaborators = self._parse_credits_field(result['collaborators'])
                credits_sections.append(self._generate_credit_section(
                    "Colaboradores", "🤝", collaborators
                ))

            # Información de grabación
            recording_info = []
            if result['recording_info'] and result['recording_info'].strip():
                recording_info.append(f"<p><strong>Grabación:</strong> {result['recording_info']}</p>")

            if result['studio_info'] and result['studio_info'].strip():
                recording_info.append(f"<p><strong>Estudio:</strong> {result['studio_info']}</p>")

            if result['recording_date'] and result['recording_date'].strip():
                recording_info.append(f"<p><strong>Fecha:</strong> {result['recording_date']}</p>")

            if result['label'] and result['label'].strip():
                recording_info.append(f"<p><strong>Sello:</strong> {result['label']}</p>")

            if result['catalog_number'] and result['catalog_number'].strip():
                recording_info.append(f"<p><strong>Catálogo:</strong> {result['catalog_number']}</p>")

            if recording_info:
                credits_sections.append(f"""
                <div class="credits-section">
                    <h4 class="credits-title">
                        <span class="credits-icon">📀</span>
                        Información de Grabación
                    </h4>
                    <div class="credits-content">
                        {''.join(recording_info)}
                    </div>
                </div>""")

            # Créditos completos de Discogs (si están en JSON)
            if result['discogs_credits'] and result['discogs_credits'].strip():
                try:
                    discogs_data = json.loads(result['discogs_credits'])
                    discogs_html = self._generate_discogs_credits(discogs_data)
                    if discogs_html:
                        credits_sections.append(discogs_html)
                except json.JSONDecodeError:
                    # Si no es JSON, mostrar como texto
                    credits_sections.append(f"""
                    <div class="credits-section">
                        <h4 class="credits-title">
                            <span class="credits-icon">💿</span>
                            Créditos Completos (Discogs)
                        </h4>
                        <div class="credits-content">
                            <pre>{result['discogs_credits']}</pre>
                        </div>
                    </div>""")

            return f"""
                <section id="credits" class="tab-panel">
                    <h3>Créditos y Colaboradores</h3>
                    <div class="credits-info">
                        <p>Información detallada de productores, ingenieros, músicos y colaboradores del álbum.</p>
                    </div>
                    <div class="credits-content">
                        {''.join(credits_sections)}
                    </div>
                </section>"""

        except Exception as e:
            logger.error(f"Error generando pestaña de créditos: {e}")
            return ""

    def _parse_credits_field(self, credits_text: str) -> list:
        """
        Parsear campo de créditos (puede estar separado por líneas, comas, etc.)

        Args:
            credits_text: Texto con créditos

        Returns:
            Lista de créditos parseados
        """
        if not credits_text:
            return []

        # Intentar diferentes separadores
        if '\n' in credits_text:
            # Separado por líneas
            credits = [line.strip() for line in credits_text.split('\n') if line.strip()]
        elif ';' in credits_text:
            # Separado por punto y coma
            credits = [credit.strip() for credit in credits_text.split(';') if credit.strip()]
        elif ',' in credits_text:
            # Separado por comas
            credits = [credit.strip() for credit in credits_text.split(',') if credit.strip()]
        else:
            # Texto único
            credits = [credits_text.strip()]

        return credits

    def _generate_credit_section(self, title: str, icon: str, credits: list) -> str:
        """
        Generar sección HTML para un tipo de crédito

        Args:
            title: Título de la sección
            icon: Icono emoji
            credits: Lista de créditos

        Returns:
            HTML de la sección
        """
        credits_html = []
        for credit in credits:
            # Separar nombre y rol si está en formato "Nombre - Rol"
            if ' - ' in credit:
                name, role = credit.split(' - ', 1)
                credits_html.append(f"""
                <div class="credit-item">
                    <span class="credit-name">{name.strip()}</span>
                    <span class="credit-role">{role.strip()}</span>
                </div>""")
            else:
                credits_html.append(f"""
                <div class="credit-item">
                    <span class="credit-name">{credit.strip()}</span>
                </div>""")

        return f"""
        <div class="credits-section">
            <h4 class="credits-title">
                <span class="credits-icon">{icon}</span>
                {title}
            </h4>
            <div class="credits-list">
                {''.join(credits_html)}
            </div>
        </div>"""

    def _generate_discogs_credits(self, discogs_data: dict) -> str:
        """
        Generar HTML para créditos estructurados de Discogs

        Args:
            discogs_data: Datos JSON de Discogs

        Returns:
            HTML de los créditos de Discogs
        """
        # Esta función se puede expandir según la estructura específica de datos de Discogs
        return f"""
        <div class="credits-section">
            <h4 class="credits-title">
                <span class="credits-icon">💿</span>
                Créditos Detallados (Discogs)
            </h4>
            <div class="credits-content">
                <pre>{json.dumps(discogs_data, indent=2)}</pre>
            </div>
        </div>"""

    def get_tab_info(self) -> Dict[str, str]:
        """
        Obtener información de la pestaña

        Returns:
            Información de la pestaña (id, nombre, icono)
        """
        return {
            'id': 'credits',
            'name': 'Créditos',
            'icon': '🎛️'
        }
