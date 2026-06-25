"""
updater.py — PrivacyShield Auto-Updater
Checks GitHub Releases for a newer version, downloads it, and launches the installer.
Bundle this with: pyinstaller updater.spec
"""
import json
import os
import sys
import tempfile
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox
import urllib.request
import urllib.error

# ── Config (edit these to match your GitHub repo) ─────────────────────────────
GITHUB_OWNER  = "YOUR_GITHUB_USERNAME"
GITHUB_REPO   = "PrivacyShield"
VERSION_FILE  = os.path.join(os.path.dirname(sys.executable), "version.json")
API_URL       = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
USER_AGENT    = "PrivacyShield-Updater/1.0"
# ─────────────────────────────────────────────────────────────────────────────


def get_local_version() -> str:
    """Read local version.json. Returns '0.0.0' if missing."""
    try:
        if os.path.exists(VERSION_FILE):
            with open(VERSION_FILE, "r") as f:
                return json.load(f).get("version", "0.0.0")
    except Exception:
        pass
    return "0.0.0"


def version_tuple(v: str):
    """Convert '1.2.3' → (1, 2, 3) for comparison."""
    try:
        return tuple(int(x) for x in v.lstrip("v").split("."))
    except Exception:
        return (0, 0, 0)


def fetch_release_info():
    """Query GitHub API. Returns (tag, download_url, body) or raises."""
    req = urllib.request.Request(API_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())

    tag = data.get("tag_name", "").lstrip("v")
    body = data.get("body", "")
    download_url = None

    for asset in data.get("assets", []):
        name: str = asset.get("name", "")
        # Match installer files: PrivacyShield-Setup-*.exe  or  PrivacyShield-*.exe
        if name.lower().endswith(".exe") and ("setup" in name.lower() or "privacyshield" in name.lower()):
            download_url = asset["browser_download_url"]
            break

    return tag, download_url, body


# ── GUI ───────────────────────────────────────────────────────────────────────

class UpdaterApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("PrivacyShield — Updater")
        self.root.geometry("480x320")
        self.root.resizable(False, False)
        self.root.configure(bg="#0f172a")

        # ── Try to set icon ───────────────────────────────────────────────────
        icon_path = os.path.join(os.path.dirname(sys.executable), "icon.ico")
        if os.path.exists(icon_path):
            try:
                self.root.iconbitmap(icon_path)
            except Exception:
                pass

        self.download_url = None
        self.latest_version = None
        self._build_ui()
        # Start check after window draws
        self.root.after(500, self._check_thread)

    # ── Layout ────────────────────────────────────────────────────────────────
    def _build_ui(self):
        outer = tk.Frame(self.root, bg="#0f172a", padx=30, pady=24)
        outer.pack(fill="both", expand=True)

        # Logo / title
        tk.Label(outer, text="🛡️  PrivacyShield Updater", fg="#06b6d4", bg="#0f172a",
                 font=("Segoe UI", 16, "bold")).pack(anchor="w")

        # Installed version
        self.local_var = tk.StringVar(value=f"Installed: v{get_local_version()}")
        tk.Label(outer, textvariable=self.local_var, fg="#94a3b8", bg="#0f172a",
                 font=("Segoe UI", 10)).pack(anchor="w", pady=(4, 0))

        # Status label
        self.status_var = tk.StringVar(value="Checking for updates…")
        self.status_lbl = tk.Label(outer, textvariable=self.status_var, fg="#e2e8f0",
                                   bg="#0f172a", font=("Segoe UI", 11), wraplength=420,
                                   justify="left")
        self.status_lbl.pack(anchor="w", pady=(20, 8))

        # Progress bar (hidden until download)
        self.progress_var = tk.DoubleVar(value=0)
        self.progress = ttk.Progressbar(outer, variable=self.progress_var,
                                        maximum=100, length=420, mode="determinate")
        self.progress_pct = tk.Label(outer, text="", fg="#94a3b8", bg="#0f172a",
                                     font=("Segoe UI", 9))

        # Release notes
        self.notes_frame = tk.Frame(outer, bg="#0f172a")
        self.notes_text = tk.Text(self.notes_frame, height=5, width=56, bg="#1e293b",
                                  fg="#cbd5e1", font=("Segoe UI", 9), relief="flat",
                                  wrap="word", state="disabled")
        self.notes_text.pack(fill="both", expand=True)

        # Buttons
        btn_frame = tk.Frame(outer, bg="#0f172a")
        btn_frame.pack(side="bottom", fill="x", pady=(12, 0))

        self.update_btn = tk.Button(
            btn_frame, text="Download & Install", state="disabled",
            bg="#06b6d4", fg="white", font=("Segoe UI", 10, "bold"),
            relief="flat", padx=16, pady=8, cursor="hand2",
            command=self._start_download
        )
        self.update_btn.pack(side="left")

        tk.Button(btn_frame, text="Close", bg="#1e293b", fg="#94a3b8",
                  font=("Segoe UI", 10), relief="flat", padx=14, pady=8,
                  cursor="hand2", command=self.root.destroy).pack(side="right")

    # ── Update check ─────────────────────────────────────────────────────────
    def _check_thread(self):
        threading.Thread(target=self._check_for_update, daemon=True).start()

    def _check_for_update(self):
        try:
            tag, url, body = fetch_release_info()
            local = get_local_version()

            if version_tuple(tag) > version_tuple(local):
                self.latest_version = tag
                self.download_url   = url
                self.root.after(0, lambda: self._show_update_available(tag, url, body, local))
            else:
                self.root.after(0, lambda: self._show_up_to_date(local))
        except Exception as e:
            self.root.after(0, lambda: self._show_error(str(e)))

    def _show_update_available(self, tag, url, body, local):
        self.status_var.set(f"✅  New version v{tag} is available!  (you have v{local})")
        self.status_lbl.config(fg="#22c55e")

        if body:
            self.notes_frame.pack(fill="x", pady=(0, 10))
            self.notes_text.config(state="normal")
            self.notes_text.insert("1.0", body[:800])
            self.notes_text.config(state="disabled")

        if url:
            self.update_btn.config(state="normal")
        else:
            self.status_var.set(f"v{tag} is available but no installer asset found.\nVisit GitHub to download manually.")

    def _show_up_to_date(self, local):
        self.status_var.set(f"✔  You are running the latest version (v{local}).")
        self.status_lbl.config(fg="#06b6d4")

    def _show_error(self, msg):
        self.status_var.set(f"⚠  Could not check for updates.\n{msg}")
        self.status_lbl.config(fg="#f59e0b")

    # ── Download ──────────────────────────────────────────────────────────────
    def _start_download(self):
        if not self.download_url:
            return
        self.update_btn.config(state="disabled", text="Downloading…")
        self.progress.pack(fill="x", pady=(4, 2))
        self.progress_pct.pack(anchor="e")
        threading.Thread(target=self._download, daemon=True).start()

    def _download(self):
        try:
            tmp_dir = tempfile.mkdtemp(prefix="privacyshield_update_")
            filename = self.download_url.split("/")[-1]
            dest = os.path.join(tmp_dir, filename)

            def _progress(block_count, block_size, total_size):
                if total_size > 0:
                    pct = min(block_count * block_size / total_size * 100, 100)
                    self.root.after(0, lambda p=pct: self._set_progress(p))

            urllib.request.urlretrieve(self.download_url, dest, _progress)
            self.root.after(0, lambda: self._on_download_done(dest))
        except Exception as e:
            self.root.after(0, lambda: self._on_download_error(str(e)))

    def _set_progress(self, pct):
        self.progress_var.set(pct)
        self.progress_pct.config(text=f"{pct:.0f}%")

    def _on_download_done(self, dest):
        self.status_var.set(f"✅  Download complete. Launching installer…")
        self.status_lbl.config(fg="#22c55e")
        self.progress_var.set(100)
        self.root.after(1000, lambda: self._launch_installer(dest))

    def _on_download_error(self, msg):
        self.status_var.set(f"❌  Download failed: {msg}")
        self.status_lbl.config(fg="#ef4444")
        self.update_btn.config(state="normal", text="Retry")

    def _launch_installer(self, installer_path):
        """Launch the NSIS installer silently, then quit the updater."""
        try:
            # /S = silent install (NSIS). Remove /S for interactive mode.
            subprocess.Popen([installer_path], shell=False)
        except Exception as e:
            messagebox.showerror("Error", f"Could not launch installer:\n{e}")
            return
        self.root.destroy()


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    app = UpdaterApp(root)
    root.mainloop()
