
import argparse
import logging
import socket
import threading
import time

from agent.collector import collect_metrics
from common.protocol import DEFAULT_PORT, Endpoint


# Configuração dos logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)


def positive_int(value):
    """Verifica se o argumento é um número inteiro positivo."""
    try:
        number = int(value)
        if number <= 0:
            raise ValueError
        return number
    except ValueError:
        raise argparse.ArgumentTypeError(
            "O valor deve ser um inteiro positivo."
        )


def receive_server_response(endpoint, sock, server_addr, timeout):
    """
    Aguarda uma resposta do servidor.

    Ignora mensagens inválidas e respostas de outros endereços.
    """
    deadline = time.monotonic() + timeout

    while True:
        remaining = deadline - time.monotonic()

        if remaining <= 0:
            return None

        sock.settimeout(remaining)

        try:
            received = endpoint.receive()
        except socket.timeout:
            return None
        except OSError as error:
            logging.warning("Erro ao receber resposta: %s", error)
            return None

        if received is None:
            continue

        message, addr = received

        if addr is None or addr[:2] != server_addr:
            continue

        if message is None:
            continue

        return message


def register_agent(endpoint, sock, server_addr, name, interval):
    """
    Registra o agente no servidor.

    Realiza até três tentativas, aguardando dois segundos
    por uma resposta em cada tentativa.
    """
    register_message = {
        "type": "REGISTER",
        "name": name,
        "interval": interval
    }

    for attempt in range(1, 4):
        try:
            endpoint.send(register_message, server_addr)

            logging.info(
                "%s enviou REGISTER (tentativa %d)",
                name,
                attempt
            )

            response = receive_server_response(
                endpoint,
                sock,
                server_addr,
                timeout=2
            )

            if response is None:
                logging.warning(
                    "%s não recebeu resposta do servidor.",
                    name
                )
                continue

            if response.get("type") == "OK":
                logging.info("%s registrado com sucesso!", name)
                return True

            if response.get("type") == "ERROR":
                logging.error(
                    "%s recebeu ERROR: %s",
                    name,
                    response.get("reason", "motivo desconhecido")
                )
                return False

        except (OSError, ValueError) as error:
            logging.error(
                "Erro ao registrar %s: %s",
                name,
                error
            )
            return False

    logging.error(
        "%s desistiu após três tentativas de registro.",
        name
    )

    return False


def create_metrics(name, seq):
    """
    Coleta as métricas da máquina e monta a mensagem METRICS.
    """
    collected = collect_metrics()

    cpu_data = collected["cpu"]
    memory_data = collected["memory"]

    return {
        "type": "METRICS",
        "name": name,
        "seq": seq,
        "cpu": {
            "overall": round(float(cpu_data["overall"]), 1),
            "cores": [
                round(float(core), 1)
                for core in cpu_data["cores"]
            ]
        },
        "memory": {
            "total_mb": memory_data["total_mb"],
            "used_mb": memory_data["used_mb"],
            "free_mb": memory_data["free_mb"]
        }
    }


