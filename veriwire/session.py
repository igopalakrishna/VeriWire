import time


class MemorySessions:
    def __init__(self, ttl: int = 3600):
        self.ttl = ttl
        self._sessions = {}

    def get(self, sid: str):
        record = self._sessions.get(sid)
        now = time.time()
        if not record or record["exp"] < now:
            record = {"data": {}, "exp": now + self.ttl}
            self._sessions[sid] = record
        return record["data"]

    def set(self, sid: str, data: dict):
        self._sessions[sid] = {"data": data, "exp": time.time() + self.ttl}

    def delete(self, sid: str):
        self._sessions.pop(sid, None)


SESSIONS = MemorySessions()


