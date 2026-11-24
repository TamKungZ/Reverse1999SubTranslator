import json
import urllib.request


class EngineClient:
    def __init__(self, port):
        self.base = "http://127.0.0.1:%d" % port

    def _call(self, path, data=None, headers=None, timeout=5):
        req = urllib.request.Request(
            self.base + path, data=data, headers=headers or {}, method="POST" if data is not None else "GET"
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.load(resp)

    def info(self):
        return self._call("/info", timeout=2)

    def frame(self, img_bgr, client_w, client_h, region):
        headers = {
            "Content-Type": "application/octet-stream",
            "X-Format": "bgr",
            "X-Width": str(img_bgr.shape[1]),
            "X-Height": str(img_bgr.shape[0]),
            "X-Client-W": str(client_w),
            "X-Client-H": str(client_h),
            "X-Region": ",".join("%.4f" % v for v in region),
        }
        return self._call("/frame", img_bgr.tobytes(), headers, timeout=10)

    def set_config(self, values):
        return self._call("/config", json.dumps(values).encode("utf-8"), {"Content-Type": "application/json"})

    def reset(self):
        return self._call("/reset", b"{}")

    def download_model(self):
        return self._call("/model/download", b"{}")

    def shutdown(self):
        try:
            return self._call("/shutdown", b"{}", timeout=2)
        except OSError:
            return None
