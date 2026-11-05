# Monitor de desempenho distribuído (UDP)

Sistema que acompanha, em tempo real, o uso de CPU e de memória de várias máquinas a partir de um servidor central. A comunicação entre as partes é feita com sockets UDP.

## Como funciona

O sistema tem duas partes:

- **Agente** (`agent/agent.py`): roda em cada máquina monitorada. Coleta o uso de CPU (geral e por núcleo) e de memória com a biblioteca `psutil` (`agent/collector.py`) e envia essas leituras ao servidor em intervalos regulares.
- **Servidor** (`server/server.py`): recebe as leituras de todos os agentes, guarda o estado de cada um (`server/state.py`), conta pacotes perdidos e duplicados e mostra tudo num painel no terminal (`server/dashboard.py`), atualizado automaticamente.

A conversa entre agente e servidor segue um protocolo simples de mensagens JSON, uma por datagrama UDP (detalhes em [`docs/protocol.md`](docs/protocol.md)):

1. O agente envia `REGISTER` com seu nome e intervalo de envio e espera a resposta `OK` (ou `ERROR`, com o motivo). Sem resposta em 2 segundos, tenta de novo, até 3 tentativas.
2. Registrado, o agente envia um `METRICS` a cada intervalo, com um número de sequência (`seq`) que cresce 1, 2, 3... O servidor não responde a essas mensagens.
3. Ao ser encerrado com Ctrl+C, o agente envia `BYE` e o servidor o remove na hora.
4. Se um agente ficar mais de 3 vezes o seu intervalo sem mandar nada, o servidor o remove por timeout.

## Requisitos e instalação

- Python 3.8 ou superior (testado com Python 3.13).
- Biblioteca externa: `psutil` (coleta de CPU e memória), listada em `requirements.txt`. O restante usa apenas a biblioteca padrão do Python (`socket`, `json`, `threading`, `argparse`, `logging`).

Na raiz do repositório, instale a dependência:

```bash
python -m pip install -r requirements.txt
```

> Em alguns sistemas Linux o comando do Python é `python3` em vez de `python`. Nesse caso, troque `python` por `python3` em todos os comandos deste README.

## Como executar

Todos os comandos devem ser executados **na raiz do repositório**, usando `python -m` (assim os pacotes `agent`, `server` e `common` são encontrados).

### Servidor

```bash
python -m server.server
```

Por padrão o servidor escuta em `0.0.0.0` (todas as interfaces), na porta UDP `5000`, e mostra o painel no terminal. Com o painel ligado, os eventos (registros, saídas, timeouts, perdas, duplicados, datagramas inválidos) vão para o arquivo `server.log`, criado na pasta em que o servidor foi iniciado.

| Argumento | Padrão | Descrição |
|---|---|---|
| `--host` | `0.0.0.0` | Endereço em que o servidor escuta |
| `--port` | `5000` | Porta UDP do servidor |
| `--refresh` | `2` | Segundos entre as atualizações do painel |
| `--no-dashboard` | desligado | Não mostra o painel; os logs aparecem no terminal (e o `server.log` não é criado) |

Exemplos:

```bash
python -m server.server --port 6000 --refresh 1
```

```bash
python -m server.server --no-dashboard
```

Para encerrar o servidor, use Ctrl+C. Se a porta já estiver em uso, o servidor avisa e encerra (`Não foi possível usar 0.0.0.0:5000: ...`).

### Agente

Em outro terminal (ou em outra máquina):

```bash
python -m agent.agent --name agent-ana
```

| Argumento | Padrão | Descrição |
|---|---|---|
| `--name` | obrigatório | Nome do agente (único no servidor) |
| `--host` | `127.0.0.1` | Endereço IP do servidor |
| `--port` | `5000` | Porta UDP do servidor |
| `--interval` | `5` | Intervalo entre os envios, em segundos (número inteiro) |

Para monitorar outra máquina, rode o agente nela informando o IP do servidor:

```bash
python -m agent.agent --host 192.168.0.10 --port 5000 --name lab-pc01 --interval 5
```

