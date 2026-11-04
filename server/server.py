import argparse
import logging
import socket
import time

from common.protocol import DEFAULT_PORT, Endpoint
from server.state import State

log = logging.getLogger("server")

def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)

def valid_register(message):
    return (
        isinstance(message.get("name"), str)
        and message["name"].strip() != ""
        and is_number(message.get("interval"))
        and message["interval"] > 0
    )

def valid_metrics(message):
    cpu = message.get("cpu")
    memory = message.get("memory")
    seq = message.get("seq")
    return (
        isinstance(message.get("name"), str)
        and isinstance(seq, int) and not isinstance(seq, bool) and seq >= 1
        and isinstance(cpu, dict)
        and is_number(cpu.get("overall"))
        and isinstance(cpu.get("cores"), list)
        and isinstance(memory, dict)
        and all(is_number(memory.get(key)) for key in ("total_mb", "used_mb", "free_mb"))
    )

def reply(ep, message, addr):
    try:
        ep.send(message, addr)
    except OSError:
        pass

def handle_message(ep, state, message, addr):
    kind = message.get("type")

    if kind == "REGISTER":
        if not valid_register(message):
            log.warning("REGISTER inválido de %s:%s", addr[0], addr[1])
            reply(ep, {"type": "ERROR", "reason": "invalid REGISTER"}, addr)
        elif state.register(message["name"], message["interval"], addr):
            log.info("%s registrado (%s:%s, intervalo %ss)", message["name"], addr[0], addr[1], message["interval"])
            reply(ep, {"type": "OK"}, addr)
        else:
            log.warning("registro recusado, nome em uso: %s", message["name"])
            reply(ep, {"type": "ERROR", "reason": "name already in use"}, addr)

    elif kind == "METRICS":
        if not valid_metrics(message):
            log.warning("METRICS inválido de %s:%s, ignorando", addr[0], addr[1])
            return
        status, lost = state.add_reading(message["name"], addr, message["seq"], message)
        if status == "unknown":
            reply(ep, {"type": "ERROR", "reason": "not registered"}, addr)
        elif status == "duplicate":
            log.warning("%s: seq %s duplicado ou fora de ordem", message["name"], message["seq"])
        elif lost:
            log.warning("%s: %s pacote(s) perdido(s) até o seq %s", message["name"], lost, message["seq"])

    elif kind == "BYE":
        name = message.get("name")
        if isinstance(name, str) and state.remove(name, addr):
            log.info("%s saiu (BYE)", name)

    else:
        log.warning("mensagem de tipo desconhecido de %s:%s, ignorando", addr[0], addr[1])

def parse_args():
    parser = argparse.ArgumentParser(description="Servidor de monitoramento (UDP)")
    parser.add_argument("--host", default="0.0.0.0", help="endereço em que o servidor escuta")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="porta UDP do servidor")
    parser.add_argument("--refresh", type=float, default=2, help="segundos entre as atualizações do painel")
    parser.add_argument("--no-dashboard", action="store_true", help="sem painel: os logs aparecem no terminal")
    return parser.parse_args()

def setup_logging(to_terminal):
    # o painel limpa o terminal a cada atualização, então com ele ligado os logs vão para um arquivo
    handler = logging.StreamHandler() if to_terminal else logging.FileHandler("server.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%H:%M:%S"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)

def main():
    args = parse_args()
    setup_logging(to_terminal=args.no_dashboard)
    state = State()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind((args.host, args.port))
    except OSError as e:
        print(f"Não foi possível usar {args.host}:{args.port}: {e}")
        return 1
    sock.settimeout(1.0)
    ep = Endpoint(sock)
    log.info("escutando em %s:%s (UDP)", args.host, args.port)

    if not args.no_dashboard:
        from server.dashboard import start_dashboard
        start_dashboard(state, args.refresh)

    try:
        while True:
            try:
                message, addr = ep.receive()
            except socket.timeout:
                message, addr = None, None

            for name in state.expire(time.time()):
                log.warning("%s ficou sem enviar nada, removendo (timeout)", name)

            if addr is None:
                continue
            if message is None:
                log.warning("datagrama inválido de %s:%s", addr[0], addr[1])
                continue
            handle_message(ep, state, message, addr)
    except KeyboardInterrupt:
        print("\nServidor encerrado")
    finally:
        sock.close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())