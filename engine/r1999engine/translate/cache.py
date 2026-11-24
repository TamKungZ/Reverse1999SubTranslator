from ..storage import read_json, write_json

FLUSH_EVERY = 15


class Cache:
    """A string map that is saved to disk when a path is given and kept in memory otherwise."""

    def __init__(self, path=None):
        self.path = path
        self.data = read_json(path, {}) if path else {}
        self.dirty = 0

    def get(self, key):
        return self.data.get(key)

    def put(self, key, value):
        self.data[key] = value
        self.dirty += 1
        if self.dirty >= FLUSH_EVERY:
            self.flush()

    def flush(self):
        if not (self.dirty and self.path):
            return
        if write_json(self.path, self.data):
            self.dirty = 0
