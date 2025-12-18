"""
Funciones mejoradas para manejo de colores y contraste
"""

def calculate_luminance(rgb_tuple):
    """
    Calcular luminancia relativa de un color RGB
    Basado en WCAG 2.0 guidelines
    """
    r, g, b = [c / 255.0 for c in rgb_tuple]

    # Convertir a luminancia lineal
    def to_linear(c):
        if c <= 0.03928:
            return c / 12.92
        else:
            return pow((c + 0.055) / 1.055, 2.4)

    r_lin = to_linear(r)
    g_lin = to_linear(g)
    b_lin = to_linear(b)

    # Calcular luminancia según WCAG
    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin

def calculate_contrast_ratio(color1, color2):
    """
    Calcular ratio de contraste entre dos colores
    """
    lum1 = calculate_luminance(color1)
    lum2 = calculate_luminance(color2)

    # Asegurar que lum1 sea el más claro
    if lum1 < lum2:
        lum1, lum2 = lum2, lum1

    return (lum1 + 0.05) / (lum2 + 0.05)

def get_optimal_text_color(background_color):
    """
    Obtener color de texto óptimo para un fondo dado
    Garantiza ratio de contraste >= 4.5 (WCAG AA)
    """
    bg_luminance = calculate_luminance(background_color)

    # Colores candidatos
    white = (255, 255, 255)
    black = (0, 0, 0)
    light_gray = (240, 240, 240)
    dark_gray = (40, 40, 40)

    # Calcular contrastes
    white_contrast = calculate_contrast_ratio(background_color, white)
    black_contrast = calculate_contrast_ratio(background_color, black)
    light_gray_contrast = calculate_contrast_ratio(background_color, light_gray)
    dark_gray_contrast = calculate_contrast_ratio(background_color, dark_gray)

    # Seleccionar el mejor color
    if white_contrast >= 4.5:
        return white
    elif black_contrast >= 4.5:
        return black
    elif light_gray_contrast >= 4.5:
        return light_gray
    elif dark_gray_contrast >= 4.5:
        return dark_gray
    else:
        # Forzar el que tenga mayor contraste
        contrasts = [
            (white_contrast, white),
            (black_contrast, black),
            (light_gray_contrast, light_gray),
            (dark_gray_contrast, dark_gray)
        ]
        return max(contrasts, key=lambda x: x[0])[1]

def get_secondary_text_color(background_color):
    """
    Obtener color de texto secundario (menos prominente)
    """
    primary_color = get_optimal_text_color(background_color)

    # Hacer el color secundario un 30% menos contrastante
    if sum(primary_color) > 400:  # Color claro
        # Hacer más oscuro
        return tuple(max(0, c - 80) for c in primary_color)
    else:  # Color oscuro
        # Hacer más claro
        return tuple(min(255, c + 80) for c in primary_color)

def rgb_to_hex(rgb_tuple):
    """Convertir RGB a hexadecimal"""
    return f"#{rgb_tuple[0]:02x}{rgb_tuple[1]:02x}{rgb_tuple[2]:02x}"

def hex_to_rgb(hex_color):
    """Convertir hexadecimal a RGB"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def create_enhanced_color_palette(dominant_color):
    """
    Crear paleta de colores mejorada con contraste óptimo
    """
    import colorsys

    r, g, b = dominant_color
    h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)

    # Color principal (ligeramente ajustado)
    primary_rgb = colorsys.hsv_to_rgb(h, min(1.0, s * 1.1), min(1.0, v * 0.85))
    primary_color = tuple(int(c * 255) for c in primary_rgb)

    # Color secundario (variación complementaria)
    secondary_h = (h + 0.08) % 1.0
    secondary_rgb = colorsys.hsv_to_rgb(secondary_h, min(1.0, s * 0.9), min(1.0, v * 1.0))
    secondary_color = tuple(int(c * 255) for c in secondary_rgb)

    # Color de acento (complementario)
    accent_h = (h + 0.5) % 1.0
    accent_rgb = colorsys.hsv_to_rgb(accent_h, min(1.0, s * 0.8), min(1.0, v * 0.9))
    accent_color = tuple(int(c * 255) for c in accent_rgb)

    # Colores de texto óptimos
    primary_text = get_optimal_text_color(primary_color)
    secondary_text = get_secondary_text_color(primary_color)

    return {
        'background_primary': rgb_to_hex(primary_color),
        'background_secondary': rgb_to_hex(secondary_color),
        'accent': rgb_to_hex(accent_color),
        'text_primary': rgb_to_hex(primary_text),
        'text_secondary': rgb_to_hex(secondary_text),
        'text_contrast_ratio': calculate_contrast_ratio(primary_color, primary_text)
    }

# CSS helper para inyectar colores con contraste optimizado
def generate_contrast_css(palette):
    """
    Generar CSS con colores optimizados para contraste
    """
    return f"""
/* Colores optimizados para contraste */
.album-header {{
    background: linear-gradient(135deg, {palette['background_primary']}, {palette['background_secondary']});
    color: {palette['text_primary']} !important;
}}

.album-title,
.artist-name {{
    color: {palette['text_primary']} !important;
    text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.8) !important;
}}

.album-details .detail-item {{
    background: rgba(0, 0, 0, 0.4) !important;
    color: {palette['text_primary']} !important;
    border: 1px solid rgba(255, 255, 255, 0.2) !important;
}}

.album-details .detail-item strong {{
    color: {palette['text_primary']} !important;
}}

/* Mejoras adicionales para legibilidad */
@supports (backdrop-filter: blur(10px)) {{
    .album-details .detail-item {{
        backdrop-filter: blur(10px) !important;
    }}
}}
"""
