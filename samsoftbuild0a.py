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

# Define constants
NOOB_CLIENT_DIR = os.path.expanduser("~/.noobclient")
VERSIONS_DIR = os.path.join(NOOB_CLIENT_DIR, "versions")
JAVA_DIR = os.path.join(NOOB_CLIENT_DIR, "java")
MODS_DIR = os.path.join(NOOB_CLIENT_DIR, "mods")
CONFIG_DIR = os.path.join(NOOB_CLIENT_DIR, "config")
ASSETS_DIR = os.path.join(NOOB_CLIENT_DIR, "assets")
VERSION_MANIFEST_URL = "https://launchermeta.mojang.com/mc/game/version_manifest.json"
FORGE_MANIFEST_URL = "https://files.minecraftforge.net/net/minecraftforge/forge/index.html"  # Note: Forge uses a different API; parsed via HTML/JSON
FABRIC_LOADER_URL = "https://meta.fabricmc.net/v2/versions/loader/"
MODRINTH_API = "https://api.modrinth.com/v2"

# TLauncher-inspired theme
THEME = {
    'bg': '#2c2f33',
    'sidebar': '#23272a',
    'accent': '#7289da',
    'text': '#ffffff',
    'text_secondary': '#99aab5',
    'button': '#2c2f33',
    'button_hover': '#36393f',
    'input_bg': '#202225',
    'success': '#43b581',
    'warning': '#f04747',
    'highlight': '#f1c40f'
}

