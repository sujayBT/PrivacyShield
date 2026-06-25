"""
PrivacyShield — Smart Notification Service
==========================================
Shows a centered tkinter privacy-alert dialog for risk events.

Alert priority order for _send_risk_alert:
  1. tkinter centered dialog  ← ALWAYS used for risk alerts (custom popup)
  2. plyer / win10toast       ← ONLY used for start/stop toasts (informational)
  3. log-only                 ← silent fallback if all else fail

"View Details" opens the app on the /recommendations page.
Port is resolved dynamically from the BACKEND_PORT env var so the EXE
uses the correct dynamic port rather than the hardcoded dev port 5173.
"""
import logging
import os
import sys
import threading
import time

logger = logging.getLogger(__name__)


# ── Risk display config ────────────────────────────────────────────────────────
_RISK_CONFIG = {
    "CRITICAL": {
        "emoji":   "🔴",
        "label":   "CRITICAL RISK",
        "color":   "#ef4444",
        "bg_pill": "#450a0a",
    },
    "HIGH": {
        "emoji":   "🟠",
        "label":   "HIGH RISK",
        "color":   "#f97316",
        "bg_pill": "#431407",
    },
    "MEDIUM": {
        "emoji":   "🟡",
        "label":   "MEDIUM RISK",
        "color":   "#eab308",
        "bg_pill": "#422006",
    },
    "LOW": {
        "emoji":   "🔵",
        "label":   "LOW RISK",
        "color":   "#3b82f6",
        "bg_pill": "#1e3a5f",
    },
}

# ── Friendly PII type names ────────────────────────────────────────────────────
_TYPE_LABELS = {
    "email":           "Email Address",
    "phone":           "Phone Number",
    "aadhaar":         "Aadhaar Number",
    "pan":             "PAN Card",
    "pan_card":        "PAN Card",
    "credit_card":     "Credit Card",
    "password":        "Password",
    "otp":             "OTP / PIN",
    "dob":             "Date of Birth",
    "face_detected":   "Face / Photo",
    "id_card_visible": "ID Card",
    "location":        "Location Data",
    "username":        "Username",
    "display_name":    "Full Name",
    "bio":             "Personal Bio",
    "website":         "Website Link",
    "person":          "Person Name",
    "name":            "Person Name",
}


def _friendly_types(finding_types: list, max_items: int = 3) -> str:
    labels = [_TYPE_LABELS.get(t, t.replace("_", " ").title()) for t in finding_types[:max_items]]
    result = ", ".join(labels)
    remaining = len(finding_types) - max_items
    if remaining > 0:
        result += f" +{remaining} more"
    return result


# ── Dynamic frontend URL helper ────────────────────────────────────────────────
def _get_frontend_url(page: str = "recommendations") -> str:
    """
    Return the correct frontend URL for the current run mode.

    - In a frozen EXE: the Electron main sets BACKEND_PORT in the environment.
      The frontend is served by the backend on that same port.
      URL → http://127.0.0.1:{BACKEND_PORT}/{page}

    - In dev mode (not frozen): Vite dev server is always on 5173.
      URL → http://localhost:5173/{page}
    """
    is_frozen = getattr(sys, "frozen", False)
    if is_frozen:
        port = os.environ.get("BACKEND_PORT", "8000")
        return f"http://127.0.0.1:{port}/{page}"
    else:
        # Dev: frontend Vite dev server
        return f"http://localhost:5173/{page}"


# ── Check available notification libraries (for start/stop toasts only) ────────
_PLYER_AVAILABLE = False
_WIN10TOAST_AVAILABLE = False
_TK_AVAILABLE = False

try:
    from plyer import notification as _plyer_notification
    _PLYER_AVAILABLE = True
except Exception:
    pass

try:
    from win10toast import ToastNotifier as _ToastNotifier
    _WIN10TOAST_AVAILABLE = True
except Exception:
    pass

try:
    import tkinter as tk
    from tkinter import font as tkfont
    _TK_AVAILABLE = True
except Exception:
    tk = None
    tkfont = None

logger.info(
    "[notify] Available: plyer=%s win10toast=%s tkinter=%s",
    _PLYER_AVAILABLE, _WIN10TOAST_AVAILABLE, _TK_AVAILABLE,
)


# ── plyer notification (used only for informational toasts) ───────────────────
def _show_plyer(title: str, message: str, timeout_sec: int = 6):
    try:
        _plyer_notification.notify(
            title=title,
            message=message,
            app_name="PrivacyShield",
            app_icon="",
            timeout=max(timeout_sec, 5),
        )
    except Exception as e:
        logger.warning("[notify/plyer] Failed: %s", e)
        raise


# ── win10toast (used only for informational toasts) ───────────────────────────
def _show_win10toast(title: str, message: str, timeout_sec: int = 6):
    try:
        toaster = _ToastNotifier()
        toaster.show_toast(
            title,
            message,
            duration=max(timeout_sec, 5),
            threaded=False,
        )
    except Exception as e:
        logger.warning("[notify/win10toast] Failed: %s", e)
        raise