O agente mostra uma linha por envio e, ao receber Ctrl+C, envia `BYE` e encerra. Se o servidor reiniciar, o agente recebe `ERROR not registered` e se registra de novo sozinho, sem voltar o `seq` para 1.

### Vários agentes

Cada agente é um processo independente com um nome diferente. Abra um terminal para cada um:

```bash
python -m agent.agent --name agent-ana --interval 5
```

```bash
python -m agent.agent --name agent-bia --interval 3
```

```bash
python -m agent.agent --name agent-caio --interval 10
```

Dois agentes com o mesmo nome não são aceitos ao mesmo tempo: o segundo recebe `name already in use` e encerra.

### Simulador de agentes

O simulador (`tests/simulate_agents.py`) cria vários agentes ao mesmo tempo, cada um numa thread com seu próprio socket, e força situações que o UDP local quase nunca produz sozinho:

| Agente | Comportamento |
|---|---|
| `agent-3` | Envia duas leituras e para, **sem** `BYE` (testa o timeout) |
| `agent-5` | Deixa de enviar cerca de 30% das leituras, mas continua contando o `seq` (testa perdidos) |
| `agent-7` | Repete de vez em quando uma leitura com o mesmo `seq` (testa duplicados) |
| `agent-8` | Envia o `REGISTER` duas vezes (testa o registro repetido) |
| `agent-9` | Envia de vez em quando um datagrama que não é JSON (testa lixo) |
| demais | Funcionam normalmente e terminam com `BYE` |

Com o servidor rodando, em outro terminal:

```bash
python -m tests.simulate_agents --agents 10 --duration 60 --interval 5
```

| Argumento | Padrão | Descrição |
|---|---|---|
| `--agents` | `10` | Quantidade de agentes simulados |
| `--duration` | `60` | Duração da simulação, em segundos |
| `--interval` | `5` | Intervalo entre os envios, em segundos |
| `--host` | `127.0.0.1` | Endereço do servidor |
| `--port` | `5000` | Porta UDP do servidor |

### Testes

```bash
python tests/testProtocol.py
```

```bash
python tests/testState.py
```

```bash
python tests/testDashboard.py
```

```bash
python tests/check_server.py
```

O `check_server.py` sobe o próprio servidor numa porta livre (com `--no-dashboard`), conversa com ele por UDP e o encerra no final; não é preciso iniciar outro servidor antes. O roteiro de testes completo está em [`docs/testing.md`](docs/testing.md).

## O painel

O painel mostra uma linha por agente registrado, ordenada pelo nome:

| Coluna | Significado |
|---|---|
| Agente | Nome informado no `REGISTER` |
| Endereco | IP e porta de origem dos datagramas do agente |
| Conectado | Tempo desde o registro (`HH:MM:SS`) |
| Ultima msg | Horário da última leitura aceita |
| CPU | Uso geral de CPU na última leitura |
| Memoria | Memória usada / total na última leitura |
| Recebidas | Leituras aceitas pelo servidor |
| Perdidas | Leituras que não chegaram, deduzidas pelos buracos no `seq` |
| Duplicadas | Leituras descartadas por terem `seq` repetido ou fora de ordem |
| % perda | `perdidas / (recebidas + perdidas)` |

Sem nenhum agente, o painel mostra `Nenhum agente registrado`. Um agente que acabou de se registrar e ainda não mandou leituras aparece com `-` nos campos sem valor.

## Diferenças entre TCP e UDP

Esta é a mesma atividade da APS 01, que usava TCP. Trocar para UDP mudou bastante coisa:

