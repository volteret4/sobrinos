# Instalación — Sobrinos

Sistema NFC para reproducir música, películas y series en Kodi al escanear una tarjeta física.

## Hardware necesario

- Raspberry Pi (cualquier modelo con USB)
- Lector NFC ACR122U (conectado por USB a la Pi)
- Servidor/dispositivo con Kodi corriendo y accesible en red
- TV con app Kodi configurada contra el servidor (opcional, para visualización)

---

## 1. Dependencias del sistema

```bash
sudo apt-get update
sudo apt-get install -y \
    libpcsclite-dev \
    libacsccid1 \
    pcscd \
    pcsc-tools \
    python3-venv \
    python3-pip \
    age
```

### Activar el servicio NFC

```bash
sudo systemctl enable pcscd.socket
sudo systemctl start pcscd.socket
```

### Permisos de usuario (evita tener que usar sudo)

```bash
sudo usermod -aG plugdev $USER
```

Cierra sesión y vuelve a entrar para que el grupo surta efecto.

---

## 2. Entorno virtual Python

```bash
python3 -m venv ~/Scripts/python_venv
source ~/Scripts/python_venv/bin/activate
```

Añade esta línea a `~/.bashrc` para activarlo automáticamente:

```bash
source ~/Scripts/python_venv/bin/activate
```

---

## 3. Dependencias Python

```bash
pip install -r requirements.txt
```

---

## 4. SOPS (cifrado de secretos)

### Instalar binario

Descarga el `.deb` para arm64 desde [github.com/getsops/sops/releases](https://github.com/getsops/sops/releases):

```bash
sudo dpkg -i sops_<version>_arm64.deb
hash -r
sops --version
```

### Copiar clave age desde la máquina principal

En la máquina donde ya está configurado age, copia la clave privada:

```bash
# En la máquina principal:
cat ~/.config/sops/age/keys.txt
```

En la Pi, crea el archivo con ese contenido:

```bash
mkdir -p ~/.config/sops/age
nano ~/.config/sops/age/keys.txt   # pega la clave y guarda
chmod 600 ~/.config/sops/age/keys.txt
```

La clave tiene este formato:
```
# created: ...
# public key: age1...
AGE-SECRET-KEY-1...
```

### Verificar acceso al archivo de secretos

```bash
sops edit secrets.enc.yaml
```

Si abre el editor, la configuración es correcta.

---

## 5. Configurar secretos

Edita el archivo cifrado para rellenar las credenciales:

```bash
sops edit secrets.enc.yaml
```

Rellena al menos los valores de Kodi (imprescindibles para el funcionamiento básico):

```yaml
KODI_HOST: "192.168.1.X"   # IP del dispositivo con Kodi
KODI_PORT: "8080"
KODI_USER: "kodi"
KODI_PASSWORD: "tu_contraseña"
```

El resto de credenciales (Spotify, Genius, TMDB...) son opcionales según las funciones que uses. Consulta `secrets.yaml.example` para la lista completa.

---

## 6. Kodi — activar control remoto

En el dispositivo con Kodi:

1. Ve a **Configuración → Servicios → Control**
2. Activa **Permitir control remoto via HTTP**
3. Configura el puerto (por defecto `8080`)
4. Activa **Permitir control remoto desde otras redes**
5. Establece usuario y contraseña

---

## Verificación rápida

```bash
# Comprobar que el lector NFC responde
pcsc_scan

# Comprobar conexión con Kodi
curl -u usuario:contraseña http://IP_KODI:8080/jsonrpc \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"JSONRPC.Ping","id":1}'
# Respuesta esperada: {"result":"pong",...}

# Detectar UID de una tarjeta NFC
python nfc/nfc_detect_uid.py
```
