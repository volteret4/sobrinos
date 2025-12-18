"""
Módulo para generar pestaña de equipamiento de Equipboard
"""

import logging
from typing import Dict, Any, Optional
import json

logger = logging.getLogger(__name__)


class EquipmentTabGenerator:
    """Generador de pestaña de equipamiento del artista"""

    def __init__(self, db_manager=None):
        """
        Inicializar generador de equipamiento

        Args:
            db_manager: Manager de base de datos
        """
        self.db_manager = db_manager

    def should_create_tab(self, artist_name: str) -> bool:
        """
        Determinar si se debe crear la pestaña de equipamiento

        Args:
            artist_name: Nombre del artista

        Returns:
            True si hay información de equipamiento disponible
        """
        if not self.db_manager:
            return False

        try:
            cursor = self.db_manager.connection.cursor()

            # Buscar información de equipamiento del artista
            cursor.execute("""
                SELECT equipboard_url, guitar_gear, bass_gear, drum_gear,
                       keyboard_gear, amp_gear, pedal_gear, studio_gear,
                       equipment_description, gear_setup_info
                FROM artists
                WHERE LOWER(REPLACE(REPLACE(REPLACE(name, 'á', 'a'), 'é', 'e'), 'í', 'i')) = ?
            """, (self.db_manager._normalize_for_search(artist_name),))

            result = cursor.fetchone()

            if result:
                # Verificar si al menos un campo de equipamiento tiene datos
                equipment_fields = ['equipboard_url', 'guitar_gear', 'bass_gear', 'drum_gear',
                                  'keyboard_gear', 'amp_gear', 'pedal_gear', 'studio_gear',
                                  'equipment_description', 'gear_setup_info']

                for field in equipment_fields:
                    if result[field] and result[field].strip():
                        return True

            return False

        except Exception as e:
            logger.error(f"Error verificando equipamiento: {e}")
            return False

    def generate_equipment_tab_html(self, artist_name: str) -> str:
        """
        Generar HTML para la pestaña de equipamiento

        Args:
            artist_name: Nombre del artista

        Returns:
            HTML de la pestaña de equipamiento
        """
        if not self.should_create_tab(artist_name):
            return ""

        try:
            cursor = self.db_manager.connection.cursor()

            cursor.execute("""
                SELECT name, equipboard_url, guitar_gear, bass_gear, drum_gear,
                       keyboard_gear, amp_gear, pedal_gear, studio_gear,
                       equipment_description, gear_setup_info, equipment_last_updated
                FROM artists
                WHERE LOWER(REPLACE(REPLACE(REPLACE(name, 'á', 'a'), 'é', 'e'), 'í', 'i')) = ?
            """, (self.db_manager._normalize_for_search(artist_name),))

            result = cursor.fetchone()

            if not result:
                return ""

            equipment_sections = []

            # Enlace a Equipboard si existe
            if result['equipboard_url'] and result['equipboard_url'].strip():
                equipment_sections.append(f"""
                <div class="equipment-header">
                    <div class="equipboard-link">
                        <h4>🔗 Perfil en Equipboard</h4>
                        <a href="{result['equipboard_url']}" target="_blank" rel="noopener noreferrer">
                            Ver perfil completo en Equipboard →
                        </a>
                    </div>
                </div>""")

            # Configuración de tipos de equipamiento
            gear_configs = {
                'guitar_gear': {'name': 'Guitarras', 'icon': '🎸', 'description': 'Guitarras eléctricas y acústicas'},
                'bass_gear': {'name': 'Bajos', 'icon': '🎸', 'description': 'Guitarras bajas'},
                'drum_gear': {'name': 'Batería', 'icon': '🥁', 'description': 'Baterías, platillos y percusión'},
                'keyboard_gear': {'name': 'Teclados', 'icon': '🎹', 'description': 'Pianos, sintetizadores y samplers'},
                'amp_gear': {'name': 'Amplificadores', 'icon': '🔊', 'description': 'Amplificadores y cabezales'},
                'pedal_gear': {'name': 'Pedales', 'icon': '🎚️', 'description': 'Pedales de efectos'},
                'studio_gear': {'name': 'Estudio', 'icon': '🎙️', 'description': 'Equipamiento de grabación y estudio'}
            }

            # Generar secciones de equipamiento
            for field, config in gear_configs.items():
                gear_data = result[field]
                if gear_data and gear_data.strip():
                    equipment_sections.append(self._generate_gear_section(
                        config['name'], config['icon'], config['description'], gear_data
                    ))

            # Descripción general del equipamiento
            description_html = ""
            if result['equipment_description'] and result['equipment_description'].strip():
                description_html = f"""
                <div class="equipment-description">
                    <h4>📝 Descripción del Setup</h4>
                    <p>{result['equipment_description']}</p>
                </div>"""

            # Información del setup
            setup_html = ""
            if result['gear_setup_info'] and result['gear_setup_info'].strip():
                setup_html = f"""
                <div class="setup-info">
                    <h4>⚙️ Configuración del Setup</h4>
                    <div class="setup-content">
                        {self._format_setup_info(result['gear_setup_info'])}
                    </div>
                </div>"""

            last_updated = result['equipment_last_updated'] or 'No disponible'

            return f"""
                <section id="equipment" class="tab-panel">
                    <h3>Equipamiento Musical</h3>
                    <div class="equipment-info">
                        <p>Información detallada del equipamiento y configuración musical de {result['name']}.</p>
                        <p><strong>Última actualización:</strong> {last_updated}</p>
                    </div>
                    {description_html}
                    {setup_html}
                    <div class="equipment-content">
                        {''.join(equipment_sections)}
                    </div>
                    <script>
                    function toggleGearSection(sectionId) {{
                        const section = document.getElementById(sectionId);
                        const content = section.querySelector('.gear-items');
                        const header = section.querySelector('.gear-header');

                        content.style.display = content.style.display === 'none' ? 'block' : 'none';
                        header.classList.toggle('collapsed');
                    }}
                    </script>
                </section>"""

        except Exception as e:
            logger.error(f"Error generando pestaña de equipamiento: {e}")
            return ""

    def _generate_gear_section(self, title: str, icon: str, description: str, gear_data: str) -> str:
        """
        Generar sección HTML para un tipo de equipamiento

        Args:
            title: Título de la sección
            icon: Icono emoji
            description: Descripción del tipo de equipamiento
            gear_data: Datos del equipamiento

        Returns:
            HTML de la sección
        """
        section_id = f"gear-{title.lower().replace(' ', '-')}"
        gear_items = self._parse_gear_data(gear_data)

        gear_html = []
        for item in gear_items:
            if isinstance(item, dict):
                # Equipamiento estructurado con detalles
                gear_html.append(f"""
                <div class="gear-item detailed">
                    <div class="gear-name">{item.get('name', 'Sin nombre')}</div>
                    <div class="gear-details">
                        {f"<span class='gear-model'>Modelo: {item.get('model', 'N/A')}</span>" if item.get('model') else ""}
                        {f"<span class='gear-brand'>Marca: {item.get('brand', 'N/A')}</span>" if item.get('brand') else ""}
                        {f"<span class='gear-year'>Año: {item.get('year', 'N/A')}</span>" if item.get('year') else ""}
                        {f"<div class='gear-notes'>{item.get('notes', '')}</div>" if item.get('notes') else ""}
                    </div>
                </div>""")
            else:
                # Equipamiento simple (texto)
                gear_html.append(f"""
                <div class="gear-item simple">
                    <div class="gear-name">{item}</div>
                </div>""")

        return f"""
        <div class="gear-section" id="{section_id}">
            <div class="gear-header" onclick="toggleGearSection('{section_id}')">
                <h4>
                    <span class="gear-icon">{icon}</span>
                    {title}
                    <span class="toggle-icon">▼</span>
                </h4>
                <p class="gear-description">{description}</p>
            </div>
            <div class="gear-items">
                {''.join(gear_html)}
            </div>
        </div>"""

    def _parse_gear_data(self, gear_data: str) -> list:
        """
        Parsear datos de equipamiento (puede ser JSON, texto con líneas, etc.)

        Args:
            gear_data: Datos del equipamiento

        Returns:
            Lista de equipamiento parseado
        """
        if not gear_data:
            return []

        gear_data = gear_data.strip()

        # Intentar parsear como JSON primero
        try:
            json_data = json.loads(gear_data)
            if isinstance(json_data, list):
                return json_data
            elif isinstance(json_data, dict):
                return [json_data]
        except json.JSONDecodeError:
            pass

        # Si no es JSON, parsear como texto
        if '\n' in gear_data:
            # Separado por líneas
            items = [line.strip() for line in gear_data.split('\n') if line.strip()]
        elif ';' in gear_data:
            # Separado por punto y coma
            items = [item.strip() for item in gear_data.split(';') if item.strip()]
        elif ',' in gear_data:
            # Separado por comas
            items = [item.strip() for item in gear_data.split(',') if item.strip()]
        else:
            # Texto único
            items = [gear_data.strip()]

        return items

    def _format_setup_info(self, setup_info: str) -> str:
        """
        Formatear información de configuración del setup

        Args:
            setup_info: Información del setup

        Returns:
            HTML formateado
        """
        # Convertir saltos de línea a HTML
        formatted = setup_info.replace('\n', '<br>')

        # Intentar estructurar si tiene patrones reconocibles
        if '->' in formatted or '=>' in formatted:
            # Parece ser un diagrama de señal
            formatted = f'<div class="signal-chain">{formatted}</div>'
        elif any(keyword in setup_info.lower() for keyword in ['config', 'setting', 'preset']):
            # Parece ser configuración
            formatted = f'<div class="configuration">{formatted}</div>'

        return formatted

    def get_tab_info(self) -> Dict[str, str]:
        """
        Obtener información de la pestaña

        Returns:
            Información de la pestaña (id, nombre, icono)
        """
        return {
            'id': 'equipment',
            'name': 'Equipamiento',
            'icon': '🎸'
        }
