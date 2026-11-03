import json

DEFAULT_PORT = 5000
MAX_DATAGRAM = 1200

class Endpoint:
    # Envia e recebe mensagens JSON, uma por datagrama UDP.

    def __init__(self, sock):
        self.sock = sock

    def send(self, message, addr):
        data = json.dumps(message).encode("utf-8")
        if len(data) > MAX_DATAGRAM:
            raise ValueError(f"mensagem com {len(data)} bytes, o máximo é {MAX_DATAGRAM}")
        self.sock.sendto(data, addr)

    def receive(self):
        # Devolve (mensagem, endereço). A mensagem é None se o datagrama não for um JSON de objeto.
        while True:
            try:
                data, addr = self.sock.recvfrom(4096)
                break
            except ConnectionResetError:
                # no Windows, um envio para uma porta fechada faz o próximo recvfrom falhar com este erro
                continue
        try:
            message = json.loads(data.decode("utf-8"))
        except ValueError:
            return None, addr
        if not isinstance(message, dict):
            return None, addr
        return message, addr

    def close(self):
        self.sock.close()