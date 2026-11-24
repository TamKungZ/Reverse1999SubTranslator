import numpy as np

from .lines import MIN_LINE_W, line_cuts, split_spans

DET_MAX_SIDE = 960


class RowReader:
    def __init__(self):
        from rapidocr_onnxruntime import RapidOCR

        self.eng = RapidOCR()
        # the default grows every small crop to 736 pixels before detection, which costs about a second
        resize = self.eng.text_detector.preprocess_op[0]
        resize.limit_type, resize.limit_side_len = "max", DET_MAX_SIDE

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
            line = self._read_line(crop[top:bottom], mask[top:bottom])
            if line:
                t, s, a, b, c, d = line
                rows.append((t, s, a, b + top, c, d + top))
        return rows

    def _read_line(self, line, mask):
        spans = split_spans(mask)
        parts = []
        for i, (lo, hi) in enumerate(spans):
            first, last = i == 0, i == len(spans) - 1
            left = max(0, lo - (24 if first else 4))
            right = min(line.shape[1], hi + (25 if last else 4))
            if len(spans) == 1:
                right = min(line.shape[1], max(hi + 25, left + MIN_LINE_W))  # the detector misses short, narrow crops
            for t, s, a, b, c, d in self.rows(line[:, left:right]):
                parts.append((t, s, a + left, b, c + left, d))
        if not parts:
            return None
        return (
            " ".join(p[0] for p in parts), min(p[1] for p in parts),
            min(p[2] for p in parts), min(p[3] for p in parts), max(p[4] for p in parts), max(p[5] for p in parts),
        )
