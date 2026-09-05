from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from levelupdiag_core.config import load_config
from levelupdiag_core.manifest import load_manifest

TOOL_ROOT = Path(__file__).resolve().parent


class LevelUpDiagConsole(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LevelUpDiag-Koali 2.2 — Core Stabilization First")
        self.minsize(900, 720)
        self.geometry("1040x820")

        self.process: subprocess.Popen[str] | None = None
        self.output_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.level_vars: dict[str, tk.BooleanVar] = {}
        self.level_names: dict[str, str] = {}
        self.manifest: dict = {}
        self.mode_var = tk.StringVar(value="debug")

        self._build_ui()
        self._load_levels()
        self.after(80, self._poll_output)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=12)
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x")
        ttk.Label(header, text="LevelUpDiag-Koali", font=("Segoe UI", 14, "bold")).pack(side="left")
        self.status_var = tk.StringVar(value="Prêt — STABILISATION KOALI")
        ttk.Label(header, textvariable=self.status_var).pack(side="right")

        ttk.Label(
            outer,
            text=(
                "STABILISATION KOALI vérifie d'abord l'environnement, les contrats et les composants natifs. "
                "Konnaxion reste placeholder; Ariane, Orgo et Semantik Architect sont différés jusqu'à l'intégration explicite. "
                "Le profil souverain final reste strict et n'est pas affaibli."
            ),
            wraplength=980,
        ).pack(anchor="w", pady=(4, 10))

        mode_box = ttk.LabelFrame(outer, text="Politique d'exécution")
        mode_box.pack(fill="x", pady=(0, 8))
        ttk.Radiobutton(mode_box, text="DEBUG — non bloquant", value="debug", variable=self.mode_var,
                        command=self._mode_changed).pack(side="left", padx=10, pady=6)
        ttk.Radiobutton(mode_box, text="VALIDATION — conformité", value="validation", variable=self.mode_var,
                        command=self._mode_changed).pack(side="left", padx=10, pady=6)
        ttk.Radiobutton(mode_box, text="RELEASE — strict", value="release", variable=self.mode_var,
                        command=self._mode_changed).pack(side="left", padx=10, pady=6)

        presets = ttk.Frame(outer)
        presets.pack(fill="x", pady=(0, 8))
        ttk.Button(presets, text="STABILISATION KOALI", command=lambda: self._select_campaign("stabilization", "debug")).pack(side="left", padx=(0, 5))
        ttk.Button(presets, text="RUNTIME CORE", command=lambda: self._select_campaign("stabilization-runtime", "debug")).pack(side="left", padx=5)
        ttk.Button(presets, text="DEBUG COMPLET", command=lambda: self._select_campaign("stabilization", "debug")).pack(side="left", padx=5)
        ttk.Button(presets, text="STRUCTURE", command=lambda: self._select_campaign("structure", "validation")).pack(side="left", padx=5)
        ttk.Button(presets, text="VALIDATION", command=lambda: self._select_campaign("validation", "validation")).pack(side="left", padx=5)
        ttk.Button(presets, text="RELEASE", command=lambda: self._select_campaign("release", "release")).pack(side="left", padx=5)

        self.level_frame = ttk.LabelFrame(outer, text="Niveaux")
        self.level_frame.pack(fill="x")

        self.policy_var = tk.StringVar(value="")
        ttk.Label(outer, textvariable=self.policy_var, wraplength=980).pack(anchor="w", pady=(7, 8))

        actions = ttk.Frame(outer)
        actions.pack(fill="x", pady=(0, 8))
        self.run_button = ttk.Button(actions, text="LANCER SÉLECTION", command=self._run_selected)
        self.run_button.pack(side="left", padx=(0, 6))
        self.stop_button = ttk.Button(actions, text="ARRÊTER", command=self._stop, state="disabled")
        self.stop_button.pack(side="left", padx=6)
        ttk.Button(actions, text="EFFACER CONSOLE", command=self._clear_console).pack(side="left", padx=6)

        log_actions = ttk.Frame(outer)
        log_actions.pack(fill="x", pady=(0, 8))
        ttk.Button(log_actions, text="OUVRIR DOSSIER LOG", command=self._open_log_folder).pack(side="left", padx=(0, 6))
        ttk.Button(log_actions, text="COPIER DOSSIER LOG", command=self._copy_log_folder).pack(side="left", padx=6)
        self.log_path_var = tk.StringVar(value="Dernier log: —")
        ttk.Label(log_actions, textvariable=self.log_path_var).pack(side="left", padx=(12, 0), fill="x", expand=True)

        ttk.Label(outer, text="Console", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(4, 4))
        self.console = ScrolledText(outer, wrap="word", height=24, font=("Consolas", 10))
        self.console.pack(fill="both", expand=True)
        self.console.configure(state="disabled")
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _load_levels(self) -> None:
        try:
            self.manifest = load_manifest(TOOL_ROOT)
        except Exception as exc:
            messagebox.showerror("LevelUpDiag", f"Impossible de charger le manifest:\n{exc}")
            self.run_button.configure(state="disabled")
            return

        levels = sorted(self.manifest["levels"], key=lambda item: (item.get("order", 0), item["id"]))
        for index, level in enumerate(levels):
            lid = level["id"]
            self.level_names[lid] = level["name"]
            var = tk.BooleanVar(value=False)
            self.level_vars[lid] = var
            row = index // 2
            col = index % 2
            ttk.Checkbutton(
                self.level_frame,
                text=f"{lid}  {level['name']}",
                variable=var,
            ).grid(row=row, column=col, sticky="w", padx=12, pady=5)

        self.level_frame.columnconfigure(0, weight=1)
        self.level_frame.columnconfigure(1, weight=1)
        self._select_campaign("debug", "debug")
        self._refresh_latest_log_path()

    def _select_campaign(self, campaign: str, mode: str) -> None:
        wanted = set(self.manifest.get("campaigns", {}).get(campaign, {}).get("levels", []))
        for lid, var in self.level_vars.items():
            var.set(lid in wanted)
        self.mode_var.set(mode)
        self._mode_changed()

    def _select_all(self) -> None:
        for var in self.level_vars.values():
            var.set(True)
        self._mode_changed()

    def _select_none(self) -> None:
        for var in self.level_vars.values():
            var.set(False)
        self._mode_changed()

    def _mode_changed(self) -> None:
        mode = self.mode_var.get()
        if mode == "debug":
            text = "DEBUG/STABILISATION: les blockers restent locaux. Le scope core ne prétend pas qualifier les sous-systèmes différés ni le profil souverain final."
        elif mode == "validation":
            text = "VALIDATION: les erreurs de configuration/infrastructure et BLOCKED peuvent bloquer leurs dépendants; Git propre n'est pas imposé globalement."
        else:
            text = "RELEASE: politique stricte avec protection de l'état Git suivi et dépendances bloquantes."
        self.policy_var.set(text)
        if self.process is None:
            self.status_var.set(f"Prêt — {mode.upper()}")

    def _python_executable(self) -> str:
        executable = Path(sys.executable)
        if os.name == "nt" and executable.name.lower() == "pythonw.exe":
            console_python = executable.with_name("python.exe")
            if console_python.exists():
                return str(console_python)
        return str(executable)

    def _campaign_for_selected(self, selected: list[str], mode: str) -> str | None:
        wanted = set(selected)
        preferred = ("stabilization", "stabilization-runtime", "debug", "structure", "validation", "release")
        campaigns = self.manifest.get("campaigns", {})
        for name in preferred:
            meta = campaigns.get(name, {})
            if meta.get("mode") == mode and set(meta.get("levels", [])) == wanted:
                return name
        return None

    def _run_selected(self) -> None:
        if self.process is not None:
            messagebox.showinfo("LevelUpDiag", "Un diagnostic est déjà en cours.")
            return

        selected = [lid for lid, var in self.level_vars.items() if var.get()]
        if not selected:
            messagebox.showwarning("LevelUpDiag", "Sélectionne au moins un niveau.")
            return

        mode = self.mode_var.get()
        selection = self._campaign_for_selected(selected, mode) or ",".join(selected)
        command = [
            self._python_executable(), str(TOOL_ROOT / "levelupdiag.py"),
            "run", selection, "--mode", mode,
        ]

        self._append(f"\n$ {' '.join(command)}\n")
        self.status_var.set(f"Exécution {mode.upper()}: {selection}")
        self.run_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        threading.Thread(target=self._worker, args=(command,), daemon=True).start()

    def _worker(self, command: list[str]) -> None:
        try:
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            self.process = subprocess.Popen(
                command,
                cwd=str(TOOL_ROOT),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                shell=False,
                creationflags=creationflags,
            )
            assert self.process.stdout is not None
            for line in self.process.stdout:
                self.output_queue.put(("line", line))
            self.output_queue.put(("done", self.process.wait()))
        except Exception as exc:
            self.output_queue.put(("error", str(exc)))
        finally:
            self.process = None

    def _poll_output(self) -> None:
        try:
            while True:
                kind, payload = self.output_queue.get_nowait()
                if kind == "line":
                    self._append(str(payload))
                elif kind == "done":
                    code = int(payload)
                    self._append(f"\n[Terminé — code {code}]\n")
                    self.status_var.set(f"Terminé — code {code}")
                    self.run_button.configure(state="normal")
                    self.stop_button.configure(state="disabled")
                    self._refresh_latest_log_path()
                elif kind == "error":
                    self._append(f"\n[ERREUR] {payload}\n")
                    self.status_var.set("Erreur")
                    self.run_button.configure(state="normal")
                    self.stop_button.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(80, self._poll_output)

    def _stop(self) -> None:
        process = self.process
        if process is None:
            return
        if not messagebox.askyesno("LevelUpDiag", "Arrêter le diagnostic en cours ?"):
            return
        try:
            process.terminate()
            self._append("\n[Arrêt demandé]\n")
            self.status_var.set("Arrêt demandé")
        except OSError as exc:
            messagebox.showerror("LevelUpDiag", str(exc))

    def _clear_console(self) -> None:
        self.console.configure(state="normal")
        self.console.delete("1.0", "end")
        self.console.configure(state="disabled")

    def _append(self, text: str) -> None:
        self.console.configure(state="normal")
        self.console.insert("end", text)
        self.console.see("end")
        self.console.configure(state="disabled")

    def _control_root(self) -> Path:
        cfg = load_config(TOOL_ROOT)
        return Path(cfg["_control_root"])

    def _latest_run_folder(self) -> Path | None:
        try:
            control = self._control_root()
            latest_summary = control / "latest" / "summary.json"
            if latest_summary.is_file():
                data = json.loads(latest_summary.read_text(encoding="utf-8"))
                run_id = data.get("run_id")
                if isinstance(run_id, str) and run_id:
                    candidate = control / "runs" / run_id
                    if candidate.is_dir():
                        return candidate
            runs = control / "runs"
            if runs.is_dir():
                candidates = [path for path in runs.iterdir() if path.is_dir()]
                if candidates:
                    return max(candidates, key=lambda path: path.stat().st_mtime)
        except Exception:
            return None
        return None

    def _refresh_latest_log_path(self) -> None:
        folder = self._latest_run_folder()
        self.log_path_var.set(f"Dernier log: {folder}" if folder else "Dernier log: —")

    def _open_log_folder(self) -> None:
        folder = self._latest_run_folder()
        if folder is None:
            messagebox.showwarning("LevelUpDiag", "Aucun dossier de log trouvé.")
            return
        try:
            if os.name == "nt":
                os.startfile(folder)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)])
        except OSError as exc:
            messagebox.showerror("LevelUpDiag", f"Impossible d'ouvrir le dossier:\n{exc}")

    def _copy_log_folder(self) -> None:
        source = self._latest_run_folder()
        if source is None:
            messagebox.showwarning("LevelUpDiag", "Aucun dossier de log trouvé.")
            return
        destination_parent = filedialog.askdirectory(title="Choisir où copier le dossier de log")
        if not destination_parent:
            return
        destination = Path(destination_parent) / source.name
        if destination.exists() and not messagebox.askyesno(
            "LevelUpDiag", f"Le dossier existe déjà:\n{destination}\n\nFusionner/remplacer les fichiers ?"
        ):
            return
        try:
            shutil.copytree(source, destination, dirs_exist_ok=True)
            messagebox.showinfo("LevelUpDiag", f"Dossier copié:\n{destination}")
        except OSError as exc:
            messagebox.showerror("LevelUpDiag", f"Copie impossible:\n{exc}")

    def _on_close(self) -> None:
        if self.process is not None:
            if not messagebox.askyesno("LevelUpDiag", "Un diagnostic est en cours. Fermer quand même ?"):
                return
            try:
                self.process.terminate()
            except OSError:
                pass
        self.destroy()


if __name__ == "__main__":
    LevelUpDiagConsole().mainloop()
