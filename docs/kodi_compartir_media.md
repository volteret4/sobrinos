# Compartir media al Kodi de la TV desde un servidor Linux

Guía para exponer la biblioteca de películas/series desde un servidor Linux hacia otro Kodi (TV, PC, Android), usando distintos protocolos. Kodi solo escanea a su librería lo que añades como **fuente de vídeo con scraper** — el protocolo da igual siempre que Kodi pueda leer los archivos.

---

## Añadir fuente en Kodi (común a todos los protocolos)

1. `Vídeos > Archivos > Añadir vídeos`
2. `Examinar > Introducir ruta` → escribe la URL del protocolo elegido
3. Asigna scraper: **The Movie Database** (películas) o **The TVDB** (series)
4. Acepta escanear la librería
5. Tras el escaneo, JSON-RPC verá todo el contenido

---

## NFS (recomendado en red local)

**Ventajas:** máximo rendimiento, sin contraseña, nativo en Linux.

### Servidor (Arch)

```bash
sudo pacman -S nfs-utils
sudo systemctl enable --now nfs-server
```

`/etc/exports`:
```
/mnt/pelis   192.168.1.0/24(ro,sync,no_subtree_check,no_root_squash)
/mnt/series  192.168.1.0/24(ro,sync,no_subtree_check,no_root_squash)
```

```bash
sudo exportfs -rav
sudo systemctl restart nfs-server
# Verificar que se exporta:
showmount -e localhost
```

### Servidor (Debian/Ubuntu)

```bash
sudo apt install nfs-kernel-server
# mismo /etc/exports, luego:
sudo exportfs -rav
sudo systemctl restart nfs-kernel-server
```

### URL en Kodi

```
nfs://192.168.1.10/mnt/pelis
nfs://192.168.1.10/mnt/series
```

> Si el navegador NFS de Kodi falla al descubrir servidores (error `nfs://`), usa siempre "Introducir ruta" con la URL completa.

---

## SMB/Samba (mejor compatibilidad, funciona también con Windows)

**Ventajas:** funciona en Android TV sin configuración extra, muy compatible.

### Servidor (Arch)

```bash
sudo pacman -S samba
```

`/etc/samba/smb.conf`:
```ini
[global]
workgroup = WORKGROUP
server string = Servidor Media
security = user

[pelis]
path = /mnt/pelis
browsable = yes
read only = yes
guest ok = yes

[series]
path = /mnt/series
browsable = yes
read only = yes
guest ok = yes
```

```bash
sudo systemctl enable --now smb nmb
# Verificar:
smbclient -L localhost -N
```

### Servidor (Debian/Ubuntu)

```bash
sudo apt install samba
# mismo smb.conf, luego:
sudo systemctl restart smbd nmbd
```

### URL en Kodi

```
smb://192.168.1.10/pelis
smb://192.168.1.10/series
```

Si el servidor requiere usuario:
```
smb://usuario:contraseña@192.168.1.10/pelis
```

---

## WebDAV (útil si hay firewall o quieres acceso desde internet)

**Ventajas:** funciona sobre HTTP/HTTPS, atraviesa firewalls, accesible desde fuera de la red local.

### Servidor con nginx (Arch/Debian)

```bash
# Arch:
sudo pacman -S nginx
# Debian:
sudo apt install nginx nginx-extras
```

`/etc/nginx/sites-available/webdav` (o en `/etc/nginx/nginx.conf`):
```nginx
server {
    listen 8081;

    location /pelis/ {
        alias /mnt/pelis/;
        autoindex on;
        dav_methods GET HEAD OPTIONS;
        # Para escritura (no necesario para Kodi):
        # dav_methods PUT DELETE MKCOL COPY MOVE;
    }

    location /series/ {
        alias /mnt/series/;
        autoindex on;
        dav_methods GET HEAD OPTIONS;
    }
}
```

```bash
sudo systemctl enable --now nginx
```

Con autenticación básica:
```bash
sudo apt install apache2-utils  # o: sudo pacman -S apache
htpasswd -c /etc/nginx/.htpasswd kodi
# añadir en el location:
#   auth_basic "Media";
#   auth_basic_user_file /etc/nginx/.htpasswd;
```

### URL en Kodi

```
webdav://192.168.1.10:8081/pelis/
webdav://192.168.1.10:8081/series/
# Con HTTPS:
webdavs://192.168.1.10:8443/pelis/
# Con usuario:
webdav://usuario:contraseña@192.168.1.10:8081/pelis/
```

---

## FTP (alternativa simple, menor rendimiento)

**Ventajas:** muy fácil de configurar, compatible con casi todo.  
**Desventajas:** sin cifrado (usar solo en red local), peor rendimiento que NFS/SMB.

### Servidor (Arch)

```bash
sudo pacman -S vsftpd
```

`/etc/vsftpd.conf`:
```ini
anonymous_enable=YES
local_enable=NO
write_enable=NO
anon_root=/mnt/media
anon_max_rate=0
listen=YES
```

```bash
sudo systemctl enable --now vsftpd
```

### Servidor (Debian/Ubuntu)

```bash
sudo apt install vsftpd
# mismo vsftpd.conf
sudo systemctl restart vsftpd
```

### URL en Kodi

```
ftp://192.168.1.10/pelis
# Con usuario:
ftp://usuario:contraseña@192.168.1.10/pelis
```

---

## Comparativa

| Protocolo | Rendimiento | Configuración | Android TV | Fuera de LAN |
|-----------|-------------|---------------|------------|--------------|
| NFS       | ★★★★★       | Media         | Requiere app extra | No |
| SMB       | ★★★★☆       | Fácil         | Nativo     | No (sin VPN) |
| WebDAV    | ★★★☆☆       | Media         | Nativo     | Sí (con HTTPS) |
| FTP       | ★★☆☆☆       | Muy fácil     | Nativo     | No recomendado |

**Recomendación por caso de uso:**
- **Red local, Linux/PC:** NFS
- **Red local, Android TV:** SMB
- **Acceso remoto:** WebDAV con HTTPS + autenticación

---

## Apuntar el código al Kodi correcto

En `.env` cambiar `KODI_HOST` a la IP del Kodi que quieres controlar:

```env
KODI_HOST=192.168.1.XX   # IP de la TV con Kodi
KODI_PORT=8080
KODI_USER=kodi
KODI_PASSWORD=kodi
```

El JSON-RPC de Kodi se activa en: `Configuración > Servicios > Control > Permitir control remoto por HTTP`.