def run_agent(agent_number, duration, interval, server_addr, stop_event):
    """
    Executa um agente simulado em uma thread.

    Os agentes 3, 5, 7, 8 e 9 possuem comportamentos especiais.
    """
    name = f"agent-{agent_number}"

    # Cada agente cria seu próprio socket UDP.
    sock = socket.socket(
        socket.AF_INET,
        socket.SOCK_DGRAM
    )

    endpoint = Endpoint(sock)
    registered = False

    try:
        # Primeira etapa: registrar o agente.
        registered = register_agent(
            endpoint,
            sock,
            server_addr,
            name,
            interval
        )

        if not registered:
            return

        # AGENTE 8: envia REGISTER uma segunda vez.
        # O mesmo socket é utilizado nas duas tentativas.
        if agent_number == 8:
            logging.info(
                "%s está enviando REGISTER novamente.",
                name
            )

            if not register_agent(
                endpoint,
                sock,
                server_addr,
                name,
                interval
            ):
                return

        # Não precisamos aguardar respostas durante os envios
        # normais de METRICS.
        sock.settimeout(None)

        start_time = time.monotonic()
        deadline = start_time + duration

        seq = 0

        while not stop_event.is_set() and time.monotonic() < deadline:

            seq += 1

            # Coleta CPU e memória.
            message = create_metrics(name, seq)

            # AGENTE 5: simula perda de aproximadamente 30%.
            # O seq continua aumentando mesmo quando não há envio.
            if agent_number == 5 and seq % 10 in (3, 6, 9):

                logging.warning(
                    "%s simulou perda da mensagem seq=%d",
                    name,
                    seq
                )

            else:

                endpoint.send(message, server_addr)

                logging.info(
                    "%s enviou METRICS seq=%d",
                    name,
                    seq
                )

                # AGENTE 7: repete a mesma mensagem.
                # O número de sequência não é incrementado.
                if agent_number == 7 and seq % 4 == 0:

                    endpoint.send(message, server_addr)

                    logging.warning(
                        "%s duplicou a mensagem seq=%d",
                        name,
                        seq
                    )

            # AGENTE 9: envia um datagrama que não é JSON válido.
            # O envio direto pelo socket é intencional neste caso.
            if agent_number == 9 and seq % 5 == 0:

                sock.sendto(
                    b"{mensagem-invalida",
                    server_addr
                )

                logging.warning(
                    "%s enviou uma mensagem invalida",
                    name
                )

            # AGENTE 3: envia apenas duas métricas e depois
            # para definitivamente, sem enviar BYE.
            if agent_number == 3 and seq >= 2:

                logging.warning(
                    "%s parou de enviar mensagens sem BYE.",
                    name
                )

                return

            # Aguarda o próximo intervalo.
            if stop_event.wait(interval):
                break

    except (OSError, ValueError, KeyError) as error:

        logging.error(
            "Erro no agente %s: %s",
            name,
            error
        )

    except Exception:

        logging.exception(
            "Erro inesperado no agente %s.",
            name
        )

    finally:

        # Todos os agentes normais encerram com BYE.
        # O agente 3 não envia BYE, pois testa o timeout.
        if registered and agent_number != 3:

            try:
                endpoint.send(
                    {
                        "type": "BYE",
                        "name": name
                    },
                    server_addr
                )

                logging.info(
                    "%s enviou BYE.",
                    name
                )

            except OSError as error:
                logging.warning(
                    "Não foi possível enviar BYE de %s: %s",
                    name,
                    error
                )

        endpoint.close()


def main():
    """Lê os argumentos e inicia os agentes simulados."""

    parser = argparse.ArgumentParser(
        description="Simulador de agentes UDP."
    )

    parser.add_argument(
        "--agents",
        type=positive_int,
        default=10,
        help="Quantidade de agentes simulados."
    )

    parser.add_argument(
        "--duration",
        type=positive_int,
        default=60,
        help="Duração da simulação em segundos."
    )

    parser.add_argument(
        "--interval",
        type=positive_int,
        default=5,
        help="Intervalo entre os envios de métricas."
    )

    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Endereço do servidor."
    )

    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help="Porta UDP do servidor."
    )

    args = parser.parse_args()

    if not 1 <= args.port <= 65535:
        parser.error("A porta deve estar entre 1 e 65535.")

    try:
        server_host = socket.gethostbyname(args.host)
    except socket.gaierror:
        parser.error("Não foi possível resolver o endereço do servidor.")

    server_addr = (server_host, args.port)

    logging.info("Iniciando simulador UDP.")
    logging.info("Servidor: %s:%d", *server_addr)
    logging.info("Quantidade de agentes: %d", args.agents)
    logging.info("Duração: %d segundos", args.duration)
    logging.info("Intervalo: %d segundos", args.interval)

    if args.agents < 9:
        logging.warning(
            "Para testar todos os agentes especiais, utilize pelo menos 10 agentes."
        )

    stop_event = threading.Event()
    threads = []

    # Cria uma thread para cada agente.
    for number in range(1, args.agents + 1):

        thread = threading.Thread(
            target=run_agent,
            args=(
                number,
                args.duration,
                args.interval,
                server_addr,
                stop_event
            ),
            name=f"agent-{number}"
        )

        threads.append(thread)
        thread.start()

    try:
        # Aguarda a conclusão de todos os agentes.
        for thread in threads:
            thread.join()

    except KeyboardInterrupt:

        logging.warning(
            "Interrupção solicitada. Encerrando os agentes..."
        )

        stop_event.set()

        for thread in threads:
            thread.join()

    logging.info("Simulação finalizada.")


if __name__ == "__main__":
    main()
