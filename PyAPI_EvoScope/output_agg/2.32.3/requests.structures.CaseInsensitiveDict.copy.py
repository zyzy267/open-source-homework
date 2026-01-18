def copy(self):
        return CaseInsensitiveDict(self._store.values())