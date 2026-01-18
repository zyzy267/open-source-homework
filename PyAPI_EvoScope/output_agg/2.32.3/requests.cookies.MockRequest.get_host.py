def get_host(self):
        return urlparse(self._r.url).netloc