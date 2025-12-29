import re
import subprocess
import time
import shutil
from log import log

class DBusManager:
    def __init__(self, preferred_target=None):
        self.preferred_target = preferred_target
        self.available = shutil.which("dbus-send") is not None 

    def set_preference(self, target_name):
        self.preferred_target = target_name

    def _run_cmd(self, args):
        try:
            result = subprocess.run(
                args, capture_output=True, text=True, check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return None

    def get_players(self):
        if not self.available: return []
        cmd = ["dbus-send", "--session", "--dest=org.freedesktop.DBus", "--type=method_call", "--print-reply", "/org/freedesktop/DBus", "org.freedesktop.DBus.ListNames"]
        output = self._run_cmd(cmd)
        if not output: return []
        players = []
        for line in output.split("\n"):
            match = re.search(r'"(org\.mpris\.MediaPlayer2\.[^"]+)"', line)
            if match: players.append(match.group(1))
        return players

    def get_active_player(self):
        players = self.get_players()
        if not players: return None, "No Active Players"
        target = None
        if self.preferred_target:
            target = next((p for p in players if self.preferred_target.lower() in p.lower()), None)
        if not target:
            target = next((p for p in players if "mpv" in p), None)
        if not target:
            target = players[0]
        return target, target

    def send_files(self, file_paths):
        dest, name = self.get_active_player()
        if not dest: return False, name
        count = 0
        for path in file_paths:
            uri = f"file://{path}"
            cmd = ["dbus-send", "--session", "--type=method_call", f"--dest={dest}", "/org/mpris/MediaPlayer2", "org.mpris.MediaPlayer2.Player.OpenUri", f"string:{uri}"]
            if self._run_cmd(cmd) is not None:
                count += 1
                time.sleep(0.05)
        return True, f"Sent {count} tracks to {name}"

    def control(self, command):
        dest, name = self.get_active_player()
        if not dest: return False, name
        method_map = {"next": "Next", "prev": "Previous", "play": "Play", "pause": "Pause", "toggle": "PlayPause", "stop": "Stop"}
        if command not in method_map: return False, "Unknown Command"
        cmd = ["dbus-send", "--session", "--type=method_call", f"--dest={dest}", "/org/mpris/MediaPlayer2", f"org.mpris.MediaPlayer2.Player.{method_map[command]}"]
        if self._run_cmd(cmd) is not None:
            return True, f"Executed {command} on {name}"
        return False, "Command Failed"

def execute_player_command(command, playlist, dbus_manager):
    if command in ["next", "prev", "play", "pause", "toggle", "stop"]:
        ok, msg = dbus_manager.control(command)
        color = "green" if ok else "red"
        log(f"[{color}]📡 DBus: {msg}[/]")
        return

    if not playlist and command in ["mpv", "vlc", "send"]:
        log("[red]❌ No playlist cached! Use 'p <text>' first.[/]")
        return

    paths = [item['path'] for item in playlist] if playlist else []

    if command == "send":
        if not dbus_manager.available:
            log("[red]❌ 'dbus-send' missing[/]")
            return
        ok, msg = dbus_manager.send_files(paths)
        color = "green" if ok else "red"
        log(f"[{color}]📡 DBus: {msg}[/]")
    elif command == "mpv":
        log(f"[green]🔊 MPV ({len(playlist)} trks)[/]")
        subprocess.Popen(['mpv', '--force-window', '--geometry=600x600'] + paths, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True)
    elif command == "vlc":
        log(f"[green]🟠 VLC ({len(playlist)} trks)[/]")
        subprocess.Popen(['vlc', '--one-instance', '--playlist-enqueue'] + paths, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True)
