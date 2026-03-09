# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Sobrinos

Sistema para asociar tarjetas NFC a discos de música, películas o series. Al escanear una tarjeta se lanza la reproducción en el reproductor configurado. Paralelamente genera una web en `docs/` con información del elemento escaneado, accesible mediante QR impreso en la tarjeta.

## Comandos principales

```bash
# Instalar dependencias
pip install -r requirements.txt

# Dependencias del sistema (Debian/Ubuntu) para el chip ACR122U
sudo apt-get install libacsccid1 pcscd pcsc-tools
sudo systemctl enable pcscd.socket

# Detectar UID de tarjetas NFC
python nfc/nfc_detect_uid.py

# Asociar tarjeta NFC a una ruta de reproducción (genera nfc_playlist.json)
python nfc/nfc_config_gen.py

# Monitorear tarjetas y reaccionar (requiere nfc_playlist.json)
python nfc/nfc_reaccionar.py

# Generar portadas para tarjetas de música (cara A y cara B)
python nfc/nfc_generar_portada.py /ruta/al/album [--custom-url https://tu_web]

# Generar portadas para tarjetas de cine (interactivo, por lotes)
python nfc/nfc_tarjetas_cine.py /carpeta/con/posters [-o /carpeta/salida]

# Generar página web de álbum (genera HTML + JSON en docs/albums/)
python album_web_generator.py /ruta/al/album [--db ruta/db.sqlite] [-o ruta/salida]
```

## Arquitectura

### Flujo NFC
1. `nfc/nfc_detect_uid.py` — lee el UID físico de las tarjetas presentadas al lector
2. `nfc/nfc_config_gen.py` — asocia UID→comando en `nfc_playlist.json`, con soporte para MoodeAudio (HTTP), VLC y MPV. Puede escribir un UID lógico personalizado en el bloque 4 de la tarjeta.
3. `nfc/nfc_reaccionar.py` — bucle de monitoreo: lee el ID lógico (bloque 4) o el UID físico, busca en `nfc_playlist.json` y ejecuta el comando via `subprocess.Popen`

### Generación de portadas
- `nfc/nfc_generar_portada.py` — genera dos imágenes PNG a 300 DPI (52×82 mm) para álbumes de música. Cara A: portada + metadatos. Cara B: tracklist + QR (wikipedia/genius o URL custom). Extrae metadatos con `mutagen`, descarga portadas de MusicBrainz.
- `nfc/nfc_tarjetas_cine.py` — genera portadas para películas/series. Cara A: poster ajustado al alto. Cara B: fondo color (celeste=serie, verde=película) + título + QR de IMDB/FilmAffinity.

### Web de música (`album_web_generator.py` + `modules/`)
Orquestado por `AlbumWebGenerator`, que coordina:
- `modules/album_processor.py` — extrae metadatos con `mutagen`
- `modules/image_finder.py` — busca imágenes de álbum/artista (MusicBrainz, local)
- `modules/lyrics_finder.py` — busca letras (`lyricsgenius`)
- `modules/link_finder.py` — busca enlaces externos (Spotify, etc.) usando `modules/database_manager.py`
- `modules/html_generator.py` — genera el HTML con tabs dinámicos (feeds, créditos, equipamiento)
- Genera `docs/albums/<nombre>.html`, `docs/albums/<nombre>_data.json`, actualiza `docs/albums-data.json`

### Reproductores (`reproductores/`)
- `reproductores/kodi_api_manager.py` — cliente JSON-RPC para Kodi. Gestiona biblioteca (películas, series, música), playlists y reproducción. Requiere JSON-RPC activado en Kodi > Configuración > Servicios > Control.
- `reproductores/setup_kodi.py` — script de configuración/setup de Kodi

### Web `docs/`
La web de música ya existe (generada por `album_web_generator.py`). **La web de cine necesita crearse desde cero.**

## Configuración

- `nfc_playlist.json` — mapeo UID→{nombre, comando} generado por `nfc_config_gen.py`
- `.env` — variables de entorno (credenciales Spotify, token Genius, etc.)
- Kodi requiere JSON-RPC en `http://<host>:8080/jsonrpc`

## Planificación pendiente

Flow para añadir nuevas tarjetas:
1. Asociar tarjeta NFC a álbum, serie o película (`nfc_config_gen.py`)
2. Generar portadas (`nfc_generar_portada.py` o `nfc_tarjetas_cine.py`)
3. Generar sección web — **la web de cine necesita crearse de cero**, solo existe la de música
4. El script `nfc_reaccionar.py` responde automáticamente a la nueva tarjeta
