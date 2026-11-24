import dataclasses
import time
from pathlib import Path

import numpy as np
from PySide6.QtCore import QStandardPaths
from PySide6.QtGui import QImage, QPainter

from .. import render

WHOLE_WINDOW = (0.0, 0.0, 1.0, 1.0)


def screenshot_dir():
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.PicturesLocation) or str(Path.home())
    return Path(base) / "R1999Translator"


def take(grabber, game, state, folder=None):
    """Saves the game window with the translation drawn on it and returns the file. The overlay itself is hidden from screen capture,
    so other tools never see it."""
    shot = grabber.grab(game, WHOLE_WINDOW)
    if shot is None:
        return None
    h, w = shot.shape[:2]
    rgb = np.ascontiguousarray(shot[:, :, ::-1])
    image = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888).copy()
    painter = QPainter(image)
    render.paint(painter, w, h, dataclasses.replace(state, menu_rows=None, toast=""))
    painter.end()
    folder = Path(folder) if folder else screenshot_dir()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / time.strftime("screenshot-%Y%m%d-%H%M%S.png")
    return path if image.save(str(path)) else None
