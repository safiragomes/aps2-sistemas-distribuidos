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