# ── Tkinter centered dialog ────────────────────────────────────────────────────
def _show_tkinter_dialog(source: str, name: str,
                          score: float, risk: str, finding_types: list):
    """
    Show a centered, borderless privacy-alert dialog.
    Blocks the calling thread until the user dismisses or clicks View Details.
    No animation, no auto-close loop.
    """
    if not _TK_AVAILABLE:
        logger.warning(
            "[notify] tkinter unavailable — alert logged only: [%s] %s score=%.0f",
            risk, name, score,
        )
        return

    cfg = _RISK_CONFIG.get(risk, _RISK_CONFIG["MEDIUM"])

    try:
        root = tk.Tk()
        root.withdraw()

        WIN_W, WIN_H = 420, 300
        root.title("PrivacyShield Alert")
        root.resizable(False, False)
        root.configure(bg="#0f1117")
        root.overrideredirect(True)   # no OS title bar

        # ── Center on screen ───────────────────────────────────────────────────
        root.update_idletasks()
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        x  = (sw - WIN_W) // 2
        y  = (sh - WIN_H) // 2
        root.geometry(f"{WIN_W}x{WIN_H}+{x}+{y}")

        root.attributes("-topmost", True)
        root.lift()
        root.focus_force()

        # ── Outer frame ────────────────────────────────────────────────────────
        outer = tk.Frame(root, bg="#1e2030", bd=0)
        outer.pack(fill="both", expand=True, padx=2, pady=2)

        # Colored accent bar at top
        tk.Frame(outer, bg=cfg["color"], height=4).pack(fill="x")

        # ── Header row ─────────────────────────────────────────────────────────
        hdr = tk.Frame(outer, bg="#1e2030")
        hdr.pack(fill="x", padx=20, pady=(12, 0))

        tk.Label(
            hdr,
            text="🛡  Privacy Protection Monitor",
            bg="#1e2030", fg="#94a3b8",
            font=("Segoe UI", 9, "bold"),
            anchor="w",
        ).pack(side="left")

        close_lbl = tk.Label(
            hdr, text="✕", bg="#1e2030", fg="#64748b",
            font=("Segoe UI", 11), cursor="hand2",
        )
        close_lbl.pack(side="right")
        close_lbl.bind("<Button-1>", lambda e: root.destroy())
        close_lbl.bind("<Enter>",    lambda e: close_lbl.config(fg="#f87171"))
        close_lbl.bind("<Leave>",    lambda e: close_lbl.config(fg="#64748b"))

        # ── Risk badge + score ─────────────────────────────────────────────────
        badge_row = tk.Frame(outer, bg="#1e2030")
        badge_row.pack(fill="x", padx=20, pady=(10, 0))

        tk.Label(
            badge_row,
            text=f"  {cfg['emoji']}  {cfg['label']}  ",
            bg=cfg["bg_pill"], fg=cfg["color"],
            font=("Segoe UI", 9, "bold"),
            padx=6, pady=3,
        ).pack(side="left")

        tk.Label(
            badge_row,
            text=f"  Score: {score:.0f}/100  ",
            bg="#1e293b", fg="#94a3b8",
            font=("Segoe UI", 9),
            padx=4, pady=3,
        ).pack(side="left", padx=(8, 0))

        # ── Source / filename ─────────────────────────────────────────────────
        src_icon  = "📸" if source == "screen" else "📄"
        src_label = "Screen detected" if source == "screen" else name
        tk.Label(
            outer,
            text=f"{src_icon}  {src_label[:48]}{'…' if len(src_label) > 48 else ''}",
            bg="#1e2030", fg="#e2e8f0",
            font=("Segoe UI", 11, "bold"),
            anchor="w",
        ).pack(fill="x", padx=20, pady=(12, 0))

        # ── Finding types ──────────────────────────────────────────────────────
        if finding_types:
            tk.Label(
                outer,
                text="Detected sensitive data:",
                bg="#1e2030", fg="#64748b",
                font=("Segoe UI", 8, "bold"),
                anchor="w",
            ).pack(fill="x", padx=20, pady=(10, 2))

            lines = [
                f"  •  {_TYPE_LABELS.get(t, t.replace('_', ' ').title())}"
                for t in finding_types[:3]
            ]
            if len(finding_types) > 3:
                lines.append(f"  •  +{len(finding_types) - 3} more")

            tk.Label(
                outer,
                text="\n".join(lines),
                bg="#1e2030", fg="#cbd5e1",
                font=("Segoe UI", 10),
                anchor="w", justify="left",
            ).pack(fill="x", padx=20)

        # ── Divider ────────────────────────────────────────────────────────────
        tk.Frame(outer, bg="#2d3748", height=1).pack(fill="x", padx=20, pady=14)

        # ── Buttons ────────────────────────────────────────────────────────────
        btn_row = tk.Frame(outer, bg="#1e2030")
        btn_row.pack(fill="x", padx=20, pady=(0, 18))

        def on_view_details():
            url = _get_frontend_url("recommendations")
            # Schedule the browser open AFTER the window destroys so the
            # tkinter mainloop exits cleanly first, then the browser opens.
            def _open_and_destroy():
                root.destroy()
                try:
                    import webbrowser
                    webbrowser.open(url)
                except Exception as err:
                    logger.warning("[notify] Could not open browser: %s", err)
            root.after(0, _open_and_destroy)

        view_btn = tk.Button(
            btn_row,
            text="View Details",
            command=on_view_details,
            bg=cfg["color"], fg="#ffffff",
            font=("Segoe UI", 10, "bold"),
            relief="flat", bd=0,
            padx=18, pady=7,
            cursor="hand2",
            activebackground=cfg["color"],
            activeforeground="#fff",
        )
        view_btn.pack(side="left")

        dismiss_btn = tk.Button(
            btn_row,
            text="Dismiss",
            command=root.destroy,
            bg="#1e293b", fg="#94a3b8",
            font=("Segoe UI", 10),
            relief="flat", bd=0,
            padx=14, pady=7,
            cursor="hand2",
            activebackground="#334155",
            activeforeground="#e2e8f0",
        )
        dismiss_btn.pack(side="left", padx=(10, 0))
        dismiss_btn.bind("<Enter>", lambda e: dismiss_btn.config(bg="#334155", fg="#e2e8f0"))
        dismiss_btn.bind("<Leave>", lambda e: dismiss_btn.config(bg="#1e293b", fg="#94a3b8"))

        # ── Drag to move ───────────────────────────────────────────────────────
        def start_move(e):
            root._drag_x = e.x_root - root.winfo_x()
            root._drag_y = e.y_root - root.winfo_y()

        def do_move(e):
            root.geometry(f"+{e.x_root - root._drag_x}+{e.y_root - root._drag_y}")

        for w in (outer, hdr):
            w.bind("<Button-1>",  start_move)
            w.bind("<B1-Motion>", do_move)

        # ── Show (no auto-close — user must dismiss or click View Details) ─────
        root.deiconify()
        root.mainloop()

    except Exception as e:
        logger.warning("[notify/tkinter] Dialog failed: %s", e)


