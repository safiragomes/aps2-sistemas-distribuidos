import os
import socket
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.protocol import MAX_DATAGRAM, Endpoint  # noqa: E402

def make_pair():
    socks = []
    for _ in range(2):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind(("127.0.0.1", 0))
        s.settimeout(2)
        socks.append(s)
    a, b = socks
    return Endpoint(a), Endpoint(b), a.getsockname(), b.getsockname()


def test_round_trip():
    a, b, addr_a, addr_b = make_pair()
    a.send({"type": "OK"}, addr_b)
    message, addr = b.receive()
    assert message == {"type": "OK"}
    assert addr == addr_a


def test_accents():
    a, b, _, addr_b = make_pair()
    a.send({"reason": "nome já em uso"}, addr_b)
    message, _ = b.receive()
    assert message == {"reason": "nome já em uso"}


def test_text_that_is_not_json():
    a, b, _, addr_b = make_pair()
    a.sock.sendto(b"lixo", addr_b)
    message, _ = b.receive()
    assert message is None


def test_json_that_is_not_an_object():
    a, b, _, addr_b = make_pair()
    a.sock.sendto(b"[1, 2, 3]", addr_b)
    message, _ = b.receive()
    assert message is None


def test_bytes_that_are_not_utf8():
    a, b, _, addr_b = make_pair()
    a.sock.sendto(b"\xff\xfe\xfd", addr_b)
    message, _ = b.receive()
    assert message is None


def test_message_too_big():
    a, _, _, addr_b = make_pair()
    try:
        a.send({"data": "x" * (MAX_DATAGRAM + 1)}, addr_b)
    except ValueError:
        return
    raise AssertionError("era para levantar ValueError")


def test_timeout_when_nothing_arrives():
    _, b, _, _ = make_pair()
    b.sock.settimeout(0.2)
    try:
        b.receive()
    except socket.timeout:
        return
    raise AssertionError("era para levantar socket.timeout")


if __name__ == "__main__":
    tests = [f for name, f in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print("ok  ", test.__name__)
    print("todos os testes passaram")