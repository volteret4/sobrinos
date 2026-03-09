#!/usr/bin/env python3
"""
Configurador automático para Kodi API Manager
Este script ayuda a configurar y probar la conexión con Kodi
"""

import requests
import json
import time
import subprocess
import sys

def instalar_dependencias():
    """Instalar dependencias necesarias"""
    print("📦 Instalando dependencias...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
        print("✅ Dependencias instaladas correctamente")
        return True
    except subprocess.CalledProcessError:
        print("❌ Error instalando dependencias")
        return False

def detectar_kodi_red():
    """Intentar detectar Kodi en la red local"""
    print("🔍 Buscando Kodi en la red local...")

    # IPs comunes a probar
    ips_comunes = [
        "127.0.0.1",
        "localhost",
        "192.168.1.100", "192.168.1.101", "192.168.1.102", "192.168.1.103",
        "192.168.0.100", "192.168.0.101", "192.168.0.102", "192.168.0.103"
    ]

    puertos_comunes = [8080, 8081, 80]

    for ip in ips_comunes:
        for puerto in puertos_comunes:
            if probar_conexion_kodi(ip, puerto):
                return ip, puerto

    return None, None

def probar_conexion_kodi(host, puerto, usuario="", password=""):
    """Probar conexión con Kodi"""
    url = f"http://{host}:{puerto}/jsonrpc"

    payload = {
        "jsonrpc": "2.0",
        "method": "JSONRPC.Ping",
        "id": 1
    }

    headers = {'Content-Type': 'application/json'}
    auth = (usuario, password) if usuario and password else None

    try:
        response = requests.post(
            url,
            data=json.dumps(payload),
            headers=headers,
            auth=auth,
            timeout=3
        )

        if response.status_code == 200:
            result = response.json()
            return result.get("result") == "pong"

    except requests.exceptions.RequestException:
        pass

    return False

def obtener_info_kodi(host, puerto, usuario="", password=""):
    """Obtener información básica de Kodi"""
    url = f"http://{host}:{puerto}/jsonrpc"
    auth = (usuario, password) if usuario and password else None
    headers = {'Content-Type': 'application/json'}

    # Obtener versión
    payload_version = {
        "jsonrpc": "2.0",
        "method": "Application.GetProperties",
        "params": {"properties": ["name", "version"]},
        "id": 1
    }

    try:
        response = requests.post(url, data=json.dumps(payload_version), headers=headers, auth=auth, timeout=5)
        if response.status_code == 200:
            result = response.json()
            app_info = result.get("result", {})

            # Obtener estado de reproductores
            payload_players = {
                "jsonrpc": "2.0",
                "method": "Player.GetActivePlayers",
                "id": 2
            }

            players_response = requests.post(url, data=json.dumps(payload_players), headers=headers, auth=auth, timeout=5)
            active_players = []
            if players_response.status_code == 200:
                players_result = players_response.json()
                active_players = players_result.get("result", [])

            return {
                "app_name": app_info.get("name", "Desconocido"),
                "version": app_info.get("version", {}),
                "active_players": active_players
            }
    except:
        pass

    return None

def configuracion_manual():
    """Configuración manual de conexión"""
    print("\n🔧 Configuración manual de conexión")
    print("=" * 50)

    host = input("Host/IP de Kodi (localhost): ").strip() or "localhost"
    puerto = input("Puerto (8080): ").strip() or "8080"
    try:
        puerto = int(puerto)
    except ValueError:
        puerto = 8080

    print("\n🔐 Autenticación (opcional, presiona Enter para omitir)")
    usuario = input("Usuario: ").strip()
    password = input("Contraseña: ").strip()

    return host, puerto, usuario, password

def generar_config_file(host, puerto, usuario, password):
    """Generar archivo de configuración"""
    config = f"""# Configuración de Kodi API Manager
KODI_HOST = "{host}"
KODI_PORT = {puerto}
KODI_USERNAME = "{usuario}"
KODI_PASSWORD = "{password}"

# Ejemplo de uso:
# from kodi_api_manager import KodiAPIManager
# kodi = KodiAPIManager(
#     host=KODI_HOST,
#     port=KODI_PORT,
#     username=KODI_USERNAME,
#     password=KODI_PASSWORD
# )
"""

    with open("/home/claude/kodi_config.py", "w") as f:
        f.write(config)

    print(f"📄 Archivo de configuración guardado: kodi_config.py")

def test_funcionalidades(host, puerto, usuario, password):
    """Probar funcionalidades básicas"""
    print("\n🧪 Probando funcionalidades básicas...")

    try:
        # Importar nuestro manager
        sys.path.insert(0, '/home/claude')
        from kodi_api_manager import KodiAPIManager

        kodi = KodiAPIManager(host=host, port=puerto, username=usuario, password=password)

        # Test 1: Obtener fuentes de video
        print("   📁 Probando obtención de fuentes...")
        sources = kodi.get_sources("video")
        print(f"   ✅ {len(sources)} fuentes de video encontradas")

        # Test 2: Obtener películas
        print("   🎬 Probando biblioteca de películas...")
        movies = kodi.get_movies()
        print(f"   ✅ {len(movies)} películas en la biblioteca")

        # Test 3: Obtener playlists
        print("   📋 Probando playlists...")
        playlists = kodi.get_playlists()
        print(f"   ✅ {len(playlists)} playlists disponibles")

        # Test 4: Estado de reproducción
        print("   ▶️  Probando estado de reproducción...")
        status = kodi.get_player_status()
        if status["status"] == "stopped":
            print("   ✅ No hay reproducción activa")
        else:
            print(f"   ✅ {len(status['players'])} reproductor(es) activo(s)")

        # Test 5: Volumen
        print("   🔊 Probando control de volumen...")
        volume = kodi.get_volume()
        print(f"   ✅ Volumen actual: {volume}%")

        print("\n🎉 Todas las pruebas pasaron correctamente!")
        return True

    except Exception as e:
        print(f"\n❌ Error durante las pruebas: {e}")
        return False

def mostrar_instrucciones_kodi():
    """Mostrar instrucciones para habilitar la API en Kodi"""
    print("\n📋 INSTRUCCIONES PARA HABILITAR LA API EN KODI")
    print("=" * 60)
    print("1. Abre Kodi en tu dispositivo")
    print("2. Ve a: Configuración (icono de engranaje)")
    print("3. Selecciona: Servicios")
    print("4. Ve a: Control")
    print("5. Activa: 'Permitir control remoto via HTTP'")
    print("6. Configura:")
    print("   • Puerto: 8080 (recomendado)")
    print("   • Usuario/Contraseña: (opcional pero recomendado)")
    print("   • Permitir desde otras redes: SÍ (si usas desde otro dispositivo)")
    print("7. Guarda los cambios")
    print("8. Reinicia Kodi si es necesario")
    print("=" * 60)

def main():
    """Función principal del configurador"""
    print("🎯 CONFIGURADOR KODI API MANAGER")
    print("=" * 50)
    print("Este asistente te ayudará a configurar la conexión con Kodi")
    print()

    # Paso 1: Instalar dependencias
    if not instalar_dependencias():
        return

    # Paso 2: Intentar detectar Kodi automáticamente
    host_detectado, puerto_detectado = detectar_kodi_red()

    if host_detectado and puerto_detectado:
        print(f"🎉 ¡Kodi detectado en {host_detectado}:{puerto_detectado}!")

        # Obtener información de Kodi
        info = obtener_info_kodi(host_detectado, puerto_detectado)
        if info:
            print(f"   📱 Aplicación: {info['app_name']}")
            version = info['version']
            if version:
                print(f"   📋 Versión: {version.get('major', '?')}.{version.get('minor', '?')}")

            if info['active_players']:
                print(f"   ▶️  Reproductores activos: {len(info['active_players'])}")
            else:
                print("   ⏸️  Sin reproducción activa")

        usar_detectado = input("\n¿Usar esta configuración? (s/n): ").lower() == 's'

        if usar_detectado:
            host, puerto, usuario, password = host_detectado, puerto_detectado, "", ""
        else:
            host, puerto, usuario, password = configuracion_manual()
    else:
        print("❌ No se pudo detectar Kodi automáticamente")
        mostrar_instrucciones_kodi()
        input("\nPresiona Enter cuando hayas configurado Kodi...")
        host, puerto, usuario, password = configuracion_manual()

    # Paso 3: Probar conexión final
    print(f"\n🔧 Probando conexión con {host}:{puerto}...")
    if probar_conexion_kodi(host, puerto, usuario, password):
        print("✅ Conexión exitosa!")

        # Paso 4: Generar archivo de configuración
        generar_config_file(host, puerto, usuario, password)

        # Paso 5: Probar funcionalidades
        if test_funcionalidades(host, puerto, usuario, password):
            print("\n🎉 CONFIGURACIÓN COMPLETADA EXITOSAMENTE!")
            print("\n📁 Archivos disponibles:")
            print("   • kodi_api_manager.py - Clase principal")
            print("   • ejemplos_kodi.py - Ejemplos de uso")
            print("   • kodi_config.py - Tu configuración")
            print("   • README.md - Documentación")

            print("\n🚀 Para empezar, ejecuta:")
            print("   python ejemplos_kodi.py")

        else:
            print("\n⚠️  Configuración guardada pero hay problemas con algunas funcionalidades")
            print("Revisa la documentación y verifica la configuración de Kodi")
    else:
        print("❌ No se pudo conectar con Kodi")
        print("\n💡 Posibles soluciones:")
        print("   • Verifica que Kodi esté ejecutándose")
        print("   • Confirma que la interfaz HTTP esté habilitada")
        print("   • Revisa la IP/puerto")
        print("   • Verifica las credenciales")

if __name__ == "__main__":
    main()
