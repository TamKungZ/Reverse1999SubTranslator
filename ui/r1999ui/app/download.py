from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout

POLL_MS = 500


def run_download_dialog(client, loc):
    """Asks to download the translation model and shows progress. True once the model is ready."""
    dialog = QDialog()
    dialog.setWindowTitle(loc.t("app.title"))
    dialog.setMinimumWidth(460)
    label = QLabel(loc.t("setup.text"))
    bar = QProgressBar()
    bar.setRange(0, 100)
    bar.hide()
    start = QPushButton(loc.t("setup.download"))
    quit_ = QPushButton(loc.t("setup.quit"))
    row = QHBoxLayout()
    row.addStretch(1)
    row.addWidget(start)
    row.addWidget(quit_)
    layout = QVBoxLayout(dialog)
    layout.addWidget(label)
    layout.addWidget(bar)
    layout.addLayout(row)
    poll = QTimer(dialog)

    def tick():
        try:
            info = client.info()
        except OSError:
            return
        dl = info["download"]
        if info["state"] == "ready":
            poll.stop()
            dialog.accept()
        elif info["state"] == "downloading":
            total = max(1, dl["total"])
            bar.setValue(int(dl["done"] * 100 / total))
            label.setText(loc.t("setup.downloading", file=dl["file"], done=dl["done"] >> 20, total=total >> 20))
        elif info["state"] == "loading":
            label.setText(loc.t("setup.loading"))
        elif info["state"] in ("model_missing", "error") and dl["state"] in ("error", "cancelled"):
            label.setText(loc.t("setup.failed", error=dl["error"] or info["error"]))
            start.setEnabled(True)
            start.setText(loc.t("setup.retry"))
            poll.stop()

    def begin():
        start.setEnabled(False)
        bar.show()
        client.download_model()
        poll.start(POLL_MS)

    start.clicked.connect(begin)
    quit_.clicked.connect(dialog.reject)
    poll.timeout.connect(tick)
    return bool(dialog.exec())
