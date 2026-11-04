import argparse
import socket
import sys
import time
from typing import Tuple, Dict, Any

from common.protocol import Endpoint
from agent.collector import collect_metrics

# Configura e processa os argumentos de linha de comando
def parse_args():
    parser = argparse.ArgumentParser(description="Agente de Monitoramento UDP (Fase 3)")
    parser.add_argument("--host", default="127.0.0.1", help="Endereço IP do servidor")
    parser.add_argument("--port", type=int, default=5000, help="Porta UDP do servidor")
    parser.add_argument("--name", required=True, help="Nome de registro do agente")
    parser.add_argument("--interval", type=int, default=5, help="Intervalo de envio em segundos")
    return parser.parse_args()

# Tenta registrar o agente no servidor enviando um datagrama REGISTER 
# Limita a 3 tentativas, esperando 2 segundos por resposta em cada uma
def register_agent(ep: Endpoint, server_addr: Tuple[str, int], name: str, interval: int) -> bool:
    register_msg = {
        "type": "REGISTER",
        "name": name,
        "interval": interval
    }

    for attempt in range(1, 4):
        try:
            # Envia a mensagem de registro sem estabelecer conexão persistente
            ep.send(register_msg, server_addr)
            print(f"[Registro] Tentativa {attempt}/3: Enviando REGISTER para {server_addr}...")

            # Timeout de 2 segundos
            ep.sock.settimeout(2.0)

            # Descartar lixo ou respostas de endereços errados
            while True:
                msg, addr = ep.receive()
                
                # Ignora datagramas inválidos (None) ou vindos de IP/Porta desconhecidos
                if msg is None or addr != server_addr:
                    continue
                
                msg_type = msg.get("type")
                if msg_type == "OK":
                    print("[Registro] Sucesso! Agente registrado no servidor.")
                    return True
                elif msg_type == "ERROR":
                    reason = msg.get("reason", "motivo não especificado")
                    print(f"[Registro] Servidor recusou o registro. Motivo: {reason}")
                    return False

        except socket.timeout:
            print(f"[Registro] Timeout na tentativa {attempt}. Sem resposta em 2s.")
        except OSError as e:
            print(f"[Registro] Erro de rede durante comunicação: {e}")
            return False

    # Esgotou as 3 tentativas e continuou caindo no timeout
    print("[Registro] Falha crítica: O servidor não responde após 3 tentativas.")
    return False
