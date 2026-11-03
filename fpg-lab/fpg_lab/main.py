from __future__ import annotations

from nicegui import app, ui

from fpg_lab.core.settings import get_settings
from fpg_lab.runtime import LabRuntime
from fpg_lab.ui.pages import register_pages


def main() -> None:
    settings = get_settings()
    runtime = LabRuntime()
    app.on_startup(runtime.start)
    app.on_shutdown(runtime.close)
    register_pages(runtime)
    ui.run(
        host=settings.host,
        port=settings.port,
        reload=False,
        show=False,
        title="FPG Lab",
        dark=True,
        fastapi_docs=False,
    )
