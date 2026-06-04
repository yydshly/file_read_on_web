"""System tray controller for 资料浏览器.

Provides a Windows system tray icon with menu:
  - 打开资料浏览器
  - 查看日志
  - 打开数据目录
  - 退出程序

Requires pystray and Pillow. Fails gracefully if unavailable — the app
continues to run without a tray icon.
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Callable, Optional

# pystray is optional — import lazily to avoid hard dependency
try:
    import pystray
    _PYSTRAY_AVAILABLE = True
except Exception:  # pragma: no cover — tested fallback path
    _PYSTRAY_AVAILABLE = False

try:
    from PIL import Image
    _PIL_AVAILABLE = True
except Exception:  # pragma: no cover — tested fallback path
    _PIL_AVAILABLE = False


def _load_icon_image(icon_path: Path) -> Optional["Image.Image"]:
    """Load a PIL Image from an .ico or .png file.

    Returns None on any failure; callers must handle that gracefully.
    """
    if not _PIL_AVAILABLE:
        return None
    try:
        return Image.open(str(icon_path))
    except Exception:
        return None


def _open_url_in_browser(url: str) -> bool:
    """Open a URL in the default browser."""
    try:
        if sys.platform.startswith("win"):
            os.startfile(url)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", url])
        return True
    except Exception:
        return False


class TrayController:
    """Manages the Windows system tray icon and its menu.

    All menu actions are executed in the tray's own daemon thread.
    Instances are safe to create even when pystray/Pillow are unavailable —
    start() will simply return False without crashing the host process.
    """

    def __init__(
        self,
        app_name: str,
        url: str,
        data_dir: Path,
        log_file: Path,
        icon_path: Path,
        open_url: Callable[[str], bool],
        shutdown_callback: Callable[[str], None],
    ) -> None:
        self._app_name = app_name
        self._url = url
        self._data_dir = data_dir
        self._log_file = log_file
        self._icon_path = icon_path
        self._open_url = open_url
        self._shutdown_callback = shutdown_callback

        self._icon: Optional["pystray.Icon"] = None
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Menu action callbacks (run inside the tray thread)
    # ------------------------------------------------------------------

    def _action_open_app(self) -> None:
        """Open the app URL in the default browser."""
        self._open_url(self._url)

    def _action_open_log(self) -> None:
        """Open the app log file or its containing directory."""
        if self._log_file.exists():
            try:
                if sys.platform.startswith("win"):
                    os.startfile(str(self._log_file))
                else:
                    subprocess.Popen(["xdg-open", str(self._log_file)])
            except Exception:
                # Fallback: open the logs directory
                log_dir = self._log_file.parent
                try:
                    if sys.platform.startswith("win"):
                        os.startfile(str(log_dir))
                    else:
                        subprocess.Popen(["xdg-open", str(log_dir)])
                except Exception:
                    pass
        else:
            # Log file doesn't exist yet; open its directory
            log_dir = self._log_file.parent
            try:
                if sys.platform.startswith("win"):
                    os.startfile(str(log_dir))
                else:
                    subprocess.Popen(["xdg-open", str(log_dir)])
            except Exception:
                pass

    def _action_open_data_dir(self) -> None:
        """Open the app data directory in the file manager."""
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(self._data_dir))
            else:
                subprocess.Popen(["xdg-open", str(self._data_dir)])
        except Exception:
            pass

    def _action_exit(self) -> None:
        """Stop the tray and request application shutdown."""
        # Schedule stop outside the menu callback so we don't deadlock
        # on icon.stop() while inside pystray's event dispatch.
        threading.Thread(target=self.stop, daemon=True).start()
        self._shutdown_callback("tray")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> bool:
        """Start the tray icon in a background daemon thread.

        Returns True if the tray was started successfully, False if it
        could not be started (pystray/Pillow unavailable or icon not found).
        Does not raise; failure is logged and the caller continues normally.
        """
        if not _PYSTRAY_AVAILABLE or not _PIL_AVAILABLE:
            return False

        # Try to load icon image from the packaged static path first,
        # then fall back to the app directory.
        img = _load_icon_image(self._icon_path)
        if img is None:
            # Icon loading failed — pystray requires an image
            return False

        try:
            menu = pystray.Menu(
                pystray.MenuItem("打开资料浏览器", self._action_open_app),
                pystray.MenuItem("查看日志", self._action_open_log),
                pystray.MenuItem("打开数据目录", self._action_open_data_dir),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("退出程序", self._action_exit),
            )
            self._icon = pystray.Icon(
                self._app_name,
                img,
                self._app_name,
                menu,
            )
        except Exception:
            return False

        self._thread = threading.Thread(target=self._run_icon, daemon=True, name="TrayIcon")
        self._thread.start()
        return True

    def _run_icon(self) -> None:
        """Run the pystray event loop. Called in the tray thread."""
        try:
            self._icon.run()  # type: ignore[union-attr]
        except Exception:
            # pystray.Icon.run() may raise if stop() is called concurrently;
            # ignore it — the icon is shutting down as intended.
            pass

    def stop(self) -> None:
        """Stop the tray icon and wait for its thread to finish."""
        if self._icon is not None:
            try:
                self._icon.stop()  # type: ignore[union-attr]
            except Exception:
                pass
            self._icon = None

        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None
