# Protocolo

Como o agente e o servidor conversam. O código está em `common/protocol.py`.

Usamos UDP na porta 5000. Cada mensagem é um JSON em UTF-8, mandado num datagrama só, com no máximo 1200 bytes. Como o UDP não tem conexão e pode perder, duplicar ou trocar a ordem dos pacotes, o protocolo cuida disso com um número de sequência (`seq`) e com retentativa no registro.

## Mensagens

REGISTER (agente para servidor), a primeira mensagem do agente:

```json
{"type": "REGISTER", "name": "agent-ana", "interval": 5}
```

`name` é o nome do agente e `interval` é o tempo em segundos entre os envios de METRICS.

OK ou ERROR (servidor para agente), resposta ao REGISTER:

```json
{"type": "OK"}
{"type": "ERROR", "reason": "name already in use"}
```

O servidor também responde ERROR (`not registered`) quando chega um METRICS de um agente que não está registrado.

METRICS (agente para servidor), a cada intervalo. O servidor não responde:

```json
{"type": "METRICS", "name": "agent-ana", "seq": 12,
 "cpu": {"overall": 23.5, "cores": [20.1, 30.4, 18.0, 26.2]},
 "memory": {"total_mb": 16000, "used_mb": 8200, "free_mb": 7800}}
```

BYE (agente para servidor), quando o agente encerra com Ctrl+C. O servidor não responde:

```json
{"type": "BYE", "name": "agent-ana"}
```

## Regras

1. Datagrama inválido (não é JSON, não é objeto, sem `type` ou com tipo desconhecido) é ignorado e vai para o log. O servidor não cai por causa disso.
2. O agente manda o REGISTER e espera o OK por 2 segundos. Se não vier, tenta de novo, até 3 tentativas no total. Depois desiste.
3. O servidor, ao receber um REGISTER:
   - nome novo: registra e responde OK;
   - mesmo nome, vindo do mesmo endereço: responde OK de novo, sem zerar os contadores (o OK anterior provavelmente se perdeu);
   - mesmo nome, vindo de outro endereço: ERROR `name already in use`;
   - nome vazio ou intervalo menor ou igual a zero: ERROR `invalid REGISTER`.
4. O METRICS traz `name` e `seq` (o agente conta 1, 2, 3...). O servidor só aceita de um agente registrado e do mesmo endereço do registro. Senão responde ERROR `not registered`, e o agente se registra de novo sozinho, sem voltar o `seq` para 1.
5. O primeiro `seq` depois do registro é só a referência: nada é contado como perdido. Depois disso, se o `seq` vier maior que o esperado, a diferença (`seq - último - 1`) é somada em perdidos. Se vier menor ou igual ao último, conta como duplicado (ou fora de ordem) e a leitura é descartada.
6. O BYE faz o servidor remover o agente na hora, se o endereço bater.
7. Se o servidor ficar 3 vezes o intervalo sem receber nenhum datagrama válido de um agente, ele remove o agente.
8. Se um agente for morto sem BYE (por exemplo, `kill -9`) e reiniciado com o mesmo nome, o servidor recusa até o timeout passar. É esperado.

## Usando no código

```python
from common.protocol import Endpoint

ep = Endpoint(sock)
ep.send({"type": "OK"}, addr)
message, addr = ep.receive()
```

`receive()` devolve `message = None` se o datagrama for lixo, e levanta `socket.timeout` se o socket tiver timeout e nada chegar.