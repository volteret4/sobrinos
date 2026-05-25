# Uso — Sobrinos

Todos los comandos se ejecutan desde el directorio raíz del proyecto con el entorno virtual activado.

---

## Flujo completo para una tarjeta nueva

1. **Asociar** la tarjeta a un álbum, película o serie → `nfc_config_gen.py`
2. **Generar portadas** para imprimir → `nfc_generar_portada.py` o `nfc_tarjetas_cine.py`
3. **Imprimir** las portadas en A4 → `imprimir_tarjetas.py`
4. **Monitorear** el lector para reaccionar al escaneo → `nfc_reaccionar.py`

---

## 1. Asociar tarjeta a contenido

```bash
python nfc/nfc_config_gen.py
```

El programa espera a que pongas una tarjeta en el lector y luego te guía:

1. Selecciona el reproductor → `4. Kodi`
2. Introduce la configuración de Kodi (host/puerto/credenciales) si es la primera vez
3. Elige categoría:
   - `1` Película
   - `2` Serie
   - `3` Álbum
   - `4` Artista (discografía completa)
4. Escribe parte del nombre para filtrar y selecciona de la lista
5. Retira la tarjeta — la asociación queda guardada en `nfc_playlist.json`

Para series, al escanear la tarjeta se reproduce automáticamente el **primer episodio no visto**.

---

## 2. Monitorear el lector (modo producción)

```bash
python nfc/nfc_reaccionar.py
```

Mantén este proceso corriendo siempre. Al detectar una tarjeta conocida ejecuta la acción asociada en Kodi. Muestra en pantalla qué tarjeta detectó y si la reproducción fue exitosa.

Para ejecutarlo como servicio en segundo plano, consulta la sección de systemd al final de este documento.

---

## 3. Detectar UID de una tarjeta

Útil para saber el identificador de una tarjeta antes de asociarla:

```bash
python nfc/nfc_detect_uid.py
```

---

## 4. Generar portadas para tarjetas de música

```bash
python nfc/nfc_generar_portada.py /ruta/al/album
```

Genera dos PNG a 300 DPI (52×82 mm):
- **Cara A**: portada del álbum + metadatos
- **Cara B**: tracklist + código QR

Con URL personalizada para el QR:
```bash
python nfc/nfc_generar_portada.py /ruta/al/album --custom-url https://tu_web/album
```

Los PNG se guardan en `docs/albums/`.

---

## 5. Generar portadas para tarjetas de cine

```bash
python nfc/nfc_tarjetas_cine.py /carpeta/con/posters
```

Genera pares de PNG (cara A y cara B) para cada película o serie de la carpeta.
Con carpeta de salida personalizada:

```bash
python nfc/nfc_tarjetas_cine.py /carpeta/con/posters -o docs/cine
```

Los PNG siguen el patrón `<titulo>_<fecha>_cara_A.png` / `cara_B.png`.

---

## 6. Imprimir tarjetas en A4

```bash
# Modo normal (A y B intercaladas, 9 tarjetas por página)
python nfc/imprimir_tarjetas.py

# Modo duplex (cara A en páginas impares, cara B en pares, volteada)
python nfc/imprimir_tarjetas.py --duplex

# Con marcas de corte
python nfc/imprimir_tarjetas.py --duplex --marcas

# Carpeta y archivo de salida personalizados
python nfc/imprimir_tarjetas.py --entrada docs/cine --salida mis_tarjetas.pdf
```

Caben **9 tarjetas por página A4** (3 columnas × 3 filas). El modo `--duplex` está pensado para impresoras con alimentación a doble cara girando por el borde corto.

---

## 7. Generar página web de un álbum

```bash
python album_web_generator.py /ruta/al/album
```

Genera `docs/albums/<nombre>.html` y `docs/albums/<nombre>_data.json`, y actualiza el índice `docs/albums-data.json`.

---

## Gestión de secretos

### Editar credenciales
```bash
sops edit secrets.enc.yaml
```

### Ver un valor concreto sin editar
```bash
sops decrypt secrets.enc.yaml | grep KODI_HOST
```

---

## Ejecutar el monitor como servicio systemd

Para que `nfc_reaccionar.py` arranque automáticamente con la Pi:

```bash
sudo nano /etc/systemd/system/sobrinos.service
```

```ini
[Unit]
Description=Sobrinos NFC Monitor
After=network.target

[Service]
User=mito
WorkingDirectory=/home/mito/gits/pollo/sobrinos
ExecStart=/home/mito/Scripts/python_venv/bin/python nfc/nfc_reaccionar.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable sobrinos
sudo systemctl start sobrinos
sudo systemctl status sobrinos
```

Ver logs en tiempo real:
```bash
journalctl -u sobrinos -f
```
