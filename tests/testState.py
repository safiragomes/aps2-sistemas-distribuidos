import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.state import MAX_READINGS, State  # noqa: E402

A = ("127.0.0.1", 50001)
B = ("127.0.0.1", 50002)
METRICS = {"type": "METRICS"}

def test_register_new_name():
    state = State()
    assert state.register("ana", 5, A) is True
    assert "ana" in state.snapshot()

def test_same_name_other_address_is_refused():
    state = State()
    state.register("ana", 5, A)
    assert state.register("ana", 5, B) is False

def test_register_again_from_same_address_keeps_counters():
    state = State()
    state.register("ana", 5, A)
    state.add_reading("ana", A, 1, METRICS)
    state.add_reading("ana", A, 2, METRICS)
    assert state.register("ana", 5, A) is True
    assert state.snapshot()["ana"]["received"] == 2

def test_seq_gap_counts_lost():
    state = State()
    state.register("ana", 5, A)
    assert state.add_reading("ana", A, 1, METRICS) == ("ok", 0)
    assert state.add_reading("ana", A, 2, METRICS) == ("ok", 0)
    assert state.add_reading("ana", A, 5, METRICS) == ("ok", 2)
    assert state.snapshot()["ana"]["lost"] == 2

def test_repeated_seq_is_a_duplicate():
    state = State()
    state.register("ana", 5, A)
    for seq in (1, 2, 5):
        state.add_reading("ana", A, seq, METRICS)
    assert state.add_reading("ana", A, 5, METRICS) == ("duplicate", 0)
    assert state.add_reading("ana", A, 3, METRICS) == ("duplicate", 0)
    snap = state.snapshot()["ana"]
    assert snap["duplicates"] == 2
    assert snap["received"] == 3

def test_first_seq_is_only_a_reference():
    state = State()
    state.register("ana", 5, A)
    assert state.add_reading("ana", A, 40, METRICS) == ("ok", 0)
    assert state.snapshot()["ana"]["lost"] == 0

def test_unknown_name_or_address():
    state = State()
    state.register("ana", 5, A)
    assert state.add_reading("bia", A, 1, METRICS)[0] == "unknown"
    assert state.add_reading("ana", B, 1, METRICS)[0] == "unknown"

def test_keeps_only_the_last_readings():
    state = State()
    state.register("ana", 5, A)
    for seq in range(1, MAX_READINGS + 11):
        state.add_reading("ana", A, seq, {"seq": seq})
    readings = state.snapshot()["ana"]["readings"]
    assert len(readings) == MAX_READINGS
    assert readings[-1] == {"seq": MAX_READINGS + 10}

def test_remove():
    state = State()
    state.register("ana", 5, A)
    assert state.remove("ana", B) is False
    assert state.remove("ana", A) is True
    assert state.snapshot() == {}

def test_expire_removes_only_who_passed_the_timeout():
    state = State()
    state.register("ana", 1, A)
    state.register("bia", 100, B)
    assert state.expire(time.time()) == []
    assert state.expire(time.time() + 4) == ["ana"]
    assert list(state.snapshot()) == ["bia"]

def test_many_threads_at_the_same_time():
    state = State()
    for i in range(20):
        state.register(f"a{i}", 5, ("127.0.0.1", 6000 + i))

    def worker(i):
        for seq in range(1, 501):
            state.add_reading(f"a{i}", ("127.0.0.1", 6000 + i), seq, METRICS)
            state.snapshot()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    snap = state.snapshot()
    assert all(v["received"] == 500 and v["lost"] == 0 and v["duplicates"] == 0 for v in snap.values())
    assert all(len(v["readings"]) == MAX_READINGS for v in snap.values())

if __name__ == "__main__":
    tests = [f for name, f in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print("ok  ", test.__name__)
    print("todos os testes passaram")