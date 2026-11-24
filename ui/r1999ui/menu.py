ITEMS = [
    ("ui", "enabled", "toggle"),
    ("ui", "locale", "choice"),
    ("eng", "mode", "choice", ("sentence", "word")),
    ("eng", "timing", "choice", ("wait", "live")),
    ("eng", "target_lang", "choice"),
    ("ui", "font_family", "choice"),
    ("ui", "size_adjust", "number", 0.6, 1.8, 0.05, "pct"),
    ("ui", "match_original", "toggle"),
    ("ui", "highlight_names", "toggle"),
    ("ui", "text_shadow", "toggle"),
    ("ui", "line_space", "choice", ("grow", "reserve")),
    ("ui", "max_lines", "number", 2, 5, 1, "lines"),
    ("ui", "offset_y", "number", -200, 200, 5, "px"),
    ("eng", "name_style", "choice", ("native", "original", "both")),
    ("eng", "word_level", "choice", ("off", "basic", "medium")),
    ("eng", "stable_ms", "number", 150, 2000, 50, "ms"),
    ("ui", "show_speaker", "toggle"),
    ("ui", "animations", "toggle"),
    ("act", "quit", "action"),
]


class MenuModel:
    def __init__(self, ui, engine_cfg, loc, languages, fonts, on_change, on_action):
        self.ui, self.engine_cfg, self.loc = ui, engine_cfg, loc
        self.on_change, self.on_action = on_change, on_action
        self.items = []
        for src, key, kind, *rest in ITEMS:
            item = {"src": src, "key": key, "type": kind}
            if kind == "choice":
                if key == "target_lang":
                    item["options"] = dict(languages)
                elif key == "locale":
                    item["options"] = dict(loc.available())
                elif key == "font_family":
                    item["options"] = {"": loc.t("opt.font_family.auto"), **{f: f for f in fonts}}
                else:
                    item["options"] = {v: loc.t("opt.%s.%s" % (key, v)) for v in rest[0]}
            elif kind == "number":
                item["min"], item["max"], item["step"], item["fmt"] = rest
            self.items.append(item)
        self.index = 0

    def value(self, item):
        if item["src"] == "ui":
            return self.ui[item["key"]]
        if item["src"] == "eng":
            return self.engine_cfg.get(item["key"])
        return None

    def _format(self, item, value):
        kind = item["fmt"]
        if kind == "pct":
            return "%d%%" % round(value * 100)
        if kind == "lines":
            return self.loc.t("fmt.lines", n=value)
        if kind == "px":
            return self.loc.t("fmt.px", n="%+d" % value)
        return self.loc.t("fmt.ms", n=value)

    def rows(self):
        rows = []
        for i, item in enumerate(self.items):
            value = self.value(item)
            row = {
                "label": self.loc.t("menu." + item["key"]),
                "selected": i == self.index,
                "kind": item["type"],
                "ratio": None,
                "value": "",
            }
            if item["type"] == "toggle":
                row["on"] = bool(value)
                row["value"] = self.loc.t("val.on" if value else "val.off")
            elif item["type"] == "choice":
                row["value"] = item["options"].get(value, str(value))
            elif item["type"] == "number":
                row["value"] = self._format(item, value)
                row["ratio"] = (value - item["min"]) / (item["max"] - item["min"])
            rows.append(row)
        return rows

    def handle(self, key):
        if key == "up":
            self.index = (self.index - 1) % len(self.items)
        elif key == "down":
            self.index = (self.index + 1) % len(self.items)
        elif key in ("left", "right"):
            self._adjust(1 if key == "right" else -1)
        elif key in ("pageup", "pagedown"):
            self._adjust(10 if key == "pagedown" else -10)
        elif key == "enter":
            item = self.items[self.index]
            if item["type"] == "action":
                self.on_action(item["key"])
            else:
                self._adjust(1)

    def _adjust(self, steps):
        item = self.items[self.index]
        value = self.value(item)
        if item["type"] == "toggle":
            new = not value
        elif item["type"] == "choice":
            keys = list(item["options"])
            current = keys.index(value) if value in keys else 0
            new = keys[(current + steps) % len(keys)]
        elif item["type"] == "number":
            step = item["step"]
            new = min(item["max"], max(item["min"], value + steps * step))
            new = round(new / step) * step
            new = int(new) if isinstance(step, int) else round(new, 2)
        else:
            return
        if new != value:
            self.on_change(item["src"], item["key"], new)
