## NFC Music Player

Con este proyecto podrás:

- Preparar una tarjeta NFC asociandola con un disco específico.
- Hacer que tu reproductor de música reproduzca un disco concreto al escanearla
- También podrás crear _portadas_ para esas tarjetas a escanear con tus discos favoritos.
- Incluso crear una web para mostrar más información sobre el disco escaneado que se añadirá como QR a la tarjeta.

### Requisitos

- Tarjetas NFC compatible. (52x82mm en el ejemplo, pero es adaptable).
- Lector de tarjetas NFC compatible. (En linux las más compatibles llevan el chip ACR122U).
- Reproductor de música que acepte comandos via terminal o api. (Por ejemplo: [deadbeef](https://github.com/DeaDBeeF-Player/deadbeef), [moodeaudio](https://github.com/moode-player/moode), [mpd](https://www.musicpd.org/), [mpv](https://mpv.io/), Spotify, [VLC](https://www.videolan.org/vlc/), etc.)
- Dispositivo capaz de ejecutar algúna distro de linux. (raspberry pi 4 con sistema operativo raspbian es el usado porque estaba en casa, probablemente overkill)
- Python y varios paquetes incluidos en `requirements.txt`.

## Instalación

Esto instala los paquetes necesarios para el uso del chip ACR122U en distro basada en debian

```bash
sudo apt-get install libacsccid1 pcscd pcsc-tools
```

Activa el demonio que leerá las tarjetas

```bash
sudo systemctl enable pcscd.socket
```

Añade estas lineas para desactivar los módulos nfc del kernel:

```bash
sudo nano /etc/modprobe.d/blacklist.conf
# Añade estas lineas al final
install nfc /bin/false
install pn533 /bin/false
```

Ya te debería permitir leer tarjetas usando `pcsc_scan`.

## Uso

#### Identificar tarjetas

Con el siguiente [script](https://github.com/volteret4/sobrinos/blob/main/nfc/nfc_detect_uid.py) podrás obtener el UID de cada tarjeta que mas tarde necesitaremos para reaccionar a las mismas.

#### Reaccionar a tarjetas

Una vez detectadas, podemos editar el siguiente [script](https://github.com/volteret4/sobrinos/blob/main/nfc/nfc_reaccionar.py) modificando la parte en que se identifica cada tarjeta con la función a realizar.

```json
TARJETAS_CONFIG = {
    "B2BA9C1E": { # Reemplaza con el UID real de tu tarjeta 1
        "nombre": "Tarjeta 1",
        "comando": ["touch", "/home/pi/sonidos.txt"]  # Ejemplo: Crear archivo test
    },
    "YYYYYYYY": {  # Reemplaza con el UID real de tu tarjeta 2
        "nombre": "Tarjeta 2",
        "comando": ["curl", "/home/pi/script1.py"],  # Ejemplo: ejecutar script
    },
    "ZZZZZZZZ": {  # Reemplaza con el UID real de tu tarjeta 3
        "nombre": "Tarjeta 3",
        "comando": ["systemctl", "restart", "nginx"],  # Ejemplo: reiniciar servicio
    }
}
```

> En esta ocasión usaremos moodeaudio para reproducir música. Podemos usar el siguiente commando `curl` para manejar moodeaudio:
> `curl -G -S -s --data-urlencode "cmd=REST_API_COMMAND" http://moode/command/`

> Para reproducir un disco especifico usaremos
> `curl -G -S -s --data-urlencode "cmd=play_item NAS/ruta/al/directorio" http://moode_url/command/`
> Ej:
> `curl -G -S -s --data-urlencode "cmd=play_item NAS/moode/moode/M/Mogwai/" http://moode_url/command/`

#### (Opcional) Crea imágenes para esas tarjetas

Con este [script](https://github.com/volteret4/sobrinos/blob/main/nfc/nfc_generar_portada.py) podremos crear imagenes con el tamaño de las tarjetas (52mmx82mm):

_CARA A:_

- Portada
- Artista
- Album
- Sello
- Fecha lanzamiento
- Género

_CARA B_

- Tracklist
- QR a wikipedia y genius

#### (Opcional 2) Crea una web con información para el QR de la tarjeta

Con este script podrás crear una web que recopilará información sobre el disco en cuestión.

```bash
# creará una html y actualizará el json para el index.html:
python album_web_generator.py /ruta/al/album

# buscará en la base de datos:
python album_web_generator.py /ruta/al/album --db ruta/a/db.sqlite

# ya no se guardarán en docs/albums los htmls creados.
python album_web_generator.py /ruta/al/album --db ruta/a/db.sqlite -o ruta/salida
```

Al usar el creador de portadas usa el flag `--custom-url https://tu_web.loquesea` para poder crear este QR en vez de wikipedia y genius.
