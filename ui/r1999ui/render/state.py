from dataclasses import dataclass, field


@dataclass
class RenderState:
    view: dict = None
    reveal: float = 0.0
    ui: dict = field(default_factory=dict)
    menu_rows: list = None
    menu_reveal: float = 0.0
    sel_pos: float = 0.0
    row_on: list = field(default_factory=list)
    row_ratio: list = field(default_factory=list)
    toast: str = ""
    toast_alpha: float = 0.0
    hotkeys: dict = field(default_factory=dict)
    t: object = staticmethod(lambda key, **kw: key)
