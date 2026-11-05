"""Painel de monitoramento no terminal.

Contrato:
    render(snapshot, now) -> str
    start_dashboard(state, refresh) -> threading.Thread

O snapshot segue o formato de State.snapshot():
    {nome: {"interval": ..., "connected_at": ..., "last_message": ...,
            "addr": (ip, porta), "received": ..., "lost": ...,
            "duplicates": ..., "readings": [...]}}
Cada leitura e uma mensagem METRICS, conforme docs/protocol.md.
"""

import sys
import threading
import time

EMPTY = "-"
COLUMNS = ("Agente", "Endereco", "Conectado", "Ultima msg", "CPU",
           "Memoria", "Recebidas", "Perdidas", "Duplicadas", "% perda")


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _last_reading(readings):
    """Obtem a ultima mensagem METRICS valida de uma sequencia de leituras."""
    if not isinstance(readings, (list, tuple)):
        return None
    for reading in reversed(readings):
        if isinstance(reading, dict) and isinstance(reading.get("cpu"), dict) \
                and isinstance(reading.get("memory"), dict):
            return reading
    return None


def _address(addr):
    if isinstance(addr, (list, tuple)) and len(addr) >= 2:
        return f"{addr[0]}:{addr[1]}"
    return EMPTY


def _duration(start, now):
    if not _is_number(start) or not _is_number(now):
        return EMPTY
    seconds = max(0, int(now - start))
    hours, rest = divmod(seconds, 3600)
    minutes, seconds = divmod(rest, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _clock(timestamp):
    if not _is_number(timestamp):
        return EMPTY
    return time.strftime("%H:%M:%S", time.localtime(timestamp))


def _cpu(reading):
    overall = reading.get("cpu", {}).get("overall") if reading else None
    return f"{overall:.1f}%" if _is_number(overall) else EMPTY


def _memory(reading):
    memory = reading.get("memory", {}) if reading else {}
    used, total = memory.get("used_mb"), memory.get("total_mb")
    if _is_number(used) and _is_number(total) and total > 0:
        return f"{used:.0f}/{total:.0f} MB ({used / total * 100:.0f}%)"
    return EMPTY


def _counter(value):
    return str(value) if _is_number(value) else EMPTY


def _loss(received, lost):
    # percentual de perda sobre tudo que o agente enviou (recebidas + perdidas)
    if not _is_number(received) or not _is_number(lost) or received + lost <= 0:
        return EMPTY
    return f"{lost / (received + lost) * 100:.1f}%"


def _row(name, data, now):
    if not isinstance(data, dict):
        return [str(name)] + [EMPTY] * (len(COLUMNS) - 1)

    reading = _last_reading(data.get("readings"))
    received, lost = data.get("received"), data.get("lost")
    return [
        str(name),
        _address(data.get("addr")),
        _duration(data.get("connected_at"), now),
        _clock(data.get("last_message")),
        _cpu(reading),
        _memory(reading),
        _counter(received),
        _counter(lost),
        _counter(data.get("duplicates")),
        _loss(received, lost),
    ]


def render(snapshot, now):
    """Monta o texto do painel a partir de uma copia do estado do servidor."""
    if not isinstance(snapshot, dict):
        snapshot = {}

    header = f"MONITOR DE DESEMPENHO (UDP) - {_clock(now)}"
    if not snapshot:
        rule = "=" * max(len(header), 40)
        return "\n".join([rule, header, rule, "Nenhum agente registrado", rule])

    rows = [_row(name, snapshot[name], now) for name in sorted(snapshot, key=str)]
    widths = [max(len(COLUMNS[i]), *(len(row[i]) for row in rows))
              for i in range(len(COLUMNS))]

    def line(cells):
        return "  ".join(cell.ljust(width) for cell, width in zip(cells, widths)).rstrip()

    table_width = sum(widths) + 2 * (len(widths) - 1)
    rule = "=" * max(table_width, len(header))
    lines = [rule, header, f"Agentes registrados: {len(rows)}", rule,
             line(COLUMNS), "-" * len(rule)]
    lines.extend(line(row) for row in rows)
    lines.append(rule)
    return "\n".join(lines)


def start_dashboard(state, refresh=2):
    """Inicia o painel numa thread daemon e retorna sem bloquear o servidor.

    state deve fornecer snapshot(). A thread termina junto com o processo
    principal.
    """
    if refresh <= 0:
        raise ValueError("refresh deve ser maior que zero")
    if not callable(getattr(state, "snapshot", None)):
        raise TypeError("state deve fornecer o metodo snapshot()")

    def update():
        while True:
            try:
                content = render(state.snapshot(), time.time())
            except Exception as exc:
                content = f"Falha ao atualizar painel: {exc}"

            # Sequencia ANSI para limpar a tela e voltar o cursor ao inicio.
            sys.stdout.write("\033[2J\033[H" + content + "\n")
            sys.stdout.flush()
            time.sleep(refresh)

    thread = threading.Thread(target=update, name="dashboard", daemon=True)
    thread.start()
    return thread
