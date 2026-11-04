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

# Métricas de CPU com 1 casa decimal
def round_metrics_inplace(metrics: Dict[str, Any]):
    cpu = metrics.get("cpu", {})
    if "overall" in cpu:
        cpu["overall"] = round(cpu["overall"], 1)
    if "cores" in cpu:
        cpu["cores"] = [round(c, 1) for c in cpu["cores"]]

def main():
    args = parse_args()
    server_addr = (args.host, args.port)

    # Inicializa socket focado no protocolo de datagramas
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        ep = Endpoint(sock)
    except OSError as e:
        print(f"Erro fatal ao criar socket UDP: {e}")
        sys.exit(1)

    # Executa a rotina de handshaking/registro
    if not register_agent(ep, server_addr, args.name, args.interval):
        ep.close()
        sys.exit(1)

    seq = 1
    
    try:
        while True:
            # Coleta e arredonda percentuais
            metrics = collect_metrics()
            round_metrics_inplace(metrics)
            
            # Adiciona campos estruturais de protocolo e envia
            metrics["name"] = args.name
            metrics["seq"] = seq
            
            try:
                ep.send(metrics, server_addr)
                print(f"[{time.strftime('%H:%M:%S')}] METRICS seq={seq} enviado - CPU: {metrics['cpu']['overall']}%")
            except OSError as e:
                print(f"[Erro] Falha temporária ao enviar métrica de seq={seq}: {e}")
            
            # Prepara o próximo identificador 
            seq += 1

            # Micro-laço de espera: ao invés de travar a thread num time.sleep(interval)
            # agente escuta a rede durante os segundos de intervalo para tratar quedas/resets no servidor
            end_time = time.time() + args.interval
            while time.time() < end_time:
                remaining = end_time - time.time()
                if remaining <= 0:
                    break
                
                ep.sock.settimeout(remaining)
                try:
                    msg, addr = ep.receive()
                    if msg and addr == server_addr:
                        # Se o servidor reiniciar e perder a memória RAM: 'not registered'
                        # O agente capta e refaz o registro preservando o 'seq'
                        if msg.get("type") == "ERROR" and msg.get("reason") == "not registered":
                            print("[Aviso] O Servidor não reconhece o agente. Refazendo registro...")
                            if not register_agent(ep, server_addr, args.name, args.interval):
                                print("[Erro] Impossível refazer o registro automático. Saindo.")
                                sys.exit(1)
                except socket.timeout:
                    # Timeout esperado - apenas o tempo de espera do intervalo passou
                    pass
                except OSError:
                    # Impede que quedas bruscas de link matem o cliente durante o recv
                    break

    except KeyboardInterrupt:
        print("\n[Saída] Sinal de interrupção detectado. Encerrando agente...")
        bye_msg = {"type": "BYE", "name": args.name}
        try:
            ep.send(bye_msg, server_addr)
            print("[Saída] Mensagem BYE enviada.")
        except OSError:
            pass  # Omite stack trace se a placa de rede já estiver inativa
            
    finally:
        # Fechamento garantindo devolução da porta ao SO
        ep.close()
        print("Execução finalizada.")


if __name__ == "__main__":
    main()