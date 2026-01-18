def has_header(self, name):
        return name in self._r.headers or name in self._new_headers