import numpy as np

from .lines import MIN_LINE_W, line_cuts


class RowReader:
    def __init__(self):
        from rapidocr_onnxruntime import RapidOCR

        self.eng = RapidOCR()

    def recognize(self, crop):
        res, _ = self.eng.text_recognizer([np.ascontiguousarray(crop)])
        return res[0][0], float(res[0][1])

    def rows(self, img):
        result, _ = self.eng(img, text_score=0.2)
        if not result:
            return []
        boxes = []
        for box, text, score in result:
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            boxes.append([min(xs), min(ys), max(xs), max(ys), text, float(score)])
        boxes.sort(key=lambda b: (b[1] + b[3]) / 2)
        groups = []
        for b in boxes:
            cy = (b[1] + b[3]) / 2
            h = b[3] - b[1]
            if groups and abs(cy - groups[-1]["cy"]) < 0.6 * min(h, groups[-1]["h"]):
                groups[-1]["boxes"].append(b)
            else:
                groups.append({"cy": cy, "h": h, "boxes": [b]})
        rows = []
        for g in groups:
            bs = g["boxes"]
            x0 = int(max(0, min(b[0] for b in bs) - 3))
            y0 = int(max(0, min(b[1] for b in bs) - 3))
            x1 = int(min(img.shape[1], max(b[2] for b in bs) + 3))
            y1 = int(min(img.shape[0], max(b[3] for b in bs) + 3))
            if len(bs) > 1:
                text, score = self.recognize(img[y0:y1, x0:x1])
            else:
                text, score = bs[0][4], bs[0][5]
            rows.append((text, score, x0, y0, x1, y1))
        return rows

    def rows_by_line(self, crop, mask):
        edges = [0] + line_cuts(mask) + [crop.shape[0]]
        rows = []
        for top, bottom in zip(edges, edges[1:]):
            cols = np.where(mask[top:bottom].any(axis=0))[0]
            if not len(cols):
                continue
            left = max(0, int(cols.min()) - 24)
            right = min(crop.shape[1], max(int(cols.max()) + 25, left + MIN_LINE_W))  # the detector misses short, narrow crops
            for t, s, a, b, c, d in self.rows(crop[top:bottom, left:right]):
                rows.append((t, s, a + left, b + top, c + left, d + top))
        return rows