# ── Unified risk-alert dispatcher ──────────────────────────────────────────────
def _dispatch_risk_alert(source: str, name: str,
                          score: float, risk: str, finding_types: list):
    """
    Always show the custom tkinter dialog for risk alerts.
    Fall back to log-only if tkinter is unavailable.
    """
    if _TK_AVAILABLE:
        try:
            _show_tkinter_dialog(source, name, score, risk, finding_types)
            return
        except Exception:
            pass

    # Last resort: log only
    logger.warning(
        "[notify] tkinter failed — alert logged: [%s] %s score=%.0f findings=%s",
        risk, name, score, finding_types,
    )


# ── Cooldown for screen alerts (avoid rapid-fire repeats) ─────────────────────
_last_alert_time = {"screen": 0.0}
_SCREEN_COOLDOWN = 30   # seconds


# ── Public API ─────────────────────────────────────────────────────────────────

def send_risk_alert(
    source: str,
    name: str,
    score: float,
    risk: str,
    finding_types: list,
):
    """
    Show a centered tkinter privacy-alert popup.
    Only fires for MEDIUM, HIGH, or CRITICAL risks.
    Non-blocking — runs in a daemon thread.
    """
    if risk in ("SAFE", "LOW"):
        return

    if source == "screen":
        now = time.time()
        if now - _last_alert_time.get("screen", 0.0) < _SCREEN_COOLDOWN:
            logger.info("[notify] Screen alert suppressed (cooldown active)")
            return
        _last_alert_time["screen"] = now

    threading.Thread(
        target=_dispatch_risk_alert,
        args=(source, name, score, risk, finding_types),
        daemon=True,
    ).start()

    logger.info("[notify] Alert dispatched [%s] %s score=%.0f", risk, name, score)


def send_agent_started(folder_count: int):
    """Show a startup toast when background agent is enabled."""
    msg_title = "✅ PrivacyShield — Background Protection Active"
    msg_body  = (
        f"Now monitoring {folder_count} folder(s) for sensitive files.\n"
        "You'll be alerted if PII is detected."
    )
    if _PLYER_AVAILABLE:
        try:
            threading.Thread(
                target=_show_plyer,
                args=(msg_title, msg_body, 6),
                daemon=True,
            ).start()
            return
        except Exception:
            pass
    if _WIN10TOAST_AVAILABLE:
        try:
            threading.Thread(
                target=_show_win10toast,
                args=(msg_title, msg_body, 6),
                daemon=True,
            ).start()
            return
        except Exception:
            pass
    logger.info("[notify] Background agent started — watching %d folder(s)", folder_count)


def send_agent_stopped():
    """Stopped notice — silent."""
    logger.info("[notify] Background agent stopped.")


def send_safe_scan(name: str):
    """Silent for SAFE — never notify."""
    logger.info("[notify] Safe scan: %s — no notification sent", name)
