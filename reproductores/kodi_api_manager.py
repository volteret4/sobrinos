#!/usr/bin/env python3
"""
Kodi API Manager - Script para gestionar archivos, playlists y reproducción en Kodi
Requiere que Kodi tenga habilitada la interfaz JSON-RPC en Configuración > Servicios > Control
"""

import json
import requests
from typing import Dict, List, Optional, Any
import time

class KodiAPIManager:
    def __init__(self, host: str = "localhost", port: int = 8080, username: str = "", password: str = ""):
        """
        Inicializar el cliente de la API de Kodi

        Args:
            host: IP o hostname donde está ejecutándose Kodi
            port: Puerto de la interfaz web (por defecto 8080)
            username: Usuario (si está configurado)
            password: Contraseña (si está configurada)
        """
        self.base_url = f"http://{host}:{port}/jsonrpc"
        self.auth = (username, password) if username and password else None
        self.headers = {
            'Content-Type': 'application/json'
        }

    def _send_request(self, method: str, params: Dict = None) -> Dict:
        """Enviar petición JSON-RPC a Kodi"""
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "id": 1
        }
        if params:
            payload["params"] = params

        try:
            response = requests.post(
                self.base_url,
                data=json.dumps(payload),
                headers=self.headers,
                auth=self.auth,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error de conexión: {e}")
            return {"error": str(e)}

    # === GESTIÓN DE ARCHIVOS ===

    def get_sources(self, media_type: str = "video") -> List[Dict]:
        """
        Obtener las fuentes de medios configuradas

        Args:
            media_type: 'video', 'music', 'pictures'
        """
        result = self._send_request("Files.GetSources", {"media": media_type})
        return result.get("result", {}).get("sources", [])

    def browse_directory(self, directory: str, media_type: str = "video") -> List[Dict]:
        """
        Explorar contenido de un directorio

        Args:
            directory: Ruta del directorio a explorar
            media_type: Tipo de medios a buscar
        """
        params = {
            "directory": directory,
            "media": media_type,
            "properties": ["title", "file", "thumbnail", "fanart", "duration", "size"]
        }
        result = self._send_request("Files.GetDirectory", params)
        return result.get("result", {}).get("files", [])

    def search_files(self, search_term: str, media_type: str = "video") -> List[Dict]:
        """Buscar archivos por nombre"""
        sources = self.get_sources(media_type)
        all_files = []

        for source in sources:
            files = self.browse_directory(source["file"], media_type)
            matching_files = [f for f in files if search_term.lower() in f.get("label", "").lower()]
            all_files.extend(matching_files)

        return all_files

    # === GESTIÓN DE BIBLIOTECA ===

    def get_movies(self) -> List[Dict]:
        """Obtener todas las películas de la biblioteca"""
        params = {
            "properties": ["title", "year", "rating", "runtime", "plot", "file", "thumbnail", "fanart"]
        }
        result = self._send_request("VideoLibrary.GetMovies", params)
        return result.get("result", {}).get("movies", [])

    def get_tv_shows(self) -> List[Dict]:
        """Obtener todas las series de TV"""
        params = {
            "properties": ["title", "year", "rating", "plot", "thumbnail", "fanart"]
        }
        result = self._send_request("VideoLibrary.GetTVShows", params)
        return result.get("result", {}).get("tvshows", [])

    def get_episodes(self, tvshow_id: int) -> List[Dict]:
        """Obtener episodios de una serie específica"""
        params = {
            "tvshowid": tvshow_id,
            "properties": ["title", "season", "episode", "runtime", "file", "thumbnail"]
        }
        result = self._send_request("VideoLibrary.GetEpisodes", params)
        return result.get("result", {}).get("episodes", [])

    def get_music_artists(self) -> List[Dict]:
        """Obtener artistas de música"""
        params = {
            "properties": ["description", "genre", "fanart", "thumbnail"]
        }
        result = self._send_request("AudioLibrary.GetArtists", params)
        return result.get("result", {}).get("artists", [])

    def get_albums(self, artist_id: int = None) -> List[Dict]:
        """Obtener álbumes (opcionalmente de un artista específico)"""
        params = {
            "properties": ["title", "artist", "year", "rating", "thumbnail"]
        }
        if artist_id:
            params["filter"] = {"artistid": artist_id}

        result = self._send_request("AudioLibrary.GetAlbums", params)
        return result.get("result", {}).get("albums", [])

    def get_songs(self, album_id: int = None) -> List[Dict]:
        """Obtener canciones (opcionalmente de un álbum específico)"""
        params = {
            "properties": ["title", "artist", "album", "duration", "track", "file"]
        }
        if album_id:
            params["filter"] = {"albumid": album_id}

        result = self._send_request("AudioLibrary.GetSongs", params)
        return result.get("result", {}).get("songs", [])

    # === GESTIÓN DE PLAYLISTS ===

    def get_playlists(self) -> List[Dict]:
        """Obtener todas las playlists disponibles"""
        result = self._send_request("Playlist.GetPlaylists")
        return result.get("result", [])

    def get_playlist_items(self, playlist_id: int) -> List[Dict]:
        """Obtener contenido de una playlist específica"""
        params = {
            "playlistid": playlist_id,
            "properties": ["title", "artist", "album", "duration", "file", "thumbnail"]
        }
        result = self._send_request("Playlist.GetItems", params)
        return result.get("result", {}).get("items", [])

    def add_to_playlist(self, playlist_id: int, item: Dict) -> bool:
        """
        Añadir elemento a playlist

        Args:
            playlist_id: ID de la playlist (0=música, 1=video)
            item: Puede ser {"file": "path"} o {"movieid": id} o {"songid": id}, etc.
        """
        params = {
            "playlistid": playlist_id,
            "item": item
        }
        result = self._send_request("Playlist.Add", params)
        return "result" in result and result["result"] == "OK"

    def remove_from_playlist(self, playlist_id: int, position: int) -> bool:
        """Eliminar elemento de playlist por posición"""
        params = {
            "playlistid": playlist_id,
            "position": position
        }
        result = self._send_request("Playlist.Remove", params)
        return "result" in result and result["result"] == "OK"

    def clear_playlist(self, playlist_id: int) -> bool:
        """Limpiar playlist completamente"""
        params = {"playlistid": playlist_id}
        result = self._send_request("Playlist.Clear", params)
        return "result" in result and result["result"] == "OK"

    def swap_playlist_items(self, playlist_id: int, position1: int, position2: int) -> bool:
        """Intercambiar posición de dos elementos en playlist"""
        params = {
            "playlistid": playlist_id,
            "position1": position1,
            "position2": position2
        }
        result = self._send_request("Playlist.Swap", params)
        return "result" in result and result["result"] == "OK"

    # === CONTROL DE REPRODUCCIÓN ===

    def get_active_players(self) -> List[Dict]:
        """Obtener reproductores activos"""
        result = self._send_request("Player.GetActivePlayers")
        return result.get("result", [])

    def get_player_properties(self, player_id: int) -> Dict:
        """Obtener propiedades del reproductor"""
        params = {
            "playerid": player_id,
            "properties": ["time", "totaltime", "percentage", "speed", "position", "repeat", "shuffled"]
        }
        result = self._send_request("Player.GetProperties", params)
        return result.get("result", {})

    def get_current_item(self, player_id: int) -> Dict:
        """Obtener información del elemento actual en reproducción"""
        params = {
            "playerid": player_id,
            "properties": ["title", "artist", "album", "duration", "file", "thumbnail"]
        }
        result = self._send_request("Player.GetItem", params)
        return result.get("result", {}).get("item", {})

    def play_pause(self, player_id: int) -> bool:
        """Alternar reproducción/pausa"""
        params = {"playerid": player_id}
        result = self._send_request("Player.PlayPause", params)
        return "result" in result

    def stop_playback(self, player_id: int) -> bool:
        """Detener reproducción"""
        params = {"playerid": player_id}
        result = self._send_request("Player.Stop", params)
        return "result" in result and result["result"] == "OK"

    def next_track(self, player_id: int) -> bool:
        """Siguiente pista"""
        params = {"playerid": player_id, "to": "next"}
        result = self._send_request("Player.GoTo", params)
        return "result" in result and result["result"] == "OK"

    def previous_track(self, player_id: int) -> bool:
        """Pista anterior"""
        params = {"playerid": player_id, "to": "previous"}
        result = self._send_request("Player.GoTo", params)
        return "result" in result and result["result"] == "OK"

    def seek_to_position(self, player_id: int, position: int) -> bool:
        """
        Saltar a posición específica en playlist

        Args:
            player_id: ID del reproductor
            position: Posición en la playlist (empezando en 0)
        """
        params = {"playerid": player_id, "to": position}
        result = self._send_request("Player.GoTo", params)
        return "result" in result and result["result"] == "OK"

    def seek_to_time(self, player_id: int, hours: int = 0, minutes: int = 0, seconds: int = 0) -> bool:
        """Saltar a tiempo específico"""
        params = {
            "playerid": player_id,
            "value": {"hours": hours, "minutes": minutes, "seconds": seconds}
        }
        result = self._send_request("Player.Seek", params)
        return "result" in result

    def set_volume(self, volume: int) -> bool:
        """Establecer volumen (0-100)"""
        params = {"volume": max(0, min(100, volume))}
        result = self._send_request("Application.SetVolume", params)
        return "result" in result

    def get_volume(self) -> int:
        """Obtener volumen actual"""
        result = self._send_request("Application.GetProperties", {"properties": ["volume"]})
        return result.get("result", {}).get("volume", 0)

    def set_mute(self, mute: bool) -> bool:
        """Silenciar/activar audio"""
        params = {"mute": mute}
        result = self._send_request("Application.SetMute", params)
        return "result" in result

    def set_repeat_mode(self, player_id: int, repeat_mode: str) -> bool:
        """
        Establecer modo de repetición

        Args:
            repeat_mode: 'off', 'one', 'all'
        """
        params = {"playerid": player_id, "repeat": repeat_mode}
        result = self._send_request("Player.SetRepeat", params)
        return "result" in result and result["result"] == "OK"

    def set_shuffle(self, player_id: int, shuffle: bool) -> bool:
        """Activar/desactivar modo aleatorio"""
        params = {"playerid": player_id, "shuffle": shuffle}
        result = self._send_request("Player.SetShuffle", params)
        return "result" in result and result["result"] == "OK"

    # === FUNCIONES DE REPRODUCCIÓN DIRECTA ===

    def play_file(self, file_path: str) -> bool:
        """Reproducir archivo directamente"""
        params = {"item": {"file": file_path}}
        result = self._send_request("Player.Open", params)
        return "result" in result and result["result"] == "OK"

    def play_movie(self, movie_id: int) -> bool:
        """Reproducir película por ID"""
        params = {"item": {"movieid": movie_id}}
        result = self._send_request("Player.Open", params)
        return "result" in result and result["result"] == "OK"

    def play_episode(self, episode_id: int) -> bool:
        """Reproducir episodio por ID"""
        params = {"item": {"episodeid": episode_id}}
        result = self._send_request("Player.Open", params)
        return "result" in result and result["result"] == "OK"

    def play_song(self, song_id: int) -> bool:
        """Reproducir canción por ID"""
        params = {"item": {"songid": song_id}}
        result = self._send_request("Player.Open", params)
        return "result" in result and result["result"] == "OK"

    def play_playlist(self, playlist_id: int, position: int = 0) -> bool:
        """
        Reproducir playlist desde una posición específica

        Args:
            playlist_id: ID de la playlist
            position: Posición inicial (empezando en 0)
        """
        params = {
            "item": {"playlistid": playlist_id, "position": position}
        }
        result = self._send_request("Player.Open", params)
        return "result" in result and result["result"] == "OK"

    # === FUNCIONES AUXILIARES ===

    def get_player_status(self) -> Dict:
        """Obtener estado completo del reproductor"""
        players = self.get_active_players()
        if not players:
            return {"status": "stopped", "players": []}

        status = {"status": "playing", "players": []}
        for player in players:
            player_id = player["playerid"]
            properties = self.get_player_properties(player_id)
            current_item = self.get_current_item(player_id)

            status["players"].append({
                "id": player_id,
                "type": player["type"],
                "properties": properties,
                "current_item": current_item
            })

        return status

    def create_music_playlist_from_album(self, album_id: int) -> bool:
        """Crear playlist con todas las canciones de un álbum"""
        # Limpiar playlist de música (ID 0)
        self.clear_playlist(0)

        # Obtener canciones del álbum
        songs = self.get_songs(album_id)

        # Añadir cada canción a la playlist
        for song in songs:
            self.add_to_playlist(0, {"songid": song["songid"]})

        return True

    def get_status_summary(self) -> str:
        """Obtener resumen del estado actual"""
        status = self.get_player_status()

        if status["status"] == "stopped":
            return "Kodi no está reproduciendo nada actualmente"

        summary = ["Estado de Kodi:"]
        for player in status["players"]:
            player_type = player["type"]
            current = player["current_item"]
            props = player["properties"]

            title = current.get("title", "Desconocido")
            if player_type == "audio":
                artist = current.get("artist", [""])[0] if current.get("artist") else ""
                summary.append(f"🎵 Reproduciendo: {title} - {artist}")
            else:
                summary.append(f"🎬 Reproduciendo: {title}")

            time_info = props.get("time", {})
            total_time = props.get("totaltime", {})
            percentage = props.get("percentage", 0)

            if time_info and total_time:
                current_time = f"{time_info.get('hours', 0):02d}:{time_info.get('minutes', 0):02d}:{time_info.get('seconds', 0):02d}"
                total = f"{total_time.get('hours', 0):02d}:{total_time.get('minutes', 0):02d}:{total_time.get('seconds', 0):02d}"
                summary.append(f"⏱️  Progreso: {current_time}/{total} ({percentage:.1f}%)")

        return "\n".join(summary)


def demo_usage():
    """Función de demostración del uso de la API"""
    # Conectar a Kodi (ajusta la IP/puerto según tu configuración)
    kodi = KodiAPIManager(host="192.168.1.100", port=8080)

    print("=== DEMO DE KODI API MANAGER ===\n")

    # 1. Verificar estado actual
    print("1. Estado actual del reproductor:")
    print(kodi.get_status_summary())
    print()

    # 2. Explorar fuentes de video
    print("2. Fuentes de video disponibles:")
    video_sources = kodi.get_sources("video")
    for source in video_sources:
        print(f"   - {source['label']}: {source['file']}")
    print()

    # 3. Obtener películas de la biblioteca
    print("3. Primeras 5 películas en la biblioteca:")
    movies = kodi.get_movies()[:5]
    for movie in movies:
        print(f"   - {movie['title']} ({movie.get('year', 'N/A')})")
    print()

    # 4. Gestionar playlists
    print("4. Playlists disponibles:")
    playlists = kodi.get_playlists()
    for playlist in playlists:
        print(f"   - {playlist['type']} (ID: {playlist['playlistid']})")
    print()

    # 5. Información del volumen
    volume = kodi.get_volume()
    print(f"5. Volumen actual: {volume}%")
    print()

    print("Demo completada. Revisa las funciones disponibles en la clase KodiAPIManager.")


if __name__ == "__main__":
    demo_usage()
