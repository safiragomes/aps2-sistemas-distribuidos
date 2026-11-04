import json
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def get_free_port():
    """Encontra uma porta UDP disponivel para o teste."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def create_client():
    """Cria um socket UDP para representar um agente."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    return sock


def send_json(sock, server_addr, message):
    """Envia uma mensagem JSON por UDP."""
    data = json.dumps(message).encode("utf-8")

    if len(data) > 1200:
        raise ValueError("Mensagem maior que 1200 bytes.")

    sock.sendto(data, server_addr)


def receive_json(sock, server_addr, timeout=2):
    """Recebe uma mensagem JSON enviada pelo servidor."""
    deadline = time.monotonic() + timeout

    while True:
        remaining = deadline - time.monotonic()

        if remaining <= 0:
            return None

        sock.settimeout(remaining)

        try:
            data, addr = sock.recvfrom(4096)

        except socket.timeout:
            return None

        except ConnectionResetError:
            continue

        if addr[:2] != server_addr:
            continue

        try:
            message = json.loads(data.decode("utf-8"))

        except (ValueError, UnicodeDecodeError):
            continue

        if isinstance(message, dict):
            return message


def register_agent(sock, server_addr, name, interval=5, process=None):
    """
    Registra um agente no servidor.

    Tenta novamente caso o servidor ainda esteja iniciando.
    """
    message = {
        "type": "REGISTER",
        "name": name,
        "interval": interval
    }

    for attempt in range(10):

        if process is not None and process.poll() is not None:
            raise RuntimeError("O servidor encerrou inesperadamente.")

        send_json(sock, server_addr, message)

        response = receive_json(
            sock,
            server_addr,
            timeout=0.5
        )

        if response is not None:
            return response

    return None


def create_metrics(name, seq):
    """Cria uma mensagem METRICS valida para os testes."""
    return {
        "type": "METRICS",
        "name": name,
        "seq": seq,
        "cpu": {
            "overall": 25.5,
            "cores": [20.0, 30.0]
        },
        "memory": {
            "total_mb": 16000,
            "used_mb": 8000,
            "free_mb": 8000
        }
    }


