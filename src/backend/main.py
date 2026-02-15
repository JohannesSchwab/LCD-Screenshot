import logging
from contextlib import redirect_stdout
from io import StringIO

import webview
from server import server

logger = logging.getLogger(__name__)


if __name__ == "__main__":
    stream = StringIO()
    with redirect_stdout(stream):
        window = webview.create_window(  # type: ignore
            "LCD Screenshot",
            server,
            width=1200,
            height=800,
        )

        def _on_closing():
            logger.info("Window is closing...")
            try:
                for open_window in webview.windows:
                    open_window.destroy()
            except Exception as e:
                logger.error(f"Error while closing windows: {e}")

        if window:
            window.events.closed += _on_closing
        webview.start(gui="qt")
