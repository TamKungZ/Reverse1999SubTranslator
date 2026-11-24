import cv2
import numpy as np

from ..ocr import Frame

DEFAULT_REGION = "0.08,0.78,0.90,1.0"


def decode_frame(body, headers):
    """Builds a Frame from a /frame request: raw BGR bytes or a PNG, plus the client size and capture region."""
    w, h = int(headers["X-Width"]), int(headers["X-Height"])
    if headers.get("X-Format", "bgr") == "png":
        img = cv2.imdecode(np.frombuffer(body, np.uint8), cv2.IMREAD_COLOR)
    else:
        img = np.frombuffer(body, np.uint8).reshape(h, w, 3)
    region = tuple(float(v) for v in headers.get("X-Region", DEFAULT_REGION).split(","))
    return Frame(img, int(headers["X-Client-W"]), int(headers["X-Client-H"]), region)