def stop_server(process):
    """Encerra o servidor e evita deixar processos abertos."""
    if process is None:
        return

    if process.poll() is None:
        process.terminate()

    try:
        process.wait(timeout=5)

    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def main():
    """Executa os testes automaticos do servidor."""

    port = get_free_port()
    server_addr = ("127.0.0.1", port)

    clients = []
    process = None

    # Arquivo temporario para guardar os logs do servidor.
    server_log = tempfile.TemporaryFile(mode="w+b")

    command = [
        sys.executable,
        "-m",
        "server.server",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--no-dashboard"
    ]

    print("=" * 50)
    print("INICIANDO TESTES AUTOMATICOS DO SERVIDOR UDP")
    print("=" * 50)

    try:

        # Inicia o servidor automaticamente.
        process = subprocess.Popen(
            command,
            cwd=PROJECT_ROOT,
            stdout=server_log,
            stderr=subprocess.STDOUT
        )

        print(f"\nServidor iniciado na porta UDP {port}.")

        
        # TESTE 1 - REGISTRO DE UM AGENTE NOVO
       
        client1 = create_client()
        clients.append(client1)

        response = register_agent(
            client1,
            server_addr,
            "teste-registro",
            process=process
        )

        assert response is not None
        assert response.get("type") == "OK"

        print("[OK] Registro de agente novo.")

       
        # TESTE 2 - NOME REPETIDO EM OUTRO ENDERECO
        
        client2 = create_client()
        clients.append(client2)

        response = register_agent(
            client2,
            server_addr,
            "teste-registro",
            process=process
        )

        assert response is not None
        assert response.get("type") == "ERROR"
        assert response.get("reason") == "name already in use"

        print("[OK] Nome repetido foi recusado.")


        # TESTE 3 - METRICS SEM REGISTRO
        
        client3 = create_client()
        clients.append(client3)

        send_json(
            client3,
            server_addr,
            create_metrics("agente-desconhecido", 1)
        )

        response = receive_json(client3, server_addr)

        assert response is not None
        assert response.get("type") == "ERROR"
        assert response.get("reason") == "not registered"

        print("[OK] METRICS de agente nao registrado.")

       
        # TESTES 4 E 5 - PERDAS E DUPLICACOES
        
        client4 = create_client()
        clients.append(client4)

        response = register_agent(
            client4,
            server_addr,
            "teste-sequencia",
            process=process
        )

        assert response is not None
        assert response.get("type") == "OK"

        # Envia as sequencias 1 e 2.
        for seq in (1, 2):
            send_json(
                client4,
                server_addr,
                create_metrics("teste-sequencia", seq)
            )
            time.sleep(0.1)

        # Registra novamente pelo mesmo endereco.
        # O servidor deve preservar os contadores.
        response = register_agent(
            client4,
            server_addr,
            "teste-sequencia",
            process=process
        )

        assert response is not None
        assert response.get("type") == "OK"

        # Envia seq 5: os seq 3 e 4 devem ser
        # contabilizados como perdidos.
        send_json(
            client4,
            server_addr,
            create_metrics("teste-sequencia", 5)
        )

        time.sleep(0.1)

        # Envia novamente seq 5: deve ser duplicado.
        send_json(
            client4,
            server_addr,
            create_metrics("teste-sequencia", 5)
        )

        time.sleep(0.3)

        print("[OK] Mensagens com sequencia enviadas.")
        print("[OK] Verificacao de perdas e duplicacoes registrada.")

        
        # TESTE 6 - REMOCAO PELO BYE
        
        client5 = create_client()
        clients.append(client5)

        response = register_agent(
            client5,
            server_addr,
            "teste-bye",
            process=process
        )

        assert response is not None
        assert response.get("type") == "OK"

        # Envia BYE.
        send_json(
            client5,
            server_addr,
            {
                "type": "BYE",
                "name": "teste-bye"
            }
        )

        time.sleep(0.1)

        # Tenta enviar METRICS depois do BYE.
        send_json(
            client5,
            server_addr,
            create_metrics("teste-bye", 1)
        )

        response = receive_json(client5, server_addr)

        assert response is not None
        assert response.get("type") == "ERROR"
        assert response.get("reason") == "not registered"

        print("[OK] Agente removido pelo BYE.")

        
        # TESTE 7 - REMOCAO POR TIMEOUT
       
        client6 = create_client()
        clients.append(client6)

        response = register_agent(
            client6,
            server_addr,
            "teste-timeout",
            interval=1,
            process=process
        )

        assert response is not None
        assert response.get("type") == "OK"

        print("Aguardando timeout do agente (aproximadamente 4 segundos)...")

        # O servidor remove agentes que ficam mais de
        # tres intervalos sem enviar datagramas validos.
        time.sleep(4.5)

        send_json(
            client6,
            server_addr,
            create_metrics("teste-timeout", 1)
        )

        response = receive_json(
            client6,
            server_addr,
            timeout=2
        )

        assert response is not None
        assert response.get("type") == "ERROR"
        assert response.get("reason") == "not registered"

        print("[OK] Agente removido por timeout.")

        
        # TESTE 8 - MENSAGEM INVALIDA
       
        client7 = create_client()
        clients.append(client7)

        # Envia bytes que nao representam JSON valido.
        client7.sendto(
            b"{mensagem-invalida",
            server_addr
        )

        time.sleep(0.2)

        # Confere se o servidor continua funcionando.
        assert process.poll() is None

        # Tenta registrar outro agente depois da mensagem
        # invalida para comprovar que o servidor continua ativo.
        client8 = create_client()
        clients.append(client8)

        response = register_agent(
            client8,
            server_addr,
            "teste-pos-invalido",
            process=process
        )

        assert response is not None
        assert response.get("type") == "OK"

        assert process.poll() is None

        print("[OK] Mensagem invalida nao derrubou o servidor.")

        print("\nTodos os testes de comunicacao foram executados.")

    finally:

        # Fecha os sockets dos clientes.
        for client in clients:
            client.close()

        # Encerra o processo do servidor.
        stop_server(process)

  
    # VERIFICACAO DOS LOGS DO SERVIDOR
    
    server_log.seek(0)

    logs = server_log.read().decode(
        "utf-8",
        errors="replace"
    )

    server_log.close()

    print("\nVerificando os logs do servidor...")

    assert "2 pacote(s) perdido(s)" in logs, (
        "O servidor nao registrou os 2 pacotes perdidos."
    )

    print("[OK] Servidor registrou 2 pacotes perdidos.")

    assert "seq 5 duplicado ou fora de ordem" in logs, (
        "O servidor nao identificou a mensagem duplicada."
    )

    print("[OK] Servidor identificou a mensagem duplicada.")

    assert "timeout" in logs, (
        "O servidor nao registrou a remocao por timeout."
    )

    print("[OK] Servidor registrou a remocao por timeout.")

    assert "datagrama" in logs, (
        "O servidor nao registrou o datagrama invalido."
    )

    print("[OK] Servidor registrou o datagrama invalido.")

    print("\n" + "=" * 50)
    print("TODOS OS TESTES PASSARAM!")
    print("=" * 50)


if __name__ == "__main__":
    main()