class NoobClientLauncher(tk.Tk):
    def __init__(self):
        """Initialize the TLauncher-like launcher with enhanced modloader support."""
        super().__init__()
        self.title("NOOB CLIENT - TLauncher Edition")
        self.geometry("1280x720")
        self.minsize(1100, 650)
        self.configure(bg=THEME['bg'])
        self.versions: Dict[str, Dict[str, Any]] = {}
        self.version_categories = {
            "All Versions": [],
            "Release": [],
            "Snapshot": [],
            "Forge": [],
            "Fabric": []
        }
        self.mod_profiles: Dict[str, List[str]] = {"Default": [], "Lunar": []}  # Stores filenames
        self.selected_profile = "Default"
        self.authenticated = True
        self.user_data = {"username": "Player", "uuid": self.generate_offline_uuid("Player"), "access_token": "offline_token_123"}
        self.download_progress = ttk.Progressbar(self, mode='indeterminate')
        
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
        """Set up the enhanced TLauncher-inspired UI with progress indicators."""
        main_container = tk.Frame(self, bg=THEME['bg'])
        main_container.pack(fill="both", expand=True, padx=20, pady=20)

        sidebar = tk.Frame(main_container, bg=THEME['sidebar'], width=300)
        sidebar.pack(side="left", fill="y", padx=(0, 20))
        sidebar.pack_propagate(False)

        logo_frame = tk.Frame(sidebar, bg=THEME['sidebar'])
        logo_frame.pack(fill="x", pady=(20, 30))
        tk.Label(logo_frame, text="🎮", font=("Arial", 48), bg=THEME['sidebar'], fg=THEME['accent']).pack()
        tk.Label(logo_frame, text="NOOB CLIENT\nTLAUNCHER EDITION", font=("Arial", 18, "bold"), 
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
        self.ram_scale = tk.Scale(ram_frame, from_=1, to=32, orient="horizontal",
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

        launch_button = tk.Button(button_frame, text="🚀 LAUNCH GAME", font=("Arial", 13, "bold"),
                                  bg=THEME['accent'], fg=THEME['text'],
                                  bd=0, padx=20, pady=12, command=self.launch_game)
        launch_button.pack(fill="x")
        launch_button.bind("<Enter>", on_accent_enter)
        launch_button.bind("<Leave>", on_accent_leave)

        content_area = tk.Frame(main_container, bg=THEME['bg'])
        content_area.pack(side="left", fill="both", expand=True)

        tk.Label(content_area, text="Welcome to NOOB CLIENT!", font=("Arial", 24, "bold"),
                 bg=THEME['bg'], fg=THEME['text']).pack(pady=20)
        tk.Label(content_area, text="TLauncher Edition - Play Minecraft with ease!", font=("Arial", 14),
                 bg=THEME['bg'], fg=THEME['text_secondary']).pack()

        self.download_progress.pack(fill="x", pady=10)  # Global progress bar
        self.download_progress.pack_forget()  # Hidden initially

        server_frame = tk.LabelFrame(content_area, text="SERVER STATUS", bg=THEME['bg'], fg=THEME['accent'],
                                     font=("Arial", 12, "bold"), bd=0, relief="flat")
        server_frame.pack(fill="x", pady=(20, 20))
        self.server_status_label = tk.Label(server_frame, text="Checking server status...", 
                                            font=("Arial", 11), bg=THEME['bg'], fg=THEME['text'])
        self.server_status_label.pack(pady=10)

    def set_placeholder(self, entry: tk.Entry, placeholder: str) -> None:
        """Set placeholder text in entry widget."""
        if entry.get().strip() == "" or entry.get().strip() == placeholder:
            entry.delete(0, tk.END)
            entry.insert(0, placeholder)
            entry.config(fg=THEME['text_secondary'])

    def clear_placeholder(self, entry: tk.Entry, placeholder: str) -> None:
        """Clear placeholder text on focus."""
        if entry.get() == placeholder:
            entry.delete(0, tk.END)
            entry.config(fg=THEME['text'])

    def check_server_status(self) -> None:
        """Periodically check Hypixel server status."""
        try:
            socket.create_connection(("mc.hypixel.net", 25565), timeout=5)
            self.after(0, lambda: self.server_status_label.config(text="Hypixel: Online", fg=THEME['success']))
        except Exception:
            self.after(0, lambda: self.server_status_label.config(text="Hypixel: Offline", fg=THEME['warning']))
        self.after(60000, self.check_server_status)

    def update_version_list(self, event=None) -> None:
        """Update version combobox based on selected category."""
        category = self.category_combo.get()
        self.version_combo['values'] = self.version_categories[category]
        if self.version_combo['values']:
            self.version_combo.current(0)

    def update_mod_profile(self, event=None) -> None:
        """Update selected mod profile."""
        self.selected_profile = self.profile_combo.get()
        print(f"Selected mod profile: {self.selected_profile}")

    def show_progress(self, show: bool = True) -> None:
        """Toggle download progress bar visibility."""
        if show:
            self.download_progress.pack(fill="x", pady=10)
            self.download_progress.start(10)
        else:
            self.download_progress.stop()
            self.download_progress.pack_forget()

    def launch_game(self) -> None:
        """Launch the game in a separate thread."""
        threading.Thread(target=self._prepare_and_launch, daemon=True).start()

    def _prepare_and_launch(self) -> None:
        """Prepare environment and launch Minecraft."""
        self.show_progress(True)
        try:
            # Update user data
            current_username = self.username_input.get()
            username = current_username.strip() if current_username != "Enter Username" and current_username.strip() else "Player"
            self.user_data["username"] = username
            self.user_data["uuid"] = self.generate_offline_uuid(username)
            self.authenticated = True

            version = self.version_combo.get()
            if not version or version not in self.versions:
                self.after(0, lambda: messagebox.showerror("Error", f"Invalid or no version selected: {version}"))
                return

            ram = int(self.ram_scale.get())

            self.install_java_if_needed()
            version_info = self.versions[version]
            if not self.download_version_files(version, version_info):
                return

            self.download_assets(version)
            self.modify_options_txt()

            command = self.build_launch_command(version, username, ram)
            if not command:
                return

            java_path = self.get_java_path()
            if not java_path:
                raise ValueError("No suitable Java installation found.")

            full_command = [java_path] + command[1:] if command[0] == "java" else command

            process = subprocess.Popen(full_command, cwd=NOOB_CLIENT_DIR,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"🚀 Launched Minecraft {version} for user {username}")
            self.after(0, lambda: messagebox.showinfo("Noob Client", f"Minecraft {version} launched successfully!"))
        except Exception as e:
            print(f"Failed to launch: {e}")
            self.after(0, lambda: messagebox.showerror("Error", f"Failed to launch Minecraft: {e}"))
        finally:
            self.show_progress(False)

    def open_mod_manager(self) -> None:
        """Open enhanced mod manager window with better parsing."""
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
        
        tk.Button(button_frame, text="Browse Modrinth", font=("Arial", 11),
                  bg=THEME['button'], fg=THEME['text'],
                  command=self.browse_modrinth).pack(side="left", padx=5, fill="x", expand=True)

        tk.Button(button_frame, text="Install Lunar Pack", font=("Arial", 11),
                  bg=THEME['highlight'], fg=THEME['bg'],
                  command=self.install_lunar_pack).pack(side="left", padx=5, fill="x", expand=True)

        tk.Button(button_frame, text="Save Profile", font=("Arial", 11),
                  bg=THEME['accent'], fg=THEME['text'],
                  command=self.save_mod_profile).pack(side="left", padx=5, fill="x", expand=True)

    def install_lunar_pack(self) -> None:
        """Install performance mods for Lunar-like experience."""
        if messagebox.askyesno("Lunar Pack", "Install Sodium, Lithium, etc., for better FPS?"):
            lunar_mods = ["sodium", "lithium", "phosphor", "iris"]
            self.selected_profile = "Lunar"
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = [executor.submit(self.download_modrinth_mod, slug) for slug in lunar_mods]
                for future in futures:
                    future.result()  # Wait for all
            self.save_mod_profiles()
            messagebox.showinfo("Lunar Pack", "Performance mods installed! Use 'Lunar' profile.")

    def load_installed_mods(self) -> List[Dict[str, str]]:
        """Load and parse installed mods with better filename handling."""
        os.makedirs(MODS_DIR, exist_ok=True)
        mods = []
        for mod_file in os.listdir(MODS_DIR):
            if mod_file.endswith('.jar'):
                # Improved parsing: Assume format like modname-version.jar or modname.jar
                base_name = os.path.splitext(mod_file)[0]
                parts = re.split(r'[-_]', base_name)
                name = ' '.join(parts[:-1]).title() if len(parts) > 1 else base_name.title()
                version = parts[-1] if len(parts) > 1 and re.match(r'\d+\.\d+\.\d+', parts[-1]) else "Unknown"
                mods.append({
                    "filename": mod_file,
                    "name": name,
                    "version": version,
                    "source": "Local",
                    "enabled": mod_file in self.mod_profiles.get(self.selected_profile, [])
                })
        return mods

    def toggle_mod(self, mod_filename: str, enabled: bool) -> None:
        """Toggle mod in current profile."""
        profile_mods = self.mod_profiles.setdefault(self.selected_profile, [])
        if enabled and mod_filename not in profile_mods:
            profile_mods.append(mod_filename)
        elif not enabled and mod_filename in profile_mods:
            profile_mods.remove(mod_filename)
        self.save_mod_profiles()

    def add_mod_from_file(self) -> None:
        """Add local JAR mod with validation."""
        file_path = filedialog.askopenfilename(filetypes=[("JAR Files", "*.jar")])
        if file_path:
            mod_filename = os.path.basename(file_path)
            dest_path = os.path.join(MODS_DIR, mod_filename)
            try:
                shutil.copy2(file_path, dest_path)  # Preserve metadata
                profile_mods = self.mod_profiles.setdefault(self.selected_profile, [])
                if mod_filename not in profile_mods:
                    profile_mods.append(mod_filename)
                self.save_mod_profiles()
                messagebox.showinfo("Mod Manager", f"Added: {mod_filename}")
                self.open_mod_manager()  # Refresh
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add mod: {e}")

    def browse_modrinth(self) -> None:
        """Fetch and display Modrinth mods."""
        try:
            req = urllib.request.Request(f"{MODRINTH_API}/search?facets=[[\"project_type:mod\"]]&query=minecraft&limit=10",
                                         headers={'User-Agent': 'NoobClient/1.0'})
            with urllib.request.urlopen(req) as url:
                data = json.loads(url.read().decode())
                mods = data.get("hits", [])
                mod_window = tk.Toplevel(self)
                mod_window.title("Modrinth Mods")
                mod_window.geometry("600x400")
                mod_window.configure(bg=THEME['bg'])

                tk.Label(mod_window, text="MODRINTH MODS", font=("Arial", 18, "bold"),
                         bg=THEME['bg'], fg=THEME['text']).pack(pady=20)

                for mod in mods[:10]:  # Limit display
                    title = mod.get('title', 'Unknown')
                    version = mod.get('versions', ['Unknown'])[0]
                    tk.Button(mod_window, 
                              text=f"{title} v{version}",
                              bg=THEME['button'], fg=THEME['text'],
                              command=lambda s=mod.get('slug', ''): self.download_modrinth_mod(s)).pack(fill="x", padx=20, pady=5)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to fetch mods: {e}")

    def download_modrinth_mod(self, mod_slug: str) -> None:
        """Download latest mod version from Modrinth."""
        if not mod_slug:
            messagebox.showerror("Error", "Invalid mod slug")
            return
        try:
            req = urllib.request.Request(f"{MODRINTH_API}/project/{mod_slug}/version",
                                         headers={'User-Agent': 'NoobClient/1.0'})
            with urllib.request.urlopen(req) as url:
                versions = json.loads(url.read().decode())
                if not versions:
                    raise ValueError("No versions found")
                latest_version = versions[0]
                files = latest_version.get("files", [])
                if not files:
                    raise ValueError("No files found")
                file_info = files[0]
                file_url = file_info["url"]
                mod_filename = file_info.get("filename", f"{mod_slug}.jar")
                dest_path = os.path.join(MODS_DIR, mod_filename)
                self._download_with_retry(file_url, dest_path)
                profile_mods = self.mod_profiles.setdefault(self.selected_profile, [])
                if mod_filename not in profile_mods:
                    profile_mods.append(mod_filename)
                self.save_mod_profiles()
                messagebox.showinfo("Mod Manager", f"Installed: {mod_filename}")
                self.open_mod_manager()  # Refresh
        except Exception as e:
            messagebox.showerror("Error", f"Failed to download {mod_slug}: {e}")

    def _download_with_retry(self, url: str, path: str, max_retries: int = 3) -> bool:
        """Download file with exponential backoff retries."""
        for attempt in range(max_retries):
            try:
                urllib.request.urlretrieve(url, path)
                # Verify partial download
                if os.path.getsize(path) == 0:
                    raise ValueError("Empty download")
                return True
            except Exception as e:
                if attempt == max_retries - 1:
                    raise e
                time.sleep(2 ** attempt)  # Backoff
                print(f"Retry {attempt + 1}/{max_retries} for {url}: {e}")
        return False

    def save_mod_profiles(self) -> None:
        """Persist mod profiles to INI file."""
        os.makedirs(CONFIG_DIR, exist_ok=True)
        config = configparser.ConfigParser()
        for profile, mods in self.mod_profiles.items():
            config[profile] = {"mods": ",".join(mods)}
        try:
            with open(os.path.join(CONFIG_DIR, "mod_profiles.cfg"), "w") as f:
                config.write(f)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save profiles: {e}")

    def load_mod_profiles(self) -> None:
        """Load mod profiles from INI file."""
        config_path = os.path.join(CONFIG_DIR, "mod_profiles.cfg")
        if os.path.exists(config_path):
            config = configparser.ConfigParser()
            try:
                config.read(config_path)
                for profile in config.sections():
                    mods_str = config[profile].get("mods", "")
                    self.mod_profiles[profile] = [mod.strip() for mod in mods_str.split(",") if mod.strip()]
            except Exception as e:
                print(f"Warning: Failed to load profiles: {e}")

    def load_version_manifest(self) -> None:
        """Load vanilla, Forge, and Fabric versions asynchronously."""
        def _load() -> None:
            try:
                # Vanilla
                with urllib.request.urlopen(VERSION_MANIFEST_URL) as url:
                    manifest = json.loads(url.read().decode())
                    for v in manifest["versions"]:
                        self.versions[v["id"]] = {"url": v["url"], "type": v["type"], "loader": "vanilla"}
                        self.version_categories["All Versions"].append(v["id"])
                        if v["type"] == "release":
                            self.version_categories["Release"].append(v["id"])
                        elif v["type"] == "snapshot":
                            self.version_categories["Snapshot"].append(v["id"])

                # Forge (simplified: fetch recent via API proxy; full parser would scrape HTML)
                forge_req = urllib.request.Request("https://api.mcpbot.bspk.rs/v2/forge/promotions",
                                                   headers={'User-Agent': 'NoobClient/1.0'})
                with urllib.request.urlopen(forge_req) as url:
                    forge_data = json.loads(url.read().decode())
                    for entry in forge_data.get("promos", {}):
                        if entry.startswith("1."):
                            version_id = f"forge-{entry}"
                            self.versions[version_id] = {"mc_version": entry, "loader": "forge", "url": f"https://files.minecraftforge.net/net/minecraftforge/forge/index_{entry}.html"}
                            self.version_categories["All Versions"].append(version_id)
                            self.version_categories["Forge"].append(version_id)

                # Fabric
                mc_version = "1.20.1"  # Default; could prompt or detect latest
                fabric_req = urllib.request.Request(f"{FABRIC_LOADER_URL}{mc_version}/1.0.0/profile/json",
                                                    headers={'User-Agent': 'NoobClient/1.0'})
                with urllib.request.urlopen(fabric_req) as url:
                    fabric_data = json.loads(url.read().decode())
                    version_id = f"fabric-{mc_version}"
                    self.versions[version_id] = {"inheritsFrom": mc_version, "loader": "fabric", "json": fabric_data}
                    self.version_categories["All Versions"].append(version_id)
                    self.version_categories["Fabric"].append(version_id)

                self.after(0, self.update_version_list)
            except Exception as e:
                print(f"Error loading manifests: {e}")
                self.after(0, lambda: messagebox.showerror("Error", "Failed to load versions. Check internet."))

        threading.Thread(target=_load, daemon=True).start()

    def get_java_path(self, required_version: str = "17") -> Optional[str]:
        """Locate suitable Java executable with version check."""
        current_os = platform.system()
        # System Java
        try:
            result = subprocess.run(["java", "-version"], capture_output=True, text=True)
            match = re.search(r'version "(\d+)', result.stderr)
            if match and int(match.group(1)) >= int(required_version):
                return "java"
        except FileNotFoundError:
            pass
        # Local Java
        if os.path.exists(JAVA_DIR):
            java_dirs = [d for d in os.listdir(JAVA_DIR) if d.startswith("jdk-")]
            if java_dirs:
                java_dir = java_dirs[0]
                bin_dir = os.path.join(JAVA_DIR, java_dir, "bin")
                java_exe = "java.exe" if current_os == "Windows" else "java"
                java_bin = os.path.join(bin_dir, java_exe)
                if os.path.exists(java_bin):
                    try:
                        result = subprocess.run([java_bin, "-version"], capture_output=True, text=True)
                        match = re.search(r'version "(\d+)', result.stderr)
                        if match and int(match.group(1)) >= int(required_version):
                            if current_os != "Windows":
                                os.chmod(java_bin, 0o755)
                            return java_bin
                    except:
                        pass
        return None

    def install_java_if_needed(self) -> None:
        """Download and install OpenJDK 17 if missing."""
        if self.get_java_path():
            print("Java available.")
            return
        print("Installing OpenJDK 17...")
        current_os = platform.system()
        java_urls = {
            "Windows": "https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.12%2B7/OpenJDK17U-jdk_x64_windows_hotspot_17.0.12_7.msi",  # Updated link
            "Linux": "https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.12%2B7/OpenJDK17U-jdk_x64_linux_hotspot_17.0.12_7.tar.gz",
            "Darwin": "https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.12%2B7/OpenJDK17U-jdk_x64_mac_hotspot_17.0.12_7.tar.gz"
        }
        if current_os not in java_urls:
            messagebox.showerror("Error", "Unsupported OS")
            return

        archive_name = "openjdk.tar.gz"  # Simplified for tar.gz; handle MSI separately if needed
        archive_path = os.path.join(JAVA_DIR, archive_name)
        os.makedirs(JAVA_DIR, exist_ok=True)
        try:
            self._download_with_retry(java_urls[current_os], archive_path)
            with tarfile.open(archive_path, "r:gz") as tar_ref:
                tar_ref.extractall(JAVA_DIR)
            os.remove(archive_path)
            # Rename extracted dir
            extracted_dir = next((d for d in os.listdir(JAVA_DIR) if d.startswith("jdk-17")), None)
            if extracted_dir:
                shutil.move(os.path.join(JAVA_DIR, extracted_dir), os.path.join(JAVA_DIR, "jdk-17"))
            print("Java 17 installed.")
        except Exception as e:
            print(f"Java install failed: {e}")
            messagebox.showerror("Error", "Failed to install Java 17.")

    def select_skin(self) -> None:
        """Validate and apply custom skin."""
        file_path = filedialog.askopenfilename(filetypes=[("PNG Files", "*.png")])
        if file_path:
            try:
                with Image.open(file_path) as img:
                    if img.size not in [(64, 64), (64, 32)] or img.format != "PNG":
                        raise ValueError("Invalid skin: Must be 64x64/64x32 PNG")
                skins_dir = os.path.join(NOOB_CLIENT_DIR, "skins")
                os.makedirs(skins_dir, exist_ok=True)
                username = self.user_data["username"]
                shutil.copy(file_path, os.path.join(skins_dir, f"{username}.png"))
                messagebox.showinfo("Skin Manager", "Skin applied! (Mod required for custom offline skins.)")
            except Exception as e:
                messagebox.showerror("Error", f"Skin apply failed: {e}")

    def verify_file(self, file_path: str, expected_sha1: str) -> bool:
        """Compute SHA-1 and verify file integrity."""
        try:
            sha1_hash = hashlib.sha1()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha1_hash.update(chunk)
            return sha1_hash.hexdigest() == expected_sha1
        except Exception:
            return False

    def download_version_files(self, version_id: str, version_info: Dict[str, Any]) -> bool:
        """Download version JSON, JAR, libraries, and natives with modloader handling."""
        print(f"Downloading for {version_id}...")
        version_dir = os.path.join(VERSIONS_DIR, version_id)
        os.makedirs(version_dir, exist_ok=True)
        version_json_path = os.path.join(version_dir, f"{version_id}.json")

        loader = version_info.get("loader", "vanilla")
        if loader == "forge":
            # Forge: Download installer and run to generate JSON/JAR
            mc_version = version_info.get("mc_version", "1.20.1")
            installer_url = f"https://files.minecraftforge.net/maven/net/minecraftforge/forge/{mc_version}-{version_info.get('forge_version', '47.2.0')}/forge-{mc_version}-{version_info.get('forge_version', '47.2.0')}-installer.jar"
            installer_path = os.path.join(version_dir, "forge-installer.jar")
            self._download_with_retry(installer_url, installer_path)
            # Run installer in headless mode to generate files
            subprocess.run(["java", "-jar", installer_path, "--installClient", version_dir], check=True)
            # Load generated JSON
            with open(version_json_path, "r") as f:
                data = json.load(f)
        elif loader == "fabric":
            # Fabric: Use provided JSON
            data = version_info["json"]
            with open(version_json_path, "w") as f:
                json.dump(data, f, indent=2)
        else:
            # Vanilla
            try:
                with urllib.request.urlopen(version_info["url"]) as url:
                    data = json.loads(url.read().decode())
                with open(version_json_path, "w") as f:
                    json.dump(data, f, indent=2)
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", f"Failed to download {version_id} JSON: {e}"))
                return False

        # Download JAR and libraries (common logic)
        current_os = platform.system().lower()
        if current_os == "darwin":
            current_os = "osx"
        jar_path = os.path.join(version_dir, f"{version_id}.jar")
        if loader == "vanilla" or loader == "fabric":
            jar_url = data["downloads"]["client"]["url"] if "downloads" in data else f"https://s3.amazonaws.com/Minecraft.Download/versions/{version_id}/{version_id}.jar"
            expected_sha1 = data["downloads"]["client"]["sha1"] if "downloads" in data and "client" in data["downloads"] else None
            if not os.path.exists(jar_path) or (expected_sha1 and not self.verify_file(jar_path, expected_sha1)):
                self._download_with_retry(jar_url, jar_path)
                if expected_sha1 and not self.verify_file(jar_path, expected_sha1):
                    self.after(0, lambda: messagebox.showerror("Error", f"JAR checksum mismatch for {version_id}"))
                    return False

        libraries_dir = os.path.join(NOOB_CLIENT_DIR, "libraries")
        os.makedirs(libraries_dir, exist_ok=True)
        natives_dir = os.path.join(version_dir, "natives")
        os.makedirs(natives_dir, exist_ok=True)
        version_mods_dir = os.path.join(version_dir, "mods")  # Version-specific mods for modloaders
        os.makedirs(version_mods_dir, exist_ok=True)

        # Copy profile mods to version mods dir for modloaders
        if loader in ["forge", "fabric"]:
            for mod_file in self.mod_profiles.get(self.selected_profile, []):
                src = os.path.join(MODS_DIR, mod_file)
                if os.path.exists(src):
                    shutil.copy2(src, version_mods_dir)

        # Download libraries and natives
        libraries = data.get("libraries", [])
        with ThreadPoolExecutor(max_workers=5) as executor:  # Parallel downloads
            futures = []
            for lib in libraries:
                if not self.is_library_allowed(lib, current_os):
                    continue
                future = executor.submit(self._download_library, lib, libraries_dir, natives_dir, current_os)
                futures.append(future)
            for future in futures:
                if not future.result():
                    return False

        print("✅ Downloads complete!")
        return True

    def _download_library(self, lib: Dict[str, Any], libraries_dir: str, natives_dir: str, current_os: str) -> bool:
        """Download single library and natives."""
        name = lib.get("name", "")
        name_parts = name.split(":")
        if len(name_parts) < 3:
            return True
        group, artifact, version_lib = name_parts[0], name_parts[1], name_parts[2]
        group_path = group.replace(".", "/")

        # Artifact
        lib_url = lib["downloads"]["artifact"]["url"] if "downloads" in lib and "artifact" in lib["downloads"] else f"https://libraries.minecraft.net/{group_path}/{artifact}/{version_lib}/{artifact}-{version_lib}.jar"
        lib_path = os.path.join(libraries_dir, lib["downloads"]["artifact"]["path"] if "downloads" in lib else f"{group_path}/{artifact}/{version_lib}/{artifact}-{version_lib}.jar")
        expected_sha1 = lib["downloads"]["artifact"]["sha1"] if "downloads" in lib and "artifact" in lib["downloads"] else None
        os.makedirs(os.path.dirname(lib_path), exist_ok=True)
        if not os.path.exists(lib_path) or (expected_sha1 and not self.verify_file(lib_path, expected_sha1)):
            if not self._download_with_retry(lib_url, lib_path):
                return False
            if expected_sha1 and not self.verify_file(lib_path, expected_sha1):
                print(f"Library checksum mismatch: {name}")
                return False

        # Natives
        if "natives" in lib and current_os in lib["natives"]:
            classifier = lib["natives"][current_os]
            native_url = lib["downloads"]["classifiers"][classifier]["url"] if "downloads" in lib and "classifiers" in lib["downloads"] else f"https://libraries.minecraft.net/{group_path}/{artifact}/{version_lib}/{artifact}-{version_lib}-{classifier}.jar"
            native_filename = f"{artifact}-{version_lib}-{classifier}.jar"
            native_path = os.path.join(natives_dir, native_filename)
            expected_sha1_native = lib["downloads"]["classifiers"][classifier]["sha1"] if "downloads" in lib and "classifiers" in lib["downloads"] else None
            if not os.path.exists(native_path) or (expected_sha1_native and not self.verify_file(native_path, expected_sha1_native)):
                if not self._download_with_retry(native_url, native_path):
                    return False
                if expected_sha1_native and not self.verify_file(native_path, expected_sha1_native):
                    print(f"Native checksum mismatch: {name}")
                    return False
            try:
                with zipfile.ZipFile(native_path, "r") as zip_ref:
                    zip_ref.extractall(natives_dir)
                os.remove(native_path)
            except Exception as e:
                print(f"Native extract failed: {e}")
                return False
        return True

    def download_assets(self, version_id: str) -> None:
        """Download assets index and objects in parallel."""
        version_dir = os.path.join(VERSIONS_DIR, version_id)
        json_path = os.path.join(version_dir, f"{version_id}.json")
        try:
            with open(json_path, "r") as f:
                data = json.load(f)
            asset_index = data.get("assetIndex", {})
            if not asset_index:
                return
            index_id = asset_index["id"]
            index_url = asset_index["url"]
            index_sha1 = asset_index["sha1"]
            index_path = os.path.join(ASSETS_DIR, "indexes", f"{index_id}.json")
            os.makedirs(os.path.dirname(index_path), exist_ok=True)
            if not os.path.exists(index_path) or not self.verify_file(index_path, index_sha1):
                self._download_with_retry(index_url, index_path)
                if not self.verify_file(index_path, index_sha1):
                    raise ValueError(f"Asset index mismatch: {index_id}")
            with open(index_path, "r") as f:
                index_data = json.load(f)
            objects_dir = os.path.join(ASSETS_DIR, "objects")
            os.makedirs(objects_dir, exist_ok=True)
            objects = index_data.get("objects", {})
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = []
                for obj_hash, obj_info in objects.items():
                    obj_path = os.path.join(objects_dir, obj_hash[:2], obj_hash)
                    os.makedirs(os.path.dirname(obj_path), exist_ok=True)
                    obj_url = f"https://resources.download.minecraft.net/{obj_hash[:2]}/{obj_hash}"
                    obj_sha1 = obj_info["hash"]
                    if not os.path.exists(obj_path) or not self.verify_file(obj_path, obj_sha1):
                        future = executor.submit(self._download_with_retry, obj_url, obj_path)
                        futures.append((future, obj_path, obj_sha1))
                for future, obj_path, obj_sha1 in futures:
                    if not future.result():
                        if not self.verify_file(obj_path, obj_sha1):
                            print(f"Asset {os.path.basename(obj_path)} mismatch, retrying...")
                            self._download_with_retry(f"https://resources.download.minecraft.net/{os.path.basename(os.path.dirname(obj_path))}/{os.path.basename(obj_path)}", obj_path)
        except Exception as e:
            print(f"Assets download failed: {e}")

    def modify_options_txt(self, target_fps: int = 60) -> None:
        """Apply performance tweaks to options.txt."""
        options_path = os.path.join(NOOB_CLIENT_DIR, "options.txt")
        options = {
            'maxFps': str(target_fps),
            'enableVsync': 'false',
            'graphicsMode': 'fast',
            'renderDistance': '12',
            'smoothLighting': 'off',
            'fov': '90'
        }
        # Merge existing if present
        if os.path.exists(options_path):
            try:
                with open(options_path, "r") as f:
                    for line in f:
                        if ':' in line:
                            key, value = line.strip().split(":", 1)
                            options[key.strip()] = value.strip()
            except Exception as e:
                print(f"Options read warning: {e}")
        try:
            with open(options_path, "w") as f:
                for key, value in options.items():
                    f.write(f"{key}:{value}\n")
            print(f"Options updated: FPS={target_fps}")
        except Exception as e:
            print(f"Options write failed: {e}")

    def matches_conditions(self, rule: Dict[str, Any], os_name: str) -> bool:
        """Evaluate rule conditions for inclusion."""
        if "os" in rule and isinstance(rule["os"], dict) and rule["os"].get("name") != os_name:
            return False
        if "features" in rule:
            return False  # Launcher context assumes no features
        return True

    def should_include(self, rules: List[Dict[str, Any]], os_name: str) -> bool:
        """Determine if item should be included based on rules."""
        if not rules:
            return True
        for rule in rules:
            if self.matches_conditions(rule, os_name):
                return rule["action"] == "allow"
        return False

    def is_library_allowed(self, lib: Dict[str, Any], current_os: str) -> bool:
        """Check library rules for OS."""
        rules = lib.get("rules", [])
        return self.should_include(rules, current_os)

    def generate_offline_uuid(self, username: str) -> str:
        """Generate SHA-1 based offline UUID for compatibility."""
        hash_input = f"OfflinePlayer:{username}"
        hash_value = hashlib.sha1(hash_input.encode('utf-8')).hexdigest()
        return f"{hash_value[:8]}-{hash_value[8:12]}-{hash_value[12:16]}-{hash_value[16:20]}-{hash_value[20:]}"

    def build_launch_command(self, version: str, username: str, ram: int) -> List[str]:
        """Build JVM and game args with modloader-specific adjustments."""
        version_dir = os.path.join(VERSIONS_DIR, version)
        json_path = os.path.join(version_dir, f"{version}.json")

        try:
            with open(json_path, "r") as f:
                version_data = json.load(f)
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Error", f"Cannot read {version} JSON: {e}"))
            return []

        current_os = platform.system().lower()
        if current_os == "darwin":
            current_os = "osx"
        loader = self.versions[version].get("loader", "vanilla")
        main_class = version_data.get("mainClass", "net.minecraft.client.main.Main")
        if loader == "forge":
            main_class = "net.minecraftforge.fml.loading.FMLClientLaunchHandler"
        elif loader == "fabric":
            main_class = "net.fabricmc.loader.impl.launch.knot.KnotClient"

        libraries_dir = os.path.join(NOOB_CLIENT_DIR, "libraries")
        natives_dir = os.path.join(version_dir, "natives")
        jar_path = os.path.join(version_dir, f"{version}.jar")
        if not os.path.exists(jar_path):
            self.after(0, lambda: messagebox.showerror("Error", f"JAR missing for {version}"))
            return []

        # Classpath: JAR + libraries; mods handled by loader
        classpath = [jar_path]
        for lib in version_data.get("libraries", []):
            if self.is_library_allowed(lib, current_os):
                lib_name = lib.get("name", "")
                name_parts = lib_name.split(":")
                if len(name_parts) >= 3:
                    group, artifact, version_lib = name_parts[0], name_parts[1], name_parts[2]
                    group_path = group.replace(".", "/")
                    lib_filename = f"{artifact}-{version_lib}.jar"
                    lib_path = os.path.join(libraries_dir, group_path, artifact, version_lib, lib_filename)
                    if os.path.exists(lib_path):
                        classpath.append(lib_path)
        # Add loader JAR if applicable
        if loader == "forge":
            forge_jar = os.path.join(version_dir, "minecraft.jar")  # Generated by installer
            if os.path.exists(forge_jar):
                classpath.append(forge_jar)
        elif loader == "fabric":
            fabric_loader = os.path.join(libraries_dir, "net/fabricmc", "fabric-loader", "0.15.11", "fabric-loader-0.15.11.jar")  # Example; parse from JSON
            if os.path.exists(fabric_loader):
                classpath.append(fabric_loader)

        classpath_str = ";".join(classpath) if platform.system() == "Windows" else ":".join(classpath)
        java_path = self.get_java_path()
        if not java_path:
            self.after(0, lambda: messagebox.showerror("Error", "Java not found"))
            return []

        command = [
            java_path,
            f"-Xmx{ram}G",
            "-XX:+UseG1GC",
            "-XX:MaxGCPauseMillis=100",
            f"-Djava.library.path={natives_dir}",
            "-cp",
            classpath_str
        ]

        # JVM args with rules
        jvm_args = []
        if "arguments" in version_data and "jvm" in version_data["arguments"]:
            for arg in version_data["arguments"]["jvm"]:
                if isinstance(arg, str):
                    jvm_args.append(arg)
                elif isinstance(arg, dict) and "rules" in arg and "value" in arg:
                    if self.should_include(arg["rules"], current_os):
                        jvm_args.extend(arg["value"] if isinstance(arg["value"], list) else [arg["value"]])
        if loader == "forge":
            jvm_args.extend(["-Dforge.logging.markers=SCAN,REGISTRIES,REGISTRYDUMP"])
        elif loader == "fabric":
            jvm_args.append("-Dfabric.launcher=true")

        command.extend(jvm_args)
        command.append(main_class)

        # Game args
        game_args = [
            "--username", username,
            "--uuid", self.user_data["uuid"],
            "--accessToken", self.user_data["access_token"],
            "--version", version,
            "--gameDir", NOOB_CLIENT_DIR,
            "--assetsDir", ASSETS_DIR,
            "--assetIndex", version_data.get("assetIndex", {}).get("id", version),
            "--modDir", os.path.join(version_dir, "mods") if loader in ["forge", "fabric"] else None  # Modloader specific
        ]
        if loader in ["forge", "fabric"]:
            game_args.append("--fml.forgeVersion")  # Forge example; adjust per loader

        if "arguments" in version_data and "game" in version_data["arguments"]:
            for arg in version_data["arguments"]["game"]:
                if isinstance(arg, str):
                    game_args.append(arg)
                elif isinstance(arg, dict) and "rules" in arg and "value" in arg:
                    if self.should_include(arg["rules"], current_os):
                        game_args.extend(arg["value"] if isinstance(arg["value"], list) else [arg["value"]])

        command.extend([a for a in game_args if a is not None])
        return command

if __name__ == "__main__":
    try:
        app = NoobClientLauncher()
        app.mainloop()
    except KeyboardInterrupt:
        print("Launcher terminated.")
        sys.exit(0)
