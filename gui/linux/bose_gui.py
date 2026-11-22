#!/usr/bin/env python3
"""Native desktop interface for the bosectl command line utility."""

from __future__ import annotations

import os
import queue
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk


APP_DIR = Path(__file__).resolve().parent
RECONNECT_PAUSE = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / "bose-control-reconnect.pause"
DEFAULT_CLI = Path(
    os.environ.get("BOSECTL_PATH")
    or shutil.which("bosectl")
    or APP_DIR.parent.parent / "bosectl"
).expanduser().resolve()
BG, PANEL, PANEL_2 = "#111827", "#1f2937", "#263449"
TEXT, MUTED, BLUE, GREEN, RED = "#f8fafc", "#9ca3af", "#38bdf8", "#34d399", "#fb7185"


def audio_sinks() -> set[str]:
    output = subprocess.check_output(
        ["pactl", "list", "short", "sinks"], text=True, timeout=3
    )
    return {fields[1] for line in output.splitlines() if len(fields := line.split()) > 1}


def paired_bose() -> tuple[str, str]:
    paired = subprocess.check_output(
        ["bluetoothctl", "devices", "Paired"], text=True, timeout=5
    )
    bose_devices = re.findall(
        r"^Device ([0-9A-F:]{17}) (Bose\b[^\n]*)$", paired, re.MULTILINE | re.IGNORECASE
    )
    if not bose_devices:
        raise RuntimeError("Empareja los auriculares Bose en los ajustes de Bluetooth.")
    if len(bose_devices) > 1:
        raise RuntimeError("Hay varios dispositivos Bose emparejados. Selecciona la salida en los ajustes de sonido.")

    return bose_devices[0]


def bose_sink(sinks: set[str], address: str) -> str | None:
    return next((sink for sink in sinks if sink.upper() == f"BLUEZ_OUTPUT.{address.upper()}"), None)


def restore_bose_audio(device: tuple[str, str] | None = None) -> str:
    address, name = device or paired_bose()
    sink = bose_sink(audio_sinks(), address)
    if sink:
        subprocess.run(["pactl", "set-default-sink", sink], check=True, timeout=3)
        return f"Salida de sonido seleccionada: {name}"

    connect = subprocess.run(
        ["bluetoothctl", "connect", address], capture_output=True, text=True, timeout=15
    )
    deadline = time.monotonic() + 5
    while True:
        if sink := bose_sink(audio_sinks(), address):
            subprocess.run(["pactl", "set-default-sink", sink], check=True, timeout=3)
            return f"Salida de sonido seleccionada: {name}"
        if time.monotonic() >= deadline:
            if connect.returncode:
                raise RuntimeError("No se pudo conectar con los Bose. Comprueba que estén encendidos y al alcance.")
            raise RuntimeError("Los Bose están conectados, pero el sistema no ofrece una salida de audio.")
        time.sleep(0.25)


class BoseGUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Bose Control")
        self.geometry("1040x720")
        self.minsize(880, 620)
        self.configure(bg=BG)
        self.cli = DEFAULT_CLI
        self.jobs: queue.Queue[tuple] = queue.Queue()
        self.busy = 0
        self._style()
        self._header()
        self._content()
        self.after(100, self._poll_jobs)
        self.after(350, self.refresh)

    def _style(self) -> None:
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure(".", background=BG, foreground=TEXT, font=("Ubuntu", 11))
        s.configure("TFrame", background=BG)
        s.configure("Panel.TFrame", background=PANEL)
        s.configure("TLabel", background=BG, foreground=TEXT)
        s.configure("Panel.TLabel", background=PANEL, foreground=TEXT)
        s.configure("Muted.TLabel", background=BG, foreground=MUTED)
        s.configure("PanelMuted.TLabel", background=PANEL, foreground=MUTED)
        s.configure("Title.TLabel", font=("Ubuntu", 24, "bold"), foreground=TEXT)
        s.configure("Value.TLabel", background=PANEL, font=("Ubuntu", 22, "bold"), foreground=BLUE)
        s.configure("TButton", padding=(13, 8), background=PANEL_2, foreground=TEXT, borderwidth=0)
        s.map("TButton", background=[("active", "#334155"), ("disabled", PANEL)])
        s.configure("Accent.TButton", background="#0369a1", foreground="white")
        s.map("Accent.TButton", background=[("active", "#0284c7")])
        s.configure("Selected.TButton", background="#0ea5e9", foreground="white",
                    font=("Ubuntu", 11, "bold"), relief="solid", borderwidth=2)
        s.map("Selected.TButton",
              background=[("active", "#38bdf8"), ("pressed", "#0284c7")],
              foreground=[("active", "white")])
        s.configure("Danger.TButton", background="#9f1239", foreground="white")
        s.configure("TNotebook", background=BG, borderwidth=0)
        s.configure("TNotebook.Tab", padding=(18, 10), background=PANEL, foreground=MUTED)
        s.map("TNotebook.Tab", background=[("selected", "#0369a1")], foreground=[("selected", "white")])
        s.configure("TEntry", fieldbackground="#0f172a", foreground=TEXT, insertcolor=TEXT, padding=8)
        s.configure("TCombobox", fieldbackground="#0f172a", foreground=TEXT, padding=6)
        s.configure("Horizontal.TScale", background=PANEL, troughcolor="#0f172a")
        s.configure("TCheckbutton", background=PANEL, foreground=TEXT)
        s.map("TCheckbutton", background=[("active", PANEL)])

    def _header(self) -> None:
        bar = ttk.Frame(self, padding=(24, 18))
        bar.pack(fill="x")
        title = ttk.Frame(bar)
        title.pack(side="left")
        ttk.Label(title, text="BOSE CONTROL", style="Title.TLabel").pack(anchor="w")
        ttk.Label(title, text="Control local de tus auriculares", style="Muted.TLabel").pack(anchor="w")
        self.spinner = ttk.Label(bar, text="● Desconectado", foreground=RED)
        self.spinner.pack(side="right", padx=(15, 0))
        self.refresh_btn = ttk.Button(bar, text="↻ Actualizar", style="Accent.TButton", command=self.refresh)
        self.refresh_btn.pack(side="right")
        self.restore_audio_btn = ttk.Button(bar, text="Restaurar audio", command=self.restore_audio)
        self.restore_audio_btn.pack(side="right", padx=(0, 8))

    def _content(self) -> None:
        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True, padx=22, pady=(0, 22))
        self.dashboard = ttk.Frame(self.tabs, padding=18)
        self.sound = ttk.Frame(self.tabs, padding=18)
        self.settings = ttk.Frame(self.tabs, padding=18)
        self.profiles = ttk.Frame(self.tabs, padding=18)
        self.tools = ttk.Frame(self.tabs, padding=18)
        for frame, label in ((self.dashboard, "Inicio"), (self.sound, "Sonido"),
                             (self.settings, "Ajustes"), (self.profiles, "Perfiles"),
                             (self.tools, "Avanzado")):
            self.tabs.add(frame, text=label)
        self._dashboard_tab()
        self._sound_tab()
        self._settings_tab()
        self._profiles_tab()
        self._tools_tab()

    def _card(self, parent, title: str, value: str = "—") -> ttk.Label:
        box = ttk.Frame(parent, style="Panel.TFrame", padding=18)
        box.pack(side="left", fill="both", expand=True, padx=6)
        ttk.Label(box, text=title.upper(), style="PanelMuted.TLabel").pack(anchor="w")
        label = ttk.Label(box, text=value, style="Value.TLabel")
        label.pack(anchor="w", pady=(8, 0))
        return label

    def _dashboard_tab(self) -> None:
        cards = ttk.Frame(self.dashboard)
        cards.pack(fill="x", pady=(0, 16))
        self.model_value = self._card(cards, "Dispositivo")
        self.battery_value = self._card(cards, "Batería")
        self.mode_value = self._card(cards, "Modo")

        modes = ttk.Frame(self.dashboard, style="Panel.TFrame", padding=18)
        modes.pack(fill="x", pady=6)
        ttk.Label(modes, text="MODOS RÁPIDOS", style="PanelMuted.TLabel").pack(anchor="w", pady=(0, 12))
        row = ttk.Frame(modes, style="Panel.TFrame")
        row.pack(fill="x")
        self.mode_buttons = {}
        for command, text in (("quiet", "Silencio"), ("aware", "Atento"),
                              ("immersion", "Inmersión"), ("cinema", "Cine")):
            button = ttk.Button(row, text=text, command=lambda c=command: self.select_mode(c))
            button.pack(side="left", fill="x", expand=True, padx=4)
            self.mode_buttons[command] = button

        status_box = ttk.Frame(self.dashboard, style="Panel.TFrame", padding=18)
        status_box.pack(fill="both", expand=True, pady=10)
        ttk.Label(status_box, text="ESTADO COMPLETO", style="PanelMuted.TLabel").pack(anchor="w")
        self.status_text = tk.Text(status_box, height=13, bg=PANEL, fg=TEXT, relief="flat",
                                   font=("Ubuntu Mono", 11), insertbackground=TEXT, wrap="word")
        self.status_text.pack(fill="both", expand=True, pady=(8, 0))

    def _section(self, parent, title: str) -> ttk.Frame:
        box = ttk.Frame(parent, style="Panel.TFrame", padding=18)
        box.pack(fill="x", pady=7)
        ttk.Label(box, text=title.upper(), style="PanelMuted.TLabel").pack(anchor="w", pady=(0, 12))
        # Content gets its own container, allowing each section to use either
        # pack or grid without mixing geometry managers with the title above.
        content = ttk.Frame(box, style="Panel.TFrame")
        content.pack(fill="both", expand=True)
        return content

    def _sound_tab(self) -> None:
        mode = self._section(self.sound, "Cancelación de ruido (CNC: 0 = máxima)")
        self.cnc_var = tk.IntVar(value=0)
        line = ttk.Frame(mode, style="Panel.TFrame")
        line.pack(fill="x")
        self.cnc_label = ttk.Label(line, text="0", style="Value.TLabel", width=3)
        self.cnc_label.pack(side="right")
        scale = ttk.Scale(line, from_=0, to=10, variable=self.cnc_var,
                          command=lambda v: self.cnc_label.config(text=str(round(float(v)))))
        scale.pack(side="left", fill="x", expand=True, padx=(0, 12))
        ttk.Button(mode, text="Aplicar CNC", style="Accent.TButton",
                   command=lambda: self.run("cnc", str(self.cnc_var.get()), refresh=True)).pack(anchor="e", pady=(10, 0))

        eq = self._section(self.sound, "Ecualizador")
        eqrow = ttk.Frame(eq, style="Panel.TFrame")
        eqrow.pack(fill="x")
        self.eq_vars = []
        for name in ("Graves", "Medios", "Agudos"):
            col = ttk.Frame(eqrow, style="Panel.TFrame")
            col.pack(side="left", fill="x", expand=True, padx=8)
            var = tk.IntVar(value=0)
            self.eq_vars.append(var)
            value = ttk.Label(col, text="0", style="Panel.TLabel")
            ttk.Label(col, text=name, style="PanelMuted.TLabel").pack()
            ttk.Scale(col, from_=-10, to=10, variable=var,
                      command=lambda v, w=value: w.config(text=f"{round(float(v)):+d}")).pack(fill="x")
            value.pack()
        actions = ttk.Frame(eq, style="Panel.TFrame")
        actions.pack(fill="x", pady=(10, 0))
        ttk.Button(actions, text="Plano", command=lambda: self.run("eq", "flat", refresh=True)).pack(side="right")
        ttk.Button(actions, text="Aplicar EQ", style="Accent.TButton", command=self.apply_eq).pack(side="right", padx=8)

        spatial = self._section(self.sound, "Audio espacial")
        self.spatial_buttons = {}
        for command, label in (("off", "Desactivado"), ("room", "Fijo"), ("head", "Seguimiento de cabeza")):
            button = ttk.Button(spatial, text=label, command=lambda c=command: self.select_spatial(c))
            button.pack(side="left", fill="x", expand=True, padx=4)
            self.spatial_buttons[command] = button

    def _settings_tab(self) -> None:
        toggles = self._section(self.settings, "Interruptores")
        items = (("ANC", "anc"), ("Bloqueo de viento", "wind"), ("Multipunto", "multipoint"),
                 ("Pausa automática", "autopause"), ("Responder llamadas", "autoanswer"),
                 ("Avisos de voz", "prompts"))
        self.toggle_buttons = {}
        for i, (label, cmd) in enumerate(items):
            box = ttk.Frame(toggles, style="Panel.TFrame")
            box.grid(row=i // 2, column=i % 2, sticky="ew", padx=8, pady=5)
            toggles.columnconfigure(i % 2, weight=1)
            ttk.Label(box, text=label, style="Panel.TLabel").pack(side="left")
            off_button = ttk.Button(
                box, text="OFF", command=lambda c=cmd: self.select_toggle(c, "off"))
            off_button.pack(side="right")
            on_button = ttk.Button(
                box, text="ON", command=lambda c=cmd: self.select_toggle(c, "on"))
            on_button.pack(side="right", padx=5)
            self.toggle_buttons[cmd] = {"on": on_button, "off": off_button}

        details = self._section(self.settings, "Nombre y sidetone")
        self.name_var = tk.StringVar()
        ttk.Entry(details, textvariable=self.name_var).pack(side="left", fill="x", expand=True)
        ttk.Button(details, text="Cambiar nombre", command=lambda: self.run("name", self.name_var.get(), refresh=True)).pack(side="left", padx=8)
        self.sidetone_var = tk.StringVar(value="medium")
        ttk.Combobox(details, textvariable=self.sidetone_var, values=("off", "low", "medium", "high"),
                     state="readonly", width=12).pack(side="left")
        ttk.Button(details, text="Sidetone", command=lambda: self.run("sidetone", self.sidetone_var.get(), refresh=True)).pack(side="left", padx=8)

        control = self._section(self.settings, "Dispositivo")
        ttk.Button(control, text="Modo emparejamiento", command=lambda: self.run("pair")).pack(side="left", padx=4)
        ttk.Button(control, text="Apagar auriculares", style="Danger.TButton", command=self.power_off).pack(side="left", padx=4)

    def _profiles_tab(self) -> None:
        box = self._section(self.profiles, "Perfiles guardados")
        self.profiles_text = tk.Text(box, height=12, bg="#0f172a", fg=TEXT, relief="flat", font=("Ubuntu Mono", 11))
        self.profiles_text.pack(fill="x")
        ttk.Button(box, text="Actualizar lista", command=lambda: self.run("profiles", callback=self._show_profiles)).pack(anchor="e", pady=(8, 0))

        edit = self._section(self.profiles, "Crear, actualizar, activar o borrar")
        self.profile_name = tk.StringVar()
        ttk.Entry(edit, textvariable=self.profile_name).grid(row=0, column=0, sticky="ew", padx=4)
        self.profile_cnc = tk.IntVar(value=0)
        ttk.Spinbox(edit, from_=0, to=10, textvariable=self.profile_cnc, width=5).grid(row=0, column=1, padx=4)
        self.profile_spatial = tk.StringVar(value="off")
        ttk.Combobox(edit, textvariable=self.profile_spatial, values=("off", "room", "head"), state="readonly", width=9).grid(row=0, column=2, padx=4)
        edit.columnconfigure(0, weight=1)
        ttk.Button(edit, text="Guardar", style="Accent.TButton", command=self.save_profile).grid(row=0, column=3, padx=4)
        ttk.Button(edit, text="Activar", command=lambda: self.run("switch", self.profile_name.get(), refresh=True)).grid(row=0, column=4, padx=4)
        ttk.Button(edit, text="Borrar", style="Danger.TButton", command=self.delete_profile).grid(row=0, column=5, padx=4)
        ttk.Label(edit, text="Nombre                              CNC     Espacial", style="PanelMuted.TLabel").grid(row=1, column=0, columnspan=3, sticky="w", padx=4, pady=(5, 0))

    def _tools_tab(self) -> None:
        route = self._section(self.tools, "Fuente y ruta Bluetooth")
        self.source_label = ttk.Label(route, text="Fuente: —", style="Panel.TLabel")
        self.source_label.pack(side="left")
        ttk.Button(route, text="Consultar", command=lambda: self.run("source", callback=self._show_source)).pack(side="left", padx=8)
        self.mac_var = tk.StringVar()
        ttk.Entry(route, textvariable=self.mac_var, width=22).pack(side="left", padx=(20, 5))
        ttk.Button(route, text="Cambiar ruta", command=lambda: self.run("route", self.mac_var.get())).pack(side="left")

        buttons = self._section(self.tools, "Botón programable")
        self.button_action = tk.StringVar(value="ANC")
        ttk.Combobox(buttons, textvariable=self.button_action,
                     values=("ANC", "VPA", "Disabled"), width=16).pack(side="left")
        ttk.Button(buttons, text="Asignar", command=lambda: self.run("buttons", "set", self.button_action.get())).pack(side="left", padx=8)
        ttk.Button(buttons, text="Consultar", command=lambda: self.run("buttons")).pack(side="left")

        advanced = self._section(self.tools, "Comandos avanzados")
        self.raw_var = tk.StringVar()
        ttk.Entry(advanced, textvariable=self.raw_var).pack(side="left", fill="x", expand=True)
        ttk.Button(advanced, text="Enviar RAW", command=lambda: self.run("raw", self.raw_var.get())).pack(side="left", padx=8)
        ttk.Button(advanced, text="Dump", command=lambda: self.run("dump")).pack(side="left")

        output = self._section(self.tools, "Registro de comandos")
        self.log = tk.Text(output, height=12, bg="#020617", fg="#cbd5e1", relief="flat", font=("Ubuntu Mono", 10))
        self.log.pack(fill="both", expand=True)

    def apply_eq(self) -> None:
        self.run("eq", *(str(v.get()) for v in self.eq_vars), refresh=True)

    @staticmethod
    def _mark_choice(buttons: dict[str, ttk.Button], selected: str) -> None:
        """Highlight exactly one button in a group."""
        for value, button in buttons.items():
            button.configure(style="Selected.TButton" if value == selected else "TButton")

    def select_mode(self, mode: str) -> None:
        self.run(
            mode,
            callback=lambda _output: self._mark_choice(self.mode_buttons, mode),
            refresh=True,
        )

    def select_spatial(self, spatial: str) -> None:
        self.run(
            "spatial",
            spatial,
            callback=lambda _output: self._mark_choice(self.spatial_buttons, spatial),
            refresh=True,
        )

    def select_toggle(self, command: str, value: str) -> None:
        self.run(
            command,
            value,
            callback=lambda _output: self._mark_choice(self.toggle_buttons[command], value),
            refresh=True,
        )

    def save_profile(self) -> None:
        name = self.profile_name.get().strip()
        if not name:
            messagebox.showwarning("Falta el nombre", "Escribe un nombre para el perfil.")
            return
        self.run("profile", "set", name, f"cnc={self.profile_cnc.get()}",
                 f"spatial={self.profile_spatial.get()}", callback=lambda _: self.load_profiles())

    def delete_profile(self) -> None:
        name = self.profile_name.get().strip()
        if name and messagebox.askyesno("Borrar perfil", f"¿Borrar el perfil «{name}»?"):
            self.run("profile", "rm", name, callback=lambda _: self.load_profiles())

    def power_off(self) -> None:
        if messagebox.askyesno("Apagar", "¿Apagar los auriculares?"):
            RECONNECT_PAUSE.touch()
            self.run("off")

    def refresh(self) -> None:
        # bosectl opens an RFCOMM session per command. Keep refresh operations
        # sequential so two simultaneous connections do not fight each other.
        self.run("status", callback=self._status_then_profiles)

    def _status_then_profiles(self, output: str) -> None:
        self._show_status(output)
        self.load_profiles()

    def load_profiles(self) -> None:
        self.run("profiles", callback=self._show_profiles, silent=True)

    def run(self, *args: str, callback=None, refresh: bool = False, silent: bool = False) -> None:
        args = tuple(str(a).strip() for a in args)
        if not self.cli.is_file():
            messagebox.showerror("bosectl no encontrado", f"No existe el ejecutable:\n{self.cli}")
            return
        if any(not a for a in args):
            messagebox.showwarning("Dato incompleto", "Completa todos los campos necesarios.")
            return
        def command():
            result = subprocess.run([str(self.cli), *args], cwd=self.cli.parent,
                                    capture_output=True, text=True, timeout=25)
            return result.returncode, (result.stdout + result.stderr).strip()

        self._start_job(f"bosectl {shlex.join(args)}", command, callback, refresh, silent)

    def restore_audio(self) -> None:
        def command():
            output = restore_bose_audio()
            RECONNECT_PAUSE.unlink(missing_ok=True)
            return 0, output

        self._start_job("Restaurar audio", command, None, False, False)

    def _start_job(self, label, command, callback, refresh, silent) -> None:
        self.busy += 1
        self.restore_audio_btn.state(["disabled"])
        self.refresh_btn.state(["disabled"])
        self.spinner.config(text="● Trabajando…", foreground=BLUE)

        def worker() -> None:
            try:
                code, output = command()
                self.jobs.put((code, label, output, callback, refresh, silent))
            except Exception as exc:
                self.jobs.put((1, label, str(exc), callback, refresh, silent))
        threading.Thread(target=worker, daemon=True).start()

    def _poll_jobs(self) -> None:
        try:
            while True:
                code, label, output, callback, refresh, silent = self.jobs.get_nowait()
                self.busy = max(0, self.busy - 1)
                if hasattr(self, "log") and not silent:
                    self.log.insert("end", f"$ {label}\n{output or '(sin salida)'}\n\n")
                    self.log.see("end")
                if code == 0:
                    self.spinner.config(text="● Conectado", foreground=GREEN)
                    if callback:
                        callback(output)
                    if refresh:
                        self.after(250, self.refresh)
                else:
                    if not silent:
                        self.spinner.config(text="● Sin conexión", foreground=RED)
                    if not silent:
                        messagebox.showerror("Bose Control", output or "El comando no pudo ejecutarse.")
                if self.busy == 0:
                    self.refresh_btn.state(["!disabled"])
                    self.restore_audio_btn.state(["!disabled"])
        except queue.Empty:
            pass
        self.after(100, self._poll_jobs)

    def _show_status(self, output: str) -> None:
        self.status_text.delete("1.0", "end")
        self.status_text.insert("1.0", output)
        fields = dict(re.findall(r"^\s*([A-Za-z]+)\s+(.+?)\s*$", output, re.MULTILINE))
        self.model_value.config(text=fields.get("Model", "Bose"))
        self.battery_value.config(text=fields.get("Battery", "—").split()[0])
        self.mode_value.config(text=fields.get("Mode", "—"))

        # Mode names are supplied by the headphones and may vary in case.
        # Match both the preset command and its visible English description.
        mode_text = fields.get("Mode", "").strip().lower()
        mode_aliases = {
            "quiet": "quiet",
            "silence": "quiet",
            "silencio": "quiet",
            "aware": "aware",
            "atento": "aware",
            "immersion": "immersion",
            "inmersión": "immersion",
            "cinema": "cinema",
            "cine": "cinema",
        }
        active_mode = mode_aliases.get(mode_text, "")
        if active_mode:
            self._mark_choice(self.mode_buttons, active_mode)
            # Preset definitions establish the spatial state as well.
            preset_spatial = {
                "quiet": "off",
                "aware": "off",
                "immersion": "head",
                "cinema": "room",
            }
            self._mark_choice(self.spatial_buttons, preset_spatial[active_mode])
        else:
            # A custom profile may be active, so no preset button should look
            # selected in that case.
            self._mark_choice(self.mode_buttons, "")

        status_toggles = {
            "multipoint": fields.get("Multipoint"),
            "autopause": fields.get("AutoPause"),
            "prompts": fields.get("Prompts"),
        }
        for command, value in status_toggles.items():
            if value:
                state = "on" if value.strip().lower().startswith("on") else "off"
                self._mark_choice(self.toggle_buttons[command], state)

        if "Name" in fields:
            self.name_var.set(fields["Name"])
        cnc = re.search(r"CNC\s+.*?(\d+)/10", output)
        if cnc:
            self.cnc_var.set(int(cnc.group(1)))
            self.cnc_label.config(text=cnc.group(1))
        eq = re.search(r"EQ\s+([+-]?\d+)/([+-]?\d+)/([+-]?\d+)", output)
        if eq:
            for var, value in zip(self.eq_vars, eq.groups()):
                var.set(int(value))

    def _show_profiles(self, output: str) -> None:
        self.profiles_text.delete("1.0", "end")
        self.profiles_text.insert("1.0", output or "No se encontraron perfiles.")

    def _show_source(self, output: str) -> None:
        self.source_label.config(text=f"Fuente: {output}")


def watch_bose_audio() -> None:
    paused_disconnect = False
    reconnect_pending = False
    next_attempt = 0.0
    last_error = None
    while True:
        try:
            device = paired_bose()
            sink = bose_sink(audio_sinks(), device[0])
            if RECONNECT_PAUSE.exists():
                reconnect_pending = False
                paused_disconnect |= sink is None
                if paused_disconnect and sink:
                    RECONNECT_PAUSE.unlink(missing_ok=True)
                    paused_disconnect = False
            else:
                paused_disconnect = False
                reconnect_pending |= sink is None
                if reconnect_pending and time.monotonic() >= next_attempt:
                    next_attempt = time.monotonic() + 15
                    print(restore_bose_audio(device), flush=True)
                    reconnect_pending = False
            last_error = None
        except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
            if str(exc) != last_error:
                last_error = str(exc)
                print(f"Reconexión de Bose: {last_error}", file=sys.stderr, flush=True)
        time.sleep(2)


if __name__ == "__main__":
    if sys.argv[1:] == ["--watch-audio"]:
        watch_bose_audio()
    else:
        BoseGUI().mainloop()
