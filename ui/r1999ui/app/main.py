import os
import sys

from .. import winutil
from ..settings import UiSettings


def main():
    if not winutil.acquire_single_instance():
        return
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "0")
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "0")
    winutil.set_dpi_aware()
    # Qt must be imported after the process is DPI aware, so these imports stay inside main
    from PySide6.QtWidgets import QApplication

    from .. import render
    from .controller import Controller

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    render.load_fonts()
    controller = Controller(app, UiSettings())
    controller.start()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
