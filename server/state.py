import threading
import time
from collections import deque

MAX_READINGS = 20
TIMEOUT_FACTOR = 3

class State:
    def __init__(self):
        self._lock = threading.Lock()
        self._agents = {}

    def register(self, name, interval, addr):
        with self._lock:
            agent = self._agents.get(name)
            if agent is None:
                now = time.time()
                self._agents[name] = {
                    "addr": addr,
                    "interval": interval,
                    "connected_at": now,
                    "last_seen": now,
                    "last_message": None,
                    "last_seq": None,
                    "received": 0,
                    "lost": 0,
                    "duplicates": 0,
                    "readings": deque(maxlen=MAX_READINGS),
                }
                return True
            if agent["addr"] == addr:
                # o OK anterior deve ter se perdido: atualiza sem zerar os contadores
                agent["interval"] = interval
                agent["last_seen"] = time.time()
                return True
            return False

    def add_reading(self, name, addr, seq, metrics):
        # Devolve (status, perdidos_agora). Status: "ok", "duplicate" ou "unknown".
        with self._lock:
            agent = self._agents.get(name)
            if agent is None or agent["addr"] != addr:
                return "unknown", 0

            now = time.time()
            agent["last_seen"] = now
            last = agent["last_seq"]

            if last is None:
                lost_now = 0
            elif seq <= last:
                agent["duplicates"] += 1
                return "duplicate", 0
            else:
                lost_now = seq - last - 1

            agent["lost"] += lost_now
            agent["last_seq"] = seq
            agent["received"] += 1
            agent["readings"].append(metrics)
            agent["last_message"] = now
            return "ok", lost_now

    def remove(self, name, addr=None):
        with self._lock:
            agent = self._agents.get(name)
            if agent is None or (addr is not None and agent["addr"] != addr):
                return False
            del self._agents[name]
            return True

    def expire(self, now):
        with self._lock:
            dead = [name for name, agent in self._agents.items()
                    if now - agent["last_seen"] > TIMEOUT_FACTOR * agent["interval"]]
            for name in dead:
                del self._agents[name]
            return dead

    def snapshot(self):
        with self._lock:
            return {
                name: {
                    "interval": agent["interval"],
                    "connected_at": agent["connected_at"],
                    "last_message": agent["last_message"],
                    "addr": agent["addr"],
                    "received": agent["received"],
                    "lost": agent["lost"],
                    "duplicates": agent["duplicates"],
                    "readings": list(agent["readings"]),
                }
                for name, agent in self._agents.items()
            }