def next(self):
        """Returns a PreparedRequest for the next request in a redirect chain, if there is one."""
        return self._next