- **Sem conexão.** No TCP o servidor fazia `listen`/`accept` e mantinha uma conexão (e uma thread) por agente; quando a conexão fechava, o servidor sabia que o agente tinha saído. No UDP não existe conexão: o servidor tem um único socket e um único laço com `recvfrom` que recebe datagramas de todos os agentes, e identifica quem mandou pelo nome e pelo endereço de origem. Por isso o agente precisa se apresentar com o `REGISTER`, e o servidor responde `OK`/`ERROR` para que o agente saiba que foi aceito.
- **Uma mensagem por datagrama.** O TCP entrega um fluxo contínuo de bytes, e era preciso separar uma mensagem da outra (por exemplo, por quebra de linha). No UDP cada datagrama já é uma mensagem completa: aqui, um JSON de até 1200 bytes, tamanho que cabe num pacote sem fragmentação na maioria das redes.
- **Perda de pacotes.** O TCP reenvia o que se perde; o UDP não. Um datagrama pode simplesmente não chegar, e nem o agente nem o servidor ficam sabendo na hora. Por isso o `REGISTER` tem retentativa (3 tentativas de 2 s): se o pedido ou o `OK` se perder, o agente pergunta de novo.
- **Duplicação e fora de ordem.** O TCP entrega tudo uma vez só e na ordem. No UDP um datagrama pode chegar repetido ou depois de outro que foi enviado mais tarde.
- **Número de sequência (`seq`).** É o que permite ao servidor perceber esses problemas. Cada `METRICS` leva um `seq` que o agente incrementa a cada envio. O primeiro recebido serve de referência. Se chega um `seq` maior que o esperado, a diferença conta como **perdidos** (ex.: depois do 2 chega o 5, então 3 e 4 se perderam). Se chega um `seq` menor ou igual ao último aceito, ele conta como **duplicado** e a leitura é descartada.
- **Saída por BYE ou timeout.** Sem conexão, o servidor não percebe quando um agente cai. O agente avisa com `BYE` ao ser encerrado com Ctrl+C; se ele travar, for morto ou perder a rede (ou o próprio `BYE` se perder), o servidor só descobre pela falta de mensagens e o remove depois de 3 vezes o intervalo informado.

## Limitações

- **Uma leitura perdida não é reenviada.** O servidor só conta a perda pelo `seq`; o valor daquela leitura não é recuperado.
- **Um nome só pode ser reutilizado depois de BYE ou timeout.** Se um agente for morto sem enviar `BYE` (por exemplo, `kill -9`) e for reiniciado com o mesmo nome, ele sai de outra porta e o servidor recusa com `name already in use` até o timeout do registro antigo passar (3 vezes o intervalo).
- **Sem criptografia nem autenticação.** As mensagens trafegam em JSON puro: qualquer pessoa na rede pode lê-las ou enviar datagramas se passando por um agente.
- O estado fica só na memória do servidor: ao reiniciá-lo, os contadores começam do zero (os agentes se registram de novo sozinhos).

## Firewall

O servidor recebe datagramas na **porta UDP 5000** (ou na informada em `--port`). Para receber agentes de outras máquinas, libere essa porta UDP no firewall da máquina do servidor (no Windows, o próprio sistema costuma perguntar na primeira execução; no Linux, por exemplo, `sudo ufw allow 5000/udp`). As máquinas precisam estar na mesma rede ou ter rota entre si.

## Estrutura de pastas

```
.
├── agent/
│   ├── agent.py            # agente: registro, envio de METRICS e BYE
│   └── collector.py        # coleta de CPU e memória com psutil
├── common/
│   └── protocol.py         # Endpoint: envia e recebe JSON por UDP; porta e tamanho máximo
├── server/
│   ├── server.py           # servidor: laço recvfrom, tratamento das mensagens e timeout
│   ├── state.py            # estado dos agentes, contagem de perdidos e duplicados
│   └── dashboard.py        # painel no terminal
├── tests/
│   ├── testProtocol.py     # testes do protocolo
│   ├── testState.py        # testes do State
│   ├── testDashboard.py    # testes do painel com dados falsos
│   ├── check_server.py     # teste automático do servidor por UDP
│   └── simulate_agents.py  # simulador de vários agentes
├── docs/
│   ├── protocol.md         # mensagens e regras do protocolo
│   └── testing.md          # roteiro de testes
├── requirements.txt
└── README.md
```

## Exemplo de execução

Terminal 1, servidor com painel:

```bash
python -m server.server
```

Terminal 2, simulador com 10 agentes por 60 segundos:

```bash
python -m tests.simulate_agents --agents 10 --duration 60 --interval 5
```

