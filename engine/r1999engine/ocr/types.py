from dataclasses import dataclass

import numpy as np


@dataclass
class Frame:
    img: np.ndarray
    client_w: int
    client_h: int
    region: tuple


@dataclass
class DialogRead:
    text: str = ""
    speaker: str = ""
    speaker_known: bool = False
    top_y: float = 0.0
    name_ink: bool = False
    style: dict = None
    box: tuple = None
