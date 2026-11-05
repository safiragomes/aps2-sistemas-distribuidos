import io
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.dashboard import render, start_dashboard  # noqa: E402
from server.state import State  # noqa: E402

NOW = 1761855370.2
METRICS = {"type": "METRICS", "name": "agent-ana", "seq": 12,
           "cpu": {"overall": 23.5, "cores": [20.1, 30.4]},
           "memory": {"total_mb": 16000, "used_mb": 8200, "free_mb": 7800}}

def fake_snapshot():
    return {"agent-ana": {"interval": 5, "connected_at": 1761855360.2,
                          "last_message": 1761855365.3, "addr": ("127.0.0.1", 51234),
                          "received": 12, "lost": 2, "duplicates": 1,
                          "readings": [METRICS]}}

def row_of(text, name):
    return next(line for line in text.splitlines() if line.startswith(name))

def test_table_with_fake_data():
    text = render(fake_snapshot(), NOW)
    row = row_of(text, "agent-ana")
    assert "127.0.0.1:51234" in row
    assert "00:00:10" in row
    assert time.strftime("%H:%M:%S", time.localtime(1761855365.3)) in row
    assert "23.5%" in row
    assert "8200/16000 MB" in row
    assert row.split()[-4:] == ["12", "2", "1", "14.3%"]

def test_header_has_all_columns():
    header = render(fake_snapshot(), NOW).splitlines()[4]
    for column in ("Agente", "Endereco", "Conectado", "Ultima msg", "CPU", "Memoria",
                   "Recebidas", "Perdidas", "Duplicadas", "% perda"):
        assert column in header

def test_uses_the_last_reading():
    snapshot = fake_snapshot()
    snapshot["agent-ana"]["readings"].append(dict(METRICS, cpu={"overall": 77.0, "cores": []}))
    assert "77.0%" in row_of(render(snapshot, NOW), "agent-ana")

def test_no_agents():
    assert "Nenhum agente registrado" in render({}, NOW)

def test_agent_without_readings():
    snapshot = {"agent-bia": {"interval": 5, "connected_at": NOW - 3, "last_message": None,
                              "addr": ("127.0.0.1", 40000), "received": 0, "lost": 0,
                              "duplicates": 0, "readings": []}}
    row = row_of(render(snapshot, NOW), "agent-bia").split()
    assert row[0:3] == ["agent-bia", "127.0.0.1:40000", "00:00:03"]
    assert row[3:6] == ["-", "-", "-"]
    assert row[6:] == ["0", "0", "0", "-"]

def test_missing_or_broken_data_does_not_fail():
    snapshot = {"agent-x": {}, "agent-y": None,
                "agent-z": {"addr": None, "readings": [None, "lixo", {"cpu": 1}],
                            "received": "12", "connected_at": "ontem"}}
    text = render(snapshot, NOW)
    for name in snapshot:
        assert name in text
    assert "Nenhum agente registrado" in render(None, NOW)

def test_render_with_real_state():
    state = State()
    state.register("agent-ana", 5, ("127.0.0.1", 51234))
    for seq in (1, 2, 5, 5):
        state.add_reading("agent-ana", ("127.0.0.1", 51234), seq, dict(METRICS, seq=seq))
    row = row_of(render(state.snapshot(), time.time()), "agent-ana")
    assert row.split()[-4:] == ["3", "2", "1", "40.0%"]

def test_start_dashboard_returns_immediately_and_redraws():
    state = State()
    output = io.StringIO()
    original, sys.stdout = sys.stdout, output
    try:
        started = time.monotonic()
        thread = start_dashboard(state, 0.1)
        elapsed = time.monotonic() - started
        time.sleep(0.25)
        state.register("agent-ana", 5, ("127.0.0.1", 51234))
        time.sleep(0.3)
    finally:
        sys.stdout = original
    assert elapsed < 0.5
    assert isinstance(thread, threading.Thread)
    assert thread.daemon is True
    assert thread.is_alive()
    screens = output.getvalue().split("\033[2J\033[H")
    assert len(screens) >= 4
    assert "Nenhum agente registrado" in screens[1]
    assert "agent-ana" in screens[-1]

if __name__ == "__main__":
    tests = [f for name, f in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print("ok  ", test.__name__)
    print("todos os testes passaram")