Painel cerca de 56 segundos depois do início (saída real; os endereços, horários e valores mudam a cada execução). O `agent-3` já foi removido por timeout, o `agent-5` mostra 3 leituras perdidas e o `agent-7`, 3 duplicadas:

```
===================================================================================================================
MONITOR DE DESEMPENHO (UDP) - 23:23:05
Agentes registrados: 9
===================================================================================================================
Agente    Endereco         Conectado  Ultima msg  CPU   Memoria            Recebidas  Perdidas  Duplicadas  % perda
-------------------------------------------------------------------------------------------------------------------
agent-1   127.0.0.1:42177  00:00:56   23:23:04    0.0%  480/16091 MB (3%)  12         0         0           0.0%
agent-10  127.0.0.1:59721  00:00:56   23:23:04    0.0%  480/16091 MB (3%)  12         0         0           0.0%
agent-2   127.0.0.1:33613  00:00:56   23:23:04    0.0%  480/16091 MB (3%)  12         0         0           0.0%
agent-4   127.0.0.1:44305  00:00:56   23:23:04    0.0%  480/16091 MB (3%)  12         0         0           0.0%
agent-5   127.0.0.1:45700  00:00:56   23:23:04    0.0%  480/16091 MB (3%)  9          3         0           25.0%
agent-6   127.0.0.1:47313  00:00:56   23:23:04    0.0%  480/16091 MB (3%)  12         0         0           0.0%
agent-7   127.0.0.1:38514  00:00:56   23:23:04    0.0%  480/16091 MB (3%)  12         0         3           0.0%
agent-8   127.0.0.1:39184  00:00:56   23:23:04    0.0%  480/16091 MB (3%)  12         0         0           0.0%
agent-9   127.0.0.1:40049  00:00:56   23:23:04    0.0%  480/16091 MB (3%)  12         0         0           0.0%
===================================================================================================================
```

Ao fim da simulação, os agentes enviam `BYE` e o painel volta a mostrar `Nenhum agente registrado`.

Trecho do `server.log` da mesma execução:

```
23:22:07 escutando em 0.0.0.0:5000 (UDP)
23:22:08 agent-1 registrado (127.0.0.1:42177, intervalo 5s)
...
23:22:08 agent-8 registrado (127.0.0.1:39184, intervalo 5s)
23:22:23 agent-5: 1 pacote(s) perdido(s) até o seq 4
23:22:23 agent-7: seq 4 duplicado ou fora de ordem
23:22:28 agent-3 ficou sem enviar nada, removendo (timeout)
23:22:28 datagrama inválido de 127.0.0.1:40049
...
23:23:09 agent-1 saiu (BYE)
23:23:09 agent-5 saiu (BYE)
```

Um agente real, encerrado com Ctrl+C:

```
$ python -m agent.agent --name agent-ana --interval 2
[Registro] Tentativa 1/3: Enviando REGISTER para ('127.0.0.1', 5000)...
[Registro] Sucesso! Agente registrado no servidor.
[23:23:59] METRICS seq=1 enviado - CPU: 0.0%
[23:24:01] METRICS seq=2 enviado - CPU: 0.0%
[23:24:03] METRICS seq=3 enviado - CPU: 0.0%

[Saída] Sinal de interrupção detectado. Encerrando agente...
[Saída] Mensagem BYE enviada.
Execução finalizada.
```

Sem servidor no endereço informado, o agente desiste depois de 3 tentativas:

```
$ python -m agent.agent --name agent-ana --port 5999
[Registro] Tentativa 1/3: Enviando REGISTER para ('127.0.0.1', 5999)...
[Registro] Timeout na tentativa 1. Sem resposta em 2s.
[Registro] Tentativa 2/3: Enviando REGISTER para ('127.0.0.1', 5999)...
[Registro] Timeout na tentativa 2. Sem resposta em 2s.
[Registro] Tentativa 3/3: Enviando REGISTER para ('127.0.0.1', 5999)...
[Registro] Timeout na tentativa 3. Sem resposta em 2s.
[Registro] Falha crítica: O servidor não responde após 3 tentativas.
```
