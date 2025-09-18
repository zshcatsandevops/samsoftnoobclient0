import os
import sys
import subprocess
import platform
import urllib.request
import zipfile
import json
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import re
import hashlib
import configparser
import threading
import socket
from datetime import datetime
from PIL import Image
import tarfile
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Dict, List, Any
import time
import uuid

sys.setrecursionlimit(10000)  # Increased recursion limit

# Define constants for directories and URLs
MINECRAFT_DIR = os.path.expanduser("~/.minecraft")
VERSIONS_DIR = os.path.join(MINECRAFT_DIR, "versions")
INSTALLED_MODS_DIR = os.path.join(MINECRAFT_DIR, "installed_mods")
MODS_DIR = os.path.join(MINECRAFT_DIR, "mods")
CONFIG_DIR = os.path.join(MINECRAFT_DIR, "config")
ASSETS_DIR = os.path.join(MINECRAFT_DIR, "assets")
JAVA_DIR = os.path.expanduser("~/.nooblauncher/java")
VERSION_MANIFEST_URL = "https://launchermeta.mojang.com/mc/game/version_manifest.json"
FABRIC_LOADER_URL = "https://meta.fabricmc.net/v2/versions/loader/"
FORGE_PROMOS_URL = "https://files.minecraftforge.net/net/minecraftforge/forge/promotions_slim.json"
MODRINTH_API = "https://api.modrinth.com/v2"

# NoobLauncher theme (fused from Samsoft and HyperNoob)
THEME = {
    'bg': '#1a1a1a',
    'sidebar': '#141414',
    'accent': '#ff4500',  # HyperNoob orange for punch
    'text': '#ffffff',
    'text_secondary': '#808080',
    'button': '#1f1f1f',
    'button_hover': '#2d2d2d',
    'input_bg': '#242424',
    'success': '#43b581',
    'warning': '#f04747',
    'highlight': '#f1c40f'
}

class NoobLauncher(tk.Tk):  # Renamed and merged class
    def __init__(self):
        """Initialize the NoobLauncher with fused mod support."""
        super().__init__()
        self.title("NoobLauncher 0.X")
        self.geometry("1280x720")
        self.minsize(1100, 650)
        self.configure(bg=THEME['bg'])
        self.versions: Dict[str, Dict[str, Any]] = {}
        self.version_categories = {
            "All Versions": [],
            "Latest Release": [],
            "Latest Snapshot": [],
            "Release": [],
            "Snapshot": [],
            "Forge": [],
            "Fabric": [],
            "Old Beta": [],
            "Old Alpha": []
        }
        self.mod_profiles: Dict[str, List[str]] = {"Default": [], "Lunar": []}
        self.selected_profile = "Default"
        self.authenticated = True
        self.user_data = {"username": "Player", "uuid": self.generate_offline_uuid("Player"), "access_token": "0"}
        self.download_progress = ttk.Progressbar(self, mode='indeterminate')
        self.installed_mods = []
        self.mod_vars = {}
        self.downloaded_versions = set()  # Track downloaded versions to prevent recursion loops
       
        self.load_mod_profiles()
       
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure("TCombobox",
                             fieldbackground=THEME['input_bg'],
                             background=THEME['input_bg'],
                             foreground=THEME['text'],
                             arrowcolor=THEME['text'],
                             borderwidth=1,
                             lightcolor=THEME['accent'],
                             darkcolor=THEME['accent'])
        self.style.configure("Vertical.TScrollbar",
                             background=THEME['accent'],
                             arrowcolor=THEME['text'],
                             troughcolor=THEME['sidebar'])
        self.style.configure("TCheckbutton",
                             background=THEME['sidebar'],
                             foreground=THEME['text'],
                             indicatorcolor=THEME['accent'])
        self.style.map("TCheckbutton",
                       background=[('active', THEME['button_hover'])],
                       indicatorcolor=[('selected', THEME['success'])])
       
        self.init_ui()
        threading.Thread(target=self.check_server_status, daemon=True).start()
        self.load_version_manifest()

    def init_ui(self):
        """Set up the fused UI with mod profiles and changelog."""
        main_container = tk.Frame(self, bg=THEME['bg'])
        main_container.pack(fill="both", expand=True, padx=20, pady=20)
        sidebar = tk.Frame(main_container, bg=THEME['sidebar'], width=300)
        sidebar.pack(side="left", fill="y", padx=(0, 20))
        sidebar.pack_propagate(False)
        logo_frame = tk.Frame(sidebar, bg=THEME['sidebar'])
        logo_frame.pack(fill="x", pady=(20, 30))
        tk.Label(logo_frame, text="⚡", font=("Arial", 48), bg=THEME['sidebar'], fg=THEME['accent']).pack()
        tk.Label(logo_frame, text="NOOBLAUNCHER\n0.X", font=("Arial", 18, "bold"),
                 bg=THEME['sidebar'], fg=THEME['text'], justify="center").pack()
        version_frame = tk.LabelFrame(sidebar, text="VERSION SELECTOR", bg=THEME['sidebar'], fg=THEME['text_secondary'],
                                      font=("Arial", 10, "bold"), bd=0, relief="flat")
        version_frame.pack(fill="x", padx=20, pady=(0, 10))
        self.category_combo = ttk.Combobox(version_frame, values=list(self.version_categories.keys()),
                                           state="readonly", font=("Arial", 11))
        self.category_combo.pack(fill="x", pady=(10, 5))
        self.category_combo.set("All Versions")
        self.category_combo.bind("<<ComboboxSelected>>", self.update_version_list)
        version_inner = tk.Frame(version_frame, bg=THEME['sidebar'])
        version_inner.pack(fill="x", pady=5)
        self.version_combo = ttk.Combobox(version_inner, state="readonly", font=("Arial", 11))
        self.version_combo.pack(side="left", fill="x", expand=True)
        tk.Button(version_inner, text="Refresh", font=("Arial", 9), bg=THEME['button'], fg=THEME['text'],
                  command=self.load_version_manifest).pack(side="right", padx=(5, 0))
        # Fused mod profiles from HyperNoob
        profile_frame = tk.LabelFrame(sidebar, text="MOD PROFILES", bg=THEME['sidebar'], fg=THEME['text_secondary'],
                                      font=("Arial", 10, "bold"), bd=0, relief="flat")
        profile_frame.pack(fill="x", padx=20, pady=(0, 10))
        self.profile_combo = ttk.Combobox(profile_frame, values=list(self.mod_profiles.keys()),
                                          state="readonly", font=("Arial", 11))
        self.profile_combo.pack(fill="x", pady=(10, 5))
        self.profile_combo.set("Default")
        self.profile_combo.bind("<<ComboboxSelected>>", self.update_mod_profile)
        tk.Button(profile_frame, text="Manage Mods", font=("Arial", 11, "bold"),
                  bg=THEME['button'], fg=THEME['text'], bd=0, padx=20, pady=8,
                  command=self.open_mod_manager).pack(fill="x", pady=5)
        settings_frame = tk.LabelFrame(sidebar, text="GAME SETTINGS", bg=THEME['sidebar'], fg=THEME['text_secondary'],
                                       font=("Arial", 10, "bold"), bd=0, relief="flat")
        settings_frame.pack(fill="x", padx=20, pady=(0, 10))
        username_frame = tk.Frame(settings_frame, bg=THEME['sidebar'])
        username_frame.pack(fill="x", pady=(10, 5))
        tk.Label(username_frame, text="USERNAME", font=("Arial", 9, "bold"),
                 bg=THEME['sidebar'], fg=THEME['text_secondary']).pack(anchor="w")
        self.username_input = tk.Entry(username_frame, font=("Arial", 11), bg=THEME['input_bg'],
                                       fg=THEME['text'], insertbackground=THEME['text'], bd=0, relief="solid")
        self.username_input.pack(fill="x", pady=(5, 0))
        self.username_input.insert(0, "Enter Username")
        self.username_input.bind("<FocusIn>", lambda e: self.clear_placeholder(self.username_input, "Enter Username"))
        self.username_input.bind("<FocusOut>", lambda e: self.set_placeholder(self.username_input, "Enter Username"))
        self.username_input.config(fg=THEME['text_secondary'])
        ram_frame = tk.Frame(settings_frame, bg=THEME['sidebar'])
        ram_frame.pack(fill="x", pady=10)
        tk.Label(ram_frame, text="RAM ALLOCATION", font=("Arial", 9, "bold"),
                 bg=THEME['sidebar'], fg=THEME['text_secondary']).pack(side="left")
        self.ram_value_label = tk.Label(ram_frame, text="4GB", font=("Arial", 9),
                                        bg=THEME['sidebar'], fg=THEME['text'])
        self.ram_value_label.pack(side="right")
        self.ram_scale = tk.Scale(ram_frame, from_=1, to=16, orient="horizontal",
                                  bg=THEME['sidebar'], fg=THEME['text'],
                                  activebackground=THEME['accent'],
                                  highlightthickness=0, bd=0,
                                  troughcolor=THEME['input_bg'],
                                  command=lambda v: self.ram_value_label.config(text=f"{int(float(v))}GB"))
        self.ram_scale.set(4)
        self.ram_scale.pack(fill="x")
        button_frame = tk.Frame(sidebar, bg=THEME['sidebar'])
        button_frame.pack(fill="x", padx=20, pady=(0, 20))
        def on_enter(e):
            e.widget.configure(bg=THEME['button_hover'])
        def on_leave(e):
            e.widget.configure(bg=THEME['button'])
        def on_accent_enter(e):
            e.widget.configure(bg=THEME['highlight'], fg=THEME['bg'])
        def on_accent_leave(e):
            e.widget.configure(bg=THEME['accent'], fg=THEME['text'])
        skin_button = tk.Button(button_frame, text="🖼️ CHANGE SKIN", font=("Arial", 11, "bold"),
                                bg=THEME['button'], fg=THEME['text'],
                                bd=0, padx=20, pady=8, command=self.select_skin)
        skin_button.pack(fill="x", pady=(0, 5))
        skin_button.bind("<Enter>", on_enter)
        skin_button.bind("<Leave>", on_leave)
        launch_button = tk.Button(button_frame, text="🚀 PLAY", font=("Arial", 13, "bold"),
                                  bg=THEME['accent'], fg=THEME['text'],
                                  bd=0, padx=20, pady=12, command=self.launch_game)
        launch_button.pack(fill="x")
        launch_button.bind("<Enter>", on_accent_enter)
        launch_button.bind("<Leave>", on_accent_leave)
        content_area = tk.Frame(main_container, bg=THEME['bg'])
        content_area.pack(side="left", fill="both", expand=True)
        tk.Label(content_area, text="Welcome to NOOBLAUNCHER!", font=("Arial", 24, "bold"),
                 bg=THEME['bg'], fg=THEME['text']).pack(pady=20)
        tk.Label(content_area, text="0.X LAUNCHER - Modded & Fused!", font=("Arial", 14),
                 bg=THEME['bg'], fg=THEME['text_secondary']).pack()
        self.download_progress.pack(fill="x", pady=10)
        self.download_progress.pack_forget()
        changelog_frame = tk.LabelFrame(content_area, text="NOOBLAUNCHER - CHANGELOG", bg=THEME['bg'], fg=THEME['accent'],
                                        font=("Arial", 12, "bold"), bd=0, relief="flat")
        changelog_frame.pack(fill="x", pady=(20, 20))
        changelog_items = [
            "🚀 NoobLauncher 0.X - Fused Modded Release",
            "⚡ FPS Optimization: Automatic maxFps=60 and VSync disabled",
            "🔧 Intelligent Java 21 auto-installation system",
            "🎨 Dark theme UI with Noob design language",
            "🖼️ Custom skin management (mod support required)",
            "🌍 Full version manifest support with categorization",
            "💾 SHA1 checksum verification for all downloads",
            "📦 Modrinth integration for easy mod installation",
            "⚙️ Forge & Fabric loader support with mod profiles"
        ]
        for item in changelog_items:
            item_frame = tk.Frame(changelog_frame, bg=THEME['sidebar'])
            item_frame.pack(fill="x", padx=10, pady=5)
            tk.Label(item_frame, text=item, font=("Arial", 11), bg=THEME['sidebar'], fg=THEME['text']).pack(anchor="w")
        server_frame = tk.LabelFrame(content_area, text="SERVER STATUS", bg=THEME['bg'], fg=THEME['accent'],
                                     font=("Arial", 12, "bold"), bd=0, relief="flat")
        server_frame.pack(fill="x", pady=(20, 20))
        self.server_status_label = tk.Label(server_frame, text="Checking server status...",
                                            font=("Arial", 11), bg=THEME['bg'], fg=THEME['text'])
        self.server_status_label.pack(pady=10)

    def set_placeholder(self, entry: tk.Entry, placeholder: str) -> None:
        if entry.get().strip() == "" or entry.get().strip() == placeholder:
            entry.delete(0, tk.END)
            entry.insert(0, placeholder)
            entry.config(fg=THEME['text_secondary'])

    def clear_placeholder(self, entry: tk.Entry, placeholder: str) -> None:
        if entry.get() == placeholder:
            entry.delete(0, tk.END)
            entry.config(fg=THEME['text'])

    def check_server_status(self) -> None:
        try:
            socket.create_connection(("mc.hypixel.net", 25565), timeout=5)
            self.after(0, lambda: self.server_status_label.config(text="Hypixel: Online", fg=THEME['success']))
        except Exception:
            self.after(0, lambda: self.server_status_label.config(text="Hypixel: Offline", fg=THEME['warning']))
        self.after(60000, self.check_server_status)

    def update_version_list(self, event=None) -> None:
        category = self.category_combo.get()
        values = []
        for vid in self.version_categories[category]:
            loader = self.versions[vid].get("loader", "vanilla")
            label = f"{vid} ({loader.upper()})"
            values.append(label)
        self.version_combo['values'] = values
        if values:
            self.version_combo.current(0)

    def update_mod_profile(self, event=None) -> None:
        self.selected_profile = self.profile_combo.get()
        print(f"Selected mod profile: {self.selected_profile}")

    def show_progress(self, show: bool = True) -> None:
        if show:
            self.download_progress.pack(fill="x", pady=10)
            self.download_progress.start(10)
        else:
            self.download_progress.stop()
            self.download_progress.pack_forget()

    def launch_game(self) -> None:
        threading.Thread(target=self._prepare_and_launch, daemon=True).start()

    def _prepare_and_launch(self) -> None:
        self.show_progress(True)
        try:
            current_username = self.username_input.get()
            username = current_username.strip() if current_username != "Enter Username" and current_username.strip() else "Player"
            self.user_data["username"] = username
            self.user_data["uuid"] = self.generate_offline_uuid(username)
            self.authenticated = True
            version_display = self.version_combo.get()
            if not version_display:
                self.after(0, lambda: messagebox.showerror("Error", "No version selected"))
                return
            version = version_display.split(" (")[0]
            loader_str = version_display.split(" (")[1].rstrip(")") if "(" in version_display else "vanilla"
            loader = loader_str.lower()
            if version not in self.versions:
                self.after(0, lambda: messagebox.showerror("Error", f"Invalid version: {version}"))
                return
            ram = int(self.ram_scale.get())
            self.install_java_if_needed()
            version_info = self.versions[version]
            if loader != "vanilla" and 'url' not in version_info:
                self.after(0, lambda: messagebox.showerror("Error", "Modloader versions not fully implemented yet. Use vanilla for now."))
                return
            if not self.download_version_files(version, version_info):
                return
            self.download_assets(version)
            self.setup_mod_profile()
            self.modify_options_txt()
            version_path = os.path.join(VERSIONS_DIR, f"{version}.json")
            with open(version_path, 'r') as f:
                data = json.load(f)
            lib_paths, natives_dir = self.install_libraries(version, data)
            jar_path = os.path.join(VERSIONS_DIR, f"{version}.jar")
            lib_paths.append(jar_path)
            sep = ';' if platform.system() == 'Windows' else ':'
            classpath = sep.join(lib_paths)
            jvm_args = self.resolve_arguments(data.get('arguments', {}).get('jvm', []), data, username, version) if 'arguments' in data else []
            if 'minecraftArguments' in data:
                game_args = data['minecraftArguments'].format(**self.get_placeholders(username, version, data)).split()
            else:
                game_args = self.resolve_arguments(data['arguments']['game'], data, username, version)
            main_class = data['mainClass']
            command = [
                "java",
                f"-Xmx{ram}G",
                f"-Xms{ram}G",
                f"-Djava.library.path={natives_dir}",
            ] + jvm_args + [
                f"-cp {classpath}",
                main_class,
            ] + game_args
            java_path = self.get_java_path()
            if not java_path or not os.path.exists(java_path):
                raise ValueError("Java installation failed.")
            full_command = [java_path] + command[1:]
            process = subprocess.Popen(full_command, cwd=MINECRAFT_DIR,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"🚀 Launched Minecraft {version} for user {username}")
            self.after(0, lambda: messagebox.showinfo("NoobLauncher", f"Minecraft {version} launched successfully!"))
        except Exception as e:
            error_msg = str(e) or 'Unknown error'
            print(f"Failed to launch: {error_msg}")
            self.after(0, lambda msg=error_msg: messagebox.showerror("Error", f"Failed to launch Minecraft: {msg}"))
        finally:
            self.show_progress(False)

    def setup_mod_profile(self):
        """Setup mods dir for selected profile."""
        if os.path.exists(MODS_DIR):
            shutil.rmtree(MODS_DIR)
        os.makedirs(MODS_DIR, exist_ok=True)
        profile_mods = self.mod_profiles.get(self.selected_profile, [])
        for mod_filename in profile_mods:
            src = os.path.join(INSTALLED_MODS_DIR, mod_filename)
            if os.path.exists(src):
                shutil.copy2(src, MODS_DIR)

    def open_mod_manager(self) -> None:
        mod_window = tk.Toplevel(self)
        mod_window.title("Mod Manager")
        mod_window.geometry("600x500")
        mod_window.configure(bg=THEME['bg'])
        tk.Label(mod_window, text="MOD MANAGER", font=("Arial", 18, "bold"),
                 bg=THEME['bg'], fg=THEME['text']).pack(pady=20)
        mods_frame = tk.Frame(mod_window, bg=THEME['bg'])
        mods_frame.pack(fill="both", expand=True, padx=20)
        mods_canvas = tk.Canvas(mods_frame, bg=THEME['bg'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(mods_frame, orient="vertical", command=mods_canvas.yview)
        mods_scrollable_frame = tk.Frame(mods_canvas, bg=THEME['bg'])
        mods_scrollable_frame.bind(
            "<Configure>",
            lambda e: mods_canvas.configure(scrollregion=mods_canvas.bbox("all"))
        )
        mods_canvas.create_window((0, 0), window=mods_scrollable_frame, anchor="nw")
        mods_canvas.configure(yscrollcommand=scrollbar.set)
        mods_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.installed_mods = self.load_installed_mods()
        self.mod_vars: Dict[str, tk.BooleanVar] = {}
        for mod in self.installed_mods:
            var = tk.BooleanVar(value=mod["filename"] in self.mod_profiles.get(self.selected_profile, []))
            cb = ttk.Checkbutton(mods_scrollable_frame,
                                 text=f"{mod['name']} v{mod['version']} - {mod['source']}",
                                 variable=var,
                                 command=lambda m=mod['filename'], v=var: self.toggle_mod(m, v.get()))
            cb.pack(anchor="w", padx=10, pady=3)
            self.mod_vars[mod['filename']] = var
        button_frame = tk.Frame(mod_window, bg=THEME['bg'])
        button_frame.pack(fill="x", pady=10)
       
        tk.Button(button_frame, text="Add Mod from File", font=("Arial", 11),
                  bg=THEME['button'], fg=THEME['text'],
                  command=self.add_mod_from_file).pack(side="left", padx=5, fill="x", expand=True)
       
        tk.Button(button_frame, text="Install Mod from Modrinth", font=("Arial", 11),
                  bg=THEME['accent'], fg=THEME['text'],
                  command=self.install_mod_from_modrinth).pack(side="right", padx=5, fill="x", expand=True)
       
        tk.Button(button_frame, text="Save Profile", font=("Arial", 11),
                  bg=THEME['success'], fg=THEME['text'],
                  command=self.save_mod_profile).pack(side="right", padx=(0, 5), fill="x", expand=True)
       
        mod_window.protocol("WM_DELETE_WINDOW", lambda: self.on_mod_window_close(mod_window))

    def generate_offline_uuid(self, username: str) -> str:
        """Generate an offline UUID for the given username."""
        hash_input = f"OfflinePlayer:{username}"
        digest = hashlib.md5(hash_input.encode('utf-8')).digest()
        digest = bytearray(digest)
        digest[6] = (digest[6] & 0x0f) | 0x30
        digest[8] = (digest[8] & 0x3f) | 0x80
        return str(uuid.UUID(bytes=bytes(digest)))

    def load_version_manifest(self) -> None:
        """Load the Minecraft version manifest and categorize versions."""
        try:
            with urllib.request.urlopen(VERSION_MANIFEST_URL) as response:
                manifest = json.loads(response.read().decode('utf-8'))
            self.versions = {}
            for version in manifest['versions']:
                self.versions[version['id']] = version
                self.version_categories["All Versions"].append(version['id'])
                if version['type'] == 'release':
                    self.version_categories["Release"].append(version['id'])
                elif version['type'] == 'snapshot':
                    self.version_categories["Snapshot"].append(version['id'])
                elif version['type'] == 'old_beta':
                    self.version_categories["Old Beta"].append(version['id'])
                elif version['type'] == 'old_alpha':
                    self.version_categories["Old Alpha"].append(version['id'])
            if 'latest' in manifest:
                self.version_categories["Latest Release"].append(manifest['latest']['release'])
                self.version_categories["Latest Snapshot"].append(manifest['latest']['snapshot'])
            # Add Forge and Fabric versions
            self.load_forge_versions()
            self.load_fabric_versions()
            self.update_version_list()
        except Exception as e:
            print(f"Failed to load version manifest: {e}")
            messagebox.showerror("Error", "Failed to load version manifest")

    def load_forge_versions(self) -> None:
        """Load Forge versions from promotions json."""
        try:
            with urllib.request.urlopen(FORGE_PROMOS_URL) as response:
                promo_data = json.loads(response.read().decode('utf-8'))
            for mc_v, forges in promo_data.get('promos', {}).items():
                if isinstance(forges, dict) and 'recommended' in forges:
                    forge_v = forges['recommended']
                    v = f"{mc_v}-forge-{forge_v}"
                    installer_url = f"https://files.minecraftforge.net/maven/net/minecraftforge/forge/{mc_v}-{forge_v}/forge-{mc_v}-{forge_v}-installer.jar"
                    self.versions[v] = {'id': v, 'type': 'release', 'loader': 'forge', 'url': installer_url, 'mc_version': mc_v}
                    self.version_categories["Forge"].append(v)
                    self.version_categories["All Versions"].append(v)
        except Exception as e:
            print(f"Failed to load Forge versions: {e}")

    def load_fabric_versions(self) -> None:
        """Load Fabric versions from Fabric meta."""
        try:
            mc_versions_url = "https://meta.fabricmc.net/v2/versions/game"
            with urllib.request.urlopen(mc_versions_url) as response:
                mc_versions = json.loads(response.read().decode('utf-8'))
            for mc_v in mc_versions:
                version_id = mc_v['version']
                url = f"{FABRIC_LOADER_URL}{version_id}/"
                with urllib.request.urlopen(url) as response:
                    data = json.loads(response.read().decode('utf-8'))
                if isinstance(data, list) and data:
                    item = data[-1]
                    loaders = item['loaders']
                    for loader in loaders:
                        v = f"{version_id}-fabric-{loader['version']}"
                        if v not in self.versions:
                            self.versions[v] = {'id': v, 'type': 'release', 'loader': 'fabric', 'url': url, 'mc_version': version_id}
                            self.version_categories["Fabric"].append(v)
                            self.version_categories["All Versions"].append(v)
        except Exception as e:
            print(f"Failed to load Fabric versions: {e}")

    def download_version_files(self, version: str, version_info: Dict[str, Any]) -> bool:
        """Download version JAR and JSON if not present, handle modloaders."""
        if version in self.downloaded_versions:
            return True
        self.downloaded_versions.add(version)
        version_path = os.path.join(VERSIONS_DIR, f"{version}.json")
        if os.path.exists(version_path):
            return True
        try:
            if 'url' not in version_info:
                raise ValueError("No URL for version")
            loader = version_info.get('loader', 'vanilla')
            with urllib.request.urlopen(version_info['url']) as response:
                loader_response = json.loads(response.read().decode('utf-8'))
            if loader == 'fabric':
                mc_version = version_info['mc_version']
                if mc_version not in self.versions:
                    raise ValueError("Vanilla version not found for Fabric")
                vanilla_info = self.versions[mc_version]
                vanilla_path = os.path.join(VERSIONS_DIR, f"{mc_version}.json")
                if not os.path.exists(vanilla_path):
                    if not self.download_version_files(mc_version, vanilla_info):
                        raise ValueError("Failed to download vanilla for Fabric")
                with open(vanilla_path, 'r') as f:
                    vanilla_data = json.load(f)
                data = vanilla_data.copy()
                if isinstance(loader_response, list) and loader_response:
                    loader_item = loader_response[-1]
                    launcher_meta = loader_item['launcherMeta']
                    data['libraries'] += launcher_meta['libraries'].get('common', [])
                    data['libraries'] += launcher_meta['libraries'].get('client', [])
                    data['mainClass'] = launcher_meta['mainClass']['client']
                    if 'arguments' in launcher_meta:
                        data.setdefault('arguments', {'jvm': [], 'game': []})
                        data['arguments']['jvm'] += launcher_meta['arguments'].get('common', []) + launcher_meta['arguments'].get('client', [])
                        data['arguments']['game'] += launcher_meta['arguments'].get('common', []) + launcher_meta['arguments'].get('client', [])
                    data.setdefault('arguments', {'game': []})
                    data['arguments']['game'].extend(["--versionType", f"fabric-loader:{loader_item['loader']['version']}"])
                else:
                    raise ValueError("No loader data available")
                data['id'] = version
                with open(version_path, 'w') as f:
                    json.dump(data, f)
                vanilla_jar_path = os.path.join(VERSIONS_DIR, f"{mc_version}.jar")
                if not os.path.exists(vanilla_jar_path):
                    vanilla_jar_url = vanilla_data['downloads']['client']['url']
                    with urllib.request.urlopen(vanilla_jar_url) as resp:
                        with open(vanilla_jar_path, 'wb') as f:
                            f.write(resp.read())
                    expected_sha = vanilla_data['downloads']['client']['sha1']
                    actual_sha = hashlib.sha1(open(vanilla_jar_path, 'rb').read()).hexdigest()
                    if actual_sha != expected_sha:
                        raise ValueError("SHA1 mismatch for vanilla JAR")
                shutil.copy2(vanilla_jar_path, os.path.join(VERSIONS_DIR, f"{version}.jar"))
            elif loader == 'forge':
                installer_path = os.path.join(VERSIONS_DIR, f"{version}-installer.jar")
                if not os.path.exists(installer_path):
                    with urllib.request.urlopen(version_info['url']) as resp:
                        with open(installer_path, 'wb') as f:
                            f.write(resp.read())
                java_path = self.get_java_path()
                subprocess.check_call([java_path, "-jar", installer_path, "--installClient", VERSIONS_DIR])
                if not os.path.exists(version_path):
                    raise ValueError("Forge installation failed - JSON not generated")
                with open(version_path, 'r') as f:
                    data = json.load(f)
                os.remove(installer_path)
            else:
                with open(version_path, 'w') as f:
                    json.dump(loader_response, f)
                data = loader_response
                jar_url = data['downloads']['client']['url']
                jar_path = os.path.join(VERSIONS_DIR, f"{version}.jar")
                with urllib.request.urlopen(jar_url) as resp:
                    with open(jar_path, 'wb') as f:
                        f.write(resp.read())
                expected_sha = data['downloads']['client']['sha1']
                actual_sha = hashlib.sha1(open(jar_path, 'rb').read()).hexdigest()
                if actual_sha != expected_sha:
                    raise ValueError("SHA1 mismatch for JAR")
            return True
        except Exception as e:
            print(f"Failed to download version files: {e}")
            self.after(0, lambda: messagebox.showerror("Error", f"Failed to download version: {e}"))
            return False
        finally:
            if version in self.downloaded_versions:
                self.downloaded_versions.remove(version)

    # Fused library and asset methods from HyperNoob
    def install_libraries(self, version: str, data: Dict[str, Any]) -> tuple[List[str], str]:
        lib_dir = os.path.join(MINECRAFT_DIR, "libraries")
        os.makedirs(lib_dir, exist_ok=True)
        lib_paths = []
        natives_dir = os.path.join(VERSIONS_DIR, version, "natives")
        os.makedirs(natives_dir, exist_ok=True)
        for lib in data['libraries']:
            if not self.apply_rules(lib.get('rules', [])):
                continue
            name_parts = lib['name'].split(':')
            if len(name_parts) < 3:
                continue
            group, artifact, version_lib = name_parts[0], name_parts[1], name_parts[2]
            path = '/'.join([group.replace('.', '/'), artifact, f"{artifact}-{version_lib}.jar"])
            lib_path = os.path.join(lib_dir, path)
            os.makedirs(os.path.dirname(lib_path), exist_ok=True)
            if not os.path.exists(lib_path):
                if 'downloads' in lib and 'artifact' in lib['downloads']:
                    artifact_dl = lib['downloads']['artifact']
                    dl_url = artifact_dl['url'] + artifact_dl['path']
                    try:
                        with urllib.request.urlopen(dl_url) as resp:
                            with open(lib_path, 'wb') as f:
                                f.write(resp.read())
                        if 'sha1' in artifact_dl:
                            actual_sha = hashlib.sha1(open(lib_path, 'rb').read()).hexdigest()
                            if actual_sha != artifact_dl['sha1']:
                                os.remove(lib_path)
                                continue
                    except Exception:
                        continue
                else:
                    dl_url = f"https://libraries.minecraft.net/{path}"
                    try:
                        with urllib.request.urlopen(dl_url) as resp:
                            with open(lib_path, 'wb') as f:
                                f.write(resp.read())
                    except Exception:
                        continue
            if os.path.exists(lib_path):
                lib_paths.append(lib_path)
            # Handle natives
            if 'downloads' in lib and 'natives' in lib['downloads'] and platform.system().lower() in lib['downloads']['natives']:
                natives = lib['downloads']['natives'][platform.system().lower()]
                if 'classifiers' in natives:
                    for classifier, rel_path in natives['classifiers'].items():
                        nat_path = '/'.join([group.replace('.', '/'), artifact, f"{artifact}-{version_lib}-{classifier}.jar"])
                        nat_local = os.path.join(lib_dir, nat_path)
                        if not os.path.exists(nat_local):
                            nat_url = natives['url'] + rel_path
                            try:
                                with urllib.request.urlopen(nat_url) as resp:
                                    with open(nat_local, 'wb') as f:
                                        f.write(resp.read())
                            except Exception:
                                continue
                        try:
                            with zipfile.ZipFile(nat_local) as z:
                                for file_name in z.namelist():
                                    if file_name.startswith('META-INF/'):
                                        continue
                                    target_path = os.path.join(natives_dir, file_name)
                                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                                    with z.open(file_name) as src, open(target_path, 'wb') as dst:
                                        shutil.copyfileobj(src, dst)
                        except Exception:
                            pass
        return lib_paths, natives_dir

    def apply_rules(self, rules: List[Dict]) -> bool:
        if not rules:
            return True
        os_name = platform.system().lower()
        for rule in rules:
            os_match = True
            if 'os' in rule:
                if 'name' in rule['os'] and rule['os']['name'] != os_name:
                    os_match = False
            if os_match and rule.get('action') == 'disallow':
                return False
        return True

    def get_placeholders(self, username: str, version: str, data: Dict) -> Dict[str, str]:
        return {
            "auth_player_name": username,
            "version_name": version,
            "game_directory": MINECRAFT_DIR,
            "assets_root": ASSETS_DIR,
            "assets_index_name": data['assetIndex']['id'],
            "auth_uuid": self.user_data["uuid"],
            "auth_access_token": self.user_data["access_token"],
            "user_type": "legacy",
            "auth_session": self.user_data["access_token"],
            "auth_offline_name": username,
        }

    def resolve_arguments(self, args: List[Any], data: Dict, username: str, version: str, depth: int = 0) -> List[str]:
        if depth > 50:
            return []
        resolved = []
        placeholders = self.get_placeholders(username, version, data)
        for item in args:
            if isinstance(item, dict):
                if not self.apply_rules(item.get('rules', [])):
                    continue
                value = item.get('value')
                if isinstance(value, str):
                    try:
                        formatted = value.format(**placeholders)
                        resolved.append(formatted)
                    except KeyError:
                        resolved.append(value)
                elif isinstance(value, list):
                    resolved += self.resolve_arguments(value, data, username, version, depth + 1)
            elif isinstance(item, str):
                try:
                    formatted = item.format(**placeholders)
                    resolved.append(formatted)
                except KeyError:
                    resolved.append(item)
        return resolved

    def download_assets(self, version: str) -> None:
        try:
            version_path = os.path.join(VERSIONS_DIR, f"{version}.json")
            with open(version_path, 'r') as f:
                data = json.load(f)
            asset_index_url = data['assetIndex']['url']
            with urllib.request.urlopen(asset_index_url) as response:
                index = json.loads(response.read().decode('utf-8'))
            objects_dir = os.path.join(ASSETS_DIR, "objects")
            os.makedirs(objects_dir, exist_ok=True)
            with ThreadPoolExecutor(max_workers=8) as executor:
                futures = []
                for obj_hash, obj in index['objects'].items():
                    path = os.path.join(objects_dir, obj_hash[:2], obj_hash)
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    if not os.path.exists(path):
                        url = f"https://resources.download.minecraft.net/{obj_hash[:2]}/{obj_hash}"
                        futures.append(executor.submit(self._download_asset, url, path, obj['hash']))
                for future in futures:
                    try:
                        future.result(timeout=30)
                    except Exception as e:
                        print(f"Asset download failed: {e}")
        except Exception as e:
            print(f"Failed to download assets: {e}")

    def _download_asset(self, url: str, path: str, expected_hash: str) -> None:
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                with open(path, 'wb') as f:
                    shutil.copyfileobj(resp, f)
            actual_hash = hashlib.sha1(open(path, 'rb').read()).hexdigest()
            if actual_hash != expected_hash:
                os.remove(path)
                raise ValueError(f"Hash mismatch for {path}")
        except Exception as e:
            if os.path.exists(path):
                os.remove(path)
            raise e

    def modify_options_txt(self) -> None:
        options_path = os.path.join(MINECRAFT_DIR, "options.txt")
        if os.path.exists(options_path):
            with open(options_path, 'r') as f:
                content = f.read()
            content = re.sub(r'fpsMax:.*', 'fpsMax:60', content)
            content = re.sub(r'vsync:.*', 'vsync:false', content)
            with open(options_path, 'w') as f:
                f.write(content)
        else:
            with open(options_path, 'w') as f:
                f.write("fpsMax:60\nvsync:false\n")

    def get_java_path(self) -> str:
        self.install_java_if_needed()
        return os.path.join(JAVA_DIR, "java", "bin", "java")

    def install_java_if_needed(self) -> None:
        java_path = self.get_java_path()
        if os.path.exists(java_path):
            return
        os.makedirs(JAVA_DIR, exist_ok=True)
        system = platform.system()
        if system == "Windows":
            java_zip = "OpenJDK21U-jdk_x64_windows_hotspot_21.0.1_12.zip"
            url = f"https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.1%2B12/{java_zip}"
        else:
            java_zip = "OpenJDK21U-jdk_x64_linux_hotspot_21.0.1_12.tar.gz"
            url = f"https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.1%2B12/{java_zip}"
        temp_path = os.path.join(JAVA_DIR, java_zip)
        try:
            with urllib.request.urlopen(url) as response:
                with open(temp_path, 'wb') as f:
                    f.write(response.read())
            if system == "Windows":
                with zipfile.ZipFile(temp_path, 'r') as z:
                    z.extractall(JAVA_DIR)
            else:
                with tarfile.open(temp_path, 'r:gz') as tar:
                    tar.extractall(JAVA_DIR)
                java_bin = os.path.join(JAVA_DIR, "jdk-21.0.1+12", "bin", "java")
                os.chmod(java_bin, 0o755)
            extracted_dir = os.path.join(JAVA_DIR, "jdk-21.0.1+12")
            os.rename(extracted_dir, os.path.join(JAVA_DIR, "java"))
            os.remove(temp_path)
            print("Java 21 installed.")
        except Exception as e:
            print(f"Failed to install Java: {e}")
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def select_skin(self) -> None:
        file_path = filedialog.askopenfilename(title="Select Skin", filetypes=[("PNG files", "*.png")])
        if file_path:
            skin_dir = os.path.join(ASSETS_DIR, "skins")
            os.makedirs(skin_dir, exist_ok=True)
            shutil.copy(file_path, os.path.join(skin_dir, f"{self.user_data['username']}.png"))
            messagebox.showinfo("Success", "Skin applied! (Requires mod for in-game change)")

    def load_mod_profiles(self) -> None:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        config_path = os.path.join(CONFIG_DIR, "nooblauncher_profiles.json")
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                loaded = json.load(f)
                self.mod_profiles.update(loaded)

    def save_mod_profiles(self) -> None:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        config_path = os.path.join(CONFIG_DIR, "nooblauncher_profiles.json")
        with open(config_path, 'w') as f:
            json.dump(self.mod_profiles, f)

    def load_installed_mods(self) -> List[Dict[str, Any]]:
        mods = []
        os.makedirs(INSTALLED_MODS_DIR, exist_ok=True)
        for file in os.listdir(INSTALLED_MODS_DIR):
            if file.endswith('.jar'):
                mods.append({
                    'filename': file,
                    'name': file.split('-')[0].replace('.jar', ''),
                    'version': '1.0',
                    'source': 'File'
                })
        return mods

    def toggle_mod(self, mod_filename: str, enabled: bool) -> None:
        profile = self.mod_profiles.setdefault(self.selected_profile, [])
        if enabled:
            if mod_filename not in profile:
                profile.append(mod_filename)
        else:
            if mod_filename in profile:
                profile.remove(mod_filename)

    def add_mod_from_file(self) -> None:
        file_path = filedialog.askopenfilename(title="Select Mod JAR", filetypes=[("JAR files", "*.jar")])
        if file_path:
            os.makedirs(INSTALLED_MODS_DIR, exist_ok=True)
            dest = os.path.join(INSTALLED_MODS_DIR, os.path.basename(file_path))
            shutil.copy(file_path, dest)
            new_mod = {
                'filename': os.path.basename(file_path),
                'name': os.path.basename(file_path).split('-')[0].replace('.jar', ''),
                'version': '1.0',
                'source': 'File'
            }
            self.installed_mods.append(new_mod)
            messagebox.showinfo("Success", "Mod added!")

    def install_mod_from_modrinth(self) -> None:
        mod_window = tk.Toplevel(self)
        mod_window.title("Modrinth Search")
        mod_window.geometry("400x300")
        mod_window.configure(bg=THEME['bg'])
        tk.Label(mod_window, text="Mod Name:", bg=THEME['bg'], fg=THEME['text']).pack(pady=10)
        search_entry = tk.Entry(mod_window, bg=THEME['input_bg'], fg=THEME['text'])
        search_entry.pack(pady=5)
        def search_mods():
            query = search_entry.get()
            if not query:
                return
            try:
                url = f"{MODRINTH_API}/search?query={query}"
                with urllib.request.urlopen(url) as response:
                    data = json.loads(response.read().decode('utf-8'))
                if data['hits']:
                    mod_id = data['hits'][0]['project_id']
                    version_url = f"{MODRINTH_API}/project/{mod_id}/version"
                    with urllib.request.urlopen(version_url) as v_response:
                        v_data = json.loads(v_response.read().decode('utf-8'))[0]
                    dl_url = v_data['files'][0]['url']
                    filename = v_data['files'][0]['filename']
                    os.makedirs(INSTALLED_MODS_DIR, exist_ok=True)
                    with urllib.request.urlopen(dl_url) as dl_response:
                        with open(os.path.join(INSTALLED_MODS_DIR, filename), 'wb') as f:
                            f.write(dl_response.read())
                    new_mod = {
                        'filename': filename,
                        'name': v_data['name'],
                        'version': v_data['version_number'],
                        'source': 'Modrinth'
                    }
                    self.installed_mods.append(new_mod)
                    messagebox.showinfo("Success", f"Mod {v_data['name']} installed!")
                    mod_window.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to install mod: {e}")
        tk.Button(mod_window, text="Search & Install", command=search_mods, bg=THEME['accent'], fg=THEME['text']).pack(pady=10)

    def save_mod_profile(self) -> None:
        self.mod_profiles[self.selected_profile] = [
            mod for mod, var in self.mod_vars.items() if var.get()
        ]
        self.save_mod_profiles()
        messagebox.showinfo("Success", "Profile saved!")

    def on_mod_window_close(self, window: tk.Toplevel) -> None:
        self.save_mod_profiles()
        window.destroy()

    def run(self):
        self.mainloop()

# Entry point
if __name__ == "__main__":
    app = NoobLauncher()
    app.run()
