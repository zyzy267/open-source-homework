def close(self):
        """Closes all adapters and as such the session"""
        for v in self.adapters.values():
            v.close()