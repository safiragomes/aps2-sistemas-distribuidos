# Copiei da aps passada, precisamos ajustar.
"""Painel de monitoramento no terminal (Pessoa 5).

Contrato da equipe:
    render(snapshot) -> str
    start_dashboard(state, refresh) -> threading.Thread

O snapshot deve ser um dicionario no formato:
    {nome: {"interval": ..., "connected_at": ...,
            "last_message": ..., "readings": [...]}}
Cada leitura e uma mensagem METRICS, conforme docs/protocol.md.
"""

import sys
import threading
import time


def _number(value, suffix=""):
    """Formata valores numericos sem presumir que ja existe uma leitura."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{value:.1f}{suffix}"
    return "--"


def _last_reading(readings):
    """Obtém a ultima mensagem METRICS valida de uma sequencia de leituras."""
    for reading in reversed(list(readings)):
        if isinstance(reading, dict):
            if reading.get("type") == "METRICS" or ("cpu" in reading and "memory" in reading):
                return reading
    return None


def render(snapshot):
    """Monta o texto do painel a partir de uma copia do estado do servidor."""
    if not isinstance(snapshot, dict):
        raise TypeError("snapshot deve ser um dicionario")

    lines = [
        "=" * 65,
        "             MONITORAMENTO DISTRIBUIDO - EQUIPE 06",
        "=" * 65,
        f"Agentes conectados: {len(snapshot)}",
    ]

    if not snapshot:
        lines.append("Nenhum agente conectado. Aguardando conexoes TCP...")
        lines.append("=" * 65)
        return "\n".join(lines)

    for name, data in sorted(snapshot.items()):
        if not isinstance(data, dict):
            lines.append(f"\nAgente: {name} | Estado indisponivel")
            continue

        lines.append("-" * 65)
        lines.append(f"Agente: {name}")
        lines.append(f"Intervalo configurado: {data.get('interval', '--')} s")
        lines.append(f"Conectado desde: {data.get('connected_at') or '--'}")
        lines.append(f"Ultima mensagem: {data.get('last_message') or '--'}")

        reading = _last_reading(data.get("readings") or [])
        if reading is None:
            lines.append("Aguardando primeira leitura de CPU e memoria...")
            continue

        cpu = reading.get("cpu") or {}
        memory = reading.get("memory") or {}
        if not isinstance(cpu, dict):
            cpu = {}
        if not isinstance(memory, dict):
            memory = {}

        lines.append(f"CPU geral: {_number(cpu.get('overall'), '%')}")
        cores = cpu.get("cores")
        if isinstance(cores, (list, tuple)) and cores:
            for index, value in enumerate(cores, start=1):
                lines.append(f"  Nucleo {index}: {_number(value, '%')}")
        else:
            lines.append("  Nucleos: dados indisponiveis")

        lines.append(f"Memoria total: {_number(memory.get('total_mb'), ' MB')}")
        lines.append(f"Memoria usada: {_number(memory.get('used_mb'), ' MB')}")
        lines.append(f"Memoria livre: {_number(memory.get('free_mb'), ' MB')}")

    lines.append("=" * 65)
    return "\n".join(lines)


def start_dashboard(state, refresh=2):
    """Inicia o painel numa thread daemon sem bloquear o servidor TCP.

    state deve fornecer snapshot(). Chame esta funcao uma unica vez durante
    a inicializacao do servidor; a thread termina com o processo principal.
    """
    if refresh <= 0:
        raise ValueError("refresh deve ser maior que zero")
    if not callable(getattr(state, "snapshot", None)):
        raise TypeError("state deve fornecer o metodo snapshot()")

    def update():
        while True:
            try:
                snapshot = state.snapshot()
                content = render(snapshot)
            except Exception as exc:
                content = f"Falha ao atualizar painel: {exc}"

            # Sequencia ANSI para limpar tela e reposicionar cursor.
            # Em terminais sem ANSI, a visualizacao pode variar.
            sys.stdout.write("\033[2J\033[H" + content + "\n")
            sys.stdout.flush()
            time.sleep(refresh)

    thread = threading.Thread(target=update, name="dashboard", daemon=True)
    thread.start()
    return thread