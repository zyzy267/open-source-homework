def get_header(self, name, default=None):
        return self._r.headers.get(name, self._new_headers.get(name, default))