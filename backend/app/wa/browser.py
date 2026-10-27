"""Satu Chrome (profil khusus app) yang dikendalikan Playwright, lewat satu thread worker.

Playwright mode sync hanya boleh dipanggil dari thread yang membuatnya, sedangkan
FastAPI menjalankan request di thread berbeda-beda. Karena itu semua perintah ke
browser dikirim ke antrean dan dijalankan berurutan oleh thread `wa-worker`:

    result = worker.call(lambda b: b.page.title())
"""

import logging
import queue
import threading
from concurrent.futures import Future
from typing import Any, Callable, TypeVar

from playwright.sync_api import BrowserContext, Page, Playwright, sync_playwright

from .. import paths
from . import selectors as S

log = logging.getLogger(__name__)
T = TypeVar("T")


class BrowserClosed(Exception):
    """Jendela Chrome app ditutup pengguna / belum dibuka."""


class Browser:
    """Hanya dipakai dari dalam thread worker."""

    def __init__(self, pw: Playwright) -> None:
        self.pw = pw
        self.ctx: BrowserContext | None = None
        self._page: Page | None = None

    @property
    def is_open(self) -> bool:
        return self.ctx is not None and self._page is not None and not self._page.is_closed()

    @property
    def page(self) -> Page:
        if not self.is_open:
            raise BrowserClosed("Jendela WhatsApp belum dibuka.")
        return self._page  # type: ignore[return-value]

    def open(self) -> Page:
        """Buka Chrome profil app di WhatsApp Web (tidak membuka dua kali)."""
        if self.is_open:
            self._page.bring_to_front()  # type: ignore[union-attr]
            return self._page  # type: ignore[return-value]
        paths.ensure_dirs()
        self.ctx = self.pw.chromium.launch_persistent_context(
            user_data_dir=str(paths.CHROME_PROFILE_DIR),
            channel="chrome",  # pakai Chrome yang sudah terpasang
            headless=False,
            no_viewport=True,
            args=["--start-maximized", "--disable-features=Translate"],
        )
        self.ctx.on("close", lambda _: self._on_close())
        self._page = self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()
        self._page.goto(S.WA_URL, wait_until="domcontentloaded")
        log.info("Chrome WhatsApp dibuka")
        return self._page

    def _on_close(self) -> None:
        log.info("Chrome WhatsApp ditutup")
        self.ctx = None
        self._page = None

    def close(self) -> None:
        if self.ctx is not None:
            try:
                self.ctx.close()
            except Exception:  # sudah tertutup
                pass
        self._on_close()


class Worker:
    def __init__(self) -> None:
        self._q: queue.Queue[tuple[Callable[[Browser], Any] | None, Future]] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self.browser: Browser | None = None

    def browser_open(self) -> bool:
        """True bila jendela WhatsApp app sedang terbuka (tanpa menyalakan worker)."""
        return bool(self._thread and self._thread.is_alive() and self.browser and self.browser.is_open)

    def _ensure_thread(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            ready: Future = Future()
            self._thread = threading.Thread(target=self._loop, args=(ready,), name="wa-worker", daemon=True)
            self._thread.start()
            ready.result(timeout=60)

    def _loop(self, ready: Future) -> None:
        try:
            pw = sync_playwright().start()
        except Exception as e:
            ready.set_exception(e)
            return
        browser = Browser(pw)
        self.browser = browser
        ready.set_result(True)
        while True:
            fn, fut = self._q.get()
            if fn is None:
                break
            if fut.set_running_or_notify_cancel():
                try:
                    fut.set_result(fn(browser))
                except BaseException as e:  # diteruskan ke pemanggil
                    fut.set_exception(e)
        browser.close()
        pw.stop()
        fut.set_result(None)

    def call(self, fn: Callable[[Browser], T], timeout: float = 120) -> T:
        self._ensure_thread()
        fut: Future = Future()
        self._q.put((fn, fut))
        return fut.result(timeout=timeout)

    def shutdown(self, timeout: float = 15) -> None:
        if self._thread and self._thread.is_alive():
            fut: Future = Future()
            self._q.put((None, fut))
            try:
                fut.result(timeout=timeout)
            except Exception:
                pass


worker = Worker()
