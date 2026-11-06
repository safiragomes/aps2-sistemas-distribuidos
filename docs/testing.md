# Roteiro e resultados dos testes — APS 02, Equipe 06 (UDP)

## 1. Objetivo

Este documento reúne os procedimentos e os resultados observados nos testes do sistema distribuído de monitoramento de CPU e memória da Equipe 06. O sistema utiliza sockets UDP para registrar agentes, receber métricas periodicamente e apresentar informações em um painel no terminal.

Foram verificados o protocolo de mensagens, o gerenciamento dos agentes, a contagem de perdas e duplicações por número de sequência (`seq`), a remoção por `BYE` ou *timeout*, a tolerância a datagramas inválidos e o funcionamento com múltiplos agentes. Os resultados abaixo se referem somente a execuções registradas; cenários sem evidência específica são identificados separadamente.

## 2. Ambientes utilizados

Os registros incluem execuções realizadas em dois ambientes:

| Característica | Execução em Windows | Execução em macOS |
|---|---|---|
| Sistema operacional | Windows | macOS |
| Versão do Python | Não informada no registro | 3.9.6 |
| Biblioteca externa | `psutil` | `psutil` 7.2.2 |
| Protocolo | UDP | UDP |
| Endereço usado | `127.0.0.1` | `127.0.0.1` |
| Porta do servidor manual | `5000` | `5000` |
| Simulação principal | 10 agentes, 60 s, intervalo de 5 s | 10 agentes, 60 s, intervalo de 2 s |
| Teste automático do servidor | Porta UDP disponível (`58666` no registro) | Porta UDP disponível (`55198` na execução) |
| Visualização | Testes do servidor com `--no-dashboard` | Servidor também testado com painel ativo |


Os agentes e o servidor foram testados localmente. O endereço `127.0.0.1` não comprova comunicação entre computadores físicos distintos.

## 3. Comandos para reprodução

Execute os comandos na raiz do repositório. No macOS, foi utilizado `python3`; em sistemas em que o executável se chama `python`, ele pode ser usado no lugar.

### 3.1. Instalação

```bash
python3 -m pip install -r requirements.txt
```

Na execução em macOS, o `pip` confirmou que `psutil` 7.2.2 já estava instalado.

### 3.2. Testes automatizados

```bash
python3 tests/testProtocol.py
python3 tests/testState.py
python3 tests/testDashboard.py
python3 tests/check_server.py
```

O `check_server.py` inicia um servidor UDP de teste em uma porta disponível e o encerra ao final; não exige que um servidor manual já esteja aberto.

### 3.3. Servidor e agente reais

Terminal do servidor:

```bash
python3 -m server.server --port 5000
```

Terminal do agente:

```bash
python3 -m agent.agent --host 127.0.0.1 --port 5000 --name agente-teste --interval 2
```

Para verificar o encerramento normal, pressione `Ctrl+C` no terminal do agente e observe o envio de `BYE` e sua remoção do painel.

### 3.4. Simulador de dez agentes

Com o servidor ativo, em outro terminal:

```bash
python3 -m tests.simulate_agents --agents 10 --duration 60 --interval 2 --port 5000
```

A execução como módulo (`python3 -m tests.simulate_agents`) foi validada no macOS e corresponde à forma de execução indicada no README. A execução direta de `python3 tests/simulate_agents.py` apresentou `ModuleNotFoundError: No module named 'agent'` nesse ambiente, enquanto a execução como módulo funcionou normalmente.

## 4. Resultados dos testes automatizados

### 4.1. Protocolo UDP, estado e painel

Os três scripts foram executados no macOS e apresentaram a mensagem de aprovação de todos os seus testes.

| Arquivo | Quantidade | Funcionalidades verificadas | Resultado |
|---|---:|---|---|
| `tests/testProtocol.py` | 7 | Envio e recebimento, acentos, bytes não UTF-8, JSON que não é objeto, mensagem grande, texto inválido e timeout | **7/7 aprovados** |
| `tests/testState.py` | 11 | Registro, endereço de origem, sequência, perdas, duplicações, remoção, expiração, limite de leituras, concorrência e registro repetido | **11/11 aprovados** |
| `tests/testDashboard.py` | 8 | Painel sem agentes, agente sem leituras, cabeçalhos, dados incompletos, última leitura, estado real, dados simulados e atualização em thread | **8/8 aprovados** |
| **Total** | **26** | | **26/26 aprovados** |

### 4.2. Testes automáticos do servidor UDP

O arquivo `tests/check_server.py` também foi executado nos registros disponíveis. Na execução em macOS, iniciou o servidor na porta UDP `55198` e terminou com a mensagem `TODOS OS TESTES PASSARAM!`.

| Cenário | Resultado esperado | Resultado observado |
|---|---|---|
| Registro de um agente novo | Resposta `OK` | **APROVADO** — registro aceito |
| Nome já utilizado por outro endereço | Resposta `ERROR`, motivo `name already in use` | **APROVADO** — segundo registro recusado |
| `METRICS` de agente não registrado | Resposta `ERROR not registered` | **APROVADO** — mensagem rejeitada |
| Lacunas nos números de sequência | Contabilizar mensagens perdidas | **APROVADO** — log registrou 2 pacotes perdidos |
| Sequência repetida | Descartar e identificar duplicação | **APROVADO** — duplicação registrada |
| Saída por `BYE` | Remover o agente | **APROVADO** — remoção confirmada |
| Inatividade do agente | Remover por *timeout* | **APROVADO** — remoção após período de espera |
| Datagrama inválido | Ignorar conteúdo inválido sem derrubar o servidor | **APROVADO** — servidor continuou respondendo |

Os resultados dos testes do servidor foram verificados também por meio das mensagens registradas nos logs. Essas verificações não foram somadas novamente aos 26 testes individuais da tabela anterior.

## 5. Teste com servidor e agente reais

Foi iniciado um servidor UDP na porta `5000`, com painel ativo, e um agente chamado `agente-teste`, configurado com intervalo de 2 segundos. O agente recebeu a confirmação de registro na primeira tentativa e enviou métricas reais de CPU e memória, com números de sequência crescentes de `1` até `47`.

O painel apresentou o agente registrado, seu endereço de origem, horário da última mensagem, CPU, memória e contadores de mensagens recebidas, perdidas e duplicadas. Durante esse teste local, as leituras exibidas não apresentaram perdas nem duplicações.

Ao pressionar `Ctrl+C`, o agente exibiu:

```text
[Saída] Sinal de interrupção detectado. Encerrando agente...
[Saída] Mensagem BYE enviada.
Execução finalizada.
```

Em seguida, o painel do servidor voltou a mostrar `Nenhum agente registrado`, confirmando a remoção do agente após o encerramento normal.

**Resultado: APROVADO.**

## 6. Simulações com múltiplos agentes

Foram registradas simulações com dez agentes, duração configurada de 60 segundos e dois intervalos diferentes: 5 segundos em uma execução no Windows e 2 segundos em uma execução no macOS. Em ambas, os resultados documentados demonstraram registro de múltiplos agentes e tratamento dos comportamentos especiais previstos no simulador.

### 6.1. Comportamentos observados

| Agente / situação | Comportamento simulado | Resultado observado |
|---|---|---|
| `agent-1` a `agent-10` | Registro de dez agentes | **APROVADO** — dez confirmações de registro |
| `agent-3` | Parar de transmitir após duas leituras, sem `BYE` | **APROVADO** — removido por *timeout* |
| `agent-5` | Omitir intencionalmente parte dos envios, mantendo a sequência | **APROVADO** — servidor contabilizou perdas |
| `agent-7` | Reenviar sequências já utilizadas | **APROVADO** — duplicações registradas |
| `agent-8` | Repetir `REGISTER` usando o mesmo socket | **APROVADO** — registro repetido aceito; preservação dos contadores também foi coberta no teste de `State` |
| `agent-9` | Enviar conteúdo que não é JSON válido | **APROVADO** — datagramas inválidos registrados sem derrubar o servidor |
| Demais nove agentes | Encerrar enviando `BYE` | **APROVADO** — nove saídas registradas no servidor |

Na execução registrada com intervalo de 5 segundos, os exemplos do log mostram três perdas do agente 5 até as sequências 4, 7 e 10, e três duplicações do agente 7 nas sequências 4, 8 e 12. Esses valores são referentes aos eventos documentados naquela execução, não a um total fixo do simulador.

### 6.2. Execução com intervalo de 2 segundos

- **Início registrado:** 19:56:17.
- **Fim registrado:** 19:57:18.
- **Configuração:** 10 agentes, duração de 60 segundos e intervalo de 2 segundos.
- **Mensagem final:** `Simulação finalizada.`
- **Código de saída:** `0`, confirmado com `echo $?`.

O servidor registrou oito ocorrências de perda do agente 5 até as sequências 4, 7, 10, 14, 17, 20, 24 e 27 e duplicações do agente 7 nas sequências 4, 8, 12, 16, 20, 24 e 28. O agente 3 foi removido por *timeout* às 19:56:25. O agente 9 enviou datagramas inválidos, e o servidor continuou processando as mensagens. Ao final, os outros nove agentes enviaram `BYE`.

Trechos do `server.log` dessa execução:

```text
19:56:23 agent-7: seq 4 duplicado ou fora de ordem
19:56:23 agent-5: 1 pacote(s) perdido(s) até o seq 4
19:56:25 agent-3 ficou sem enviar nada, removendo (timeout)
19:56:25 datagrama inválido de 127.0.0.1:52730
19:56:29 agent-5: 1 pacote(s) perdido(s) até o seq 7
19:57:05 agent-5: 1 pacote(s) perdido(s) até o seq 24
19:57:05 agent-7: seq 24 duplicado ou fora de ordem
19:57:14 agent-7: seq 28 duplicado ou fora de ordem
19:57:18 agent-1 saiu (BYE)
19:57:18 agent-7 saiu (BYE)
19:57:18 agent-10 saiu (BYE)
19:57:18 agent-5 saiu (BYE)
19:57:18 agent-6 saiu (BYE)
19:57:18 agent-9 saiu (BYE)
19:57:18 agent-8 saiu (BYE)
19:57:18 agent-4 saiu (BYE)
19:57:18 agent-2 saiu (BYE)
```

**Resultado: APROVADO.** A simulação terminou normalmente e confirmou os comportamentos previstos. As perdas foram provocadas pelo simulador; elas não representam uma medição da taxa real de perda da rede local.

## 7. Outros cenários de teste

A tabela diferencia os cenários observados dos que não tiveram execução específica registrada. **Não realizado** não significa que o sistema falhou, mas que não há evidência suficiente para atribuir aprovação ao cenário.

| Cenário | Situação | Observação |
|---|---|---|
| Um agente real conectado | **APROVADO** | `agente-teste` enviou 47 leituras no macOS |
| Três agentes reais em processos separados | **NÃO REALIZADO isoladamente** | A simulação com dez agentes usou threads, não três processos reais independentes |
| Encerramento de agente com `Ctrl+C` | **APROVADO** | `BYE` enviado; agente removido do painel |
| Encerramento abrupto com `kill -9` | **NÃO REALIZADO isoladamente** | A remoção por inatividade foi comprovada por simulação e teste automático |
| Nome duplicado | **APROVADO** | Recusa confirmada no teste do servidor |
| Reinício do servidor com agente ativo | **NÃO REALIZADO** | A recuperação automática do agente não foi verificada nessa condição |
| Agente iniciado sem servidor ativo | **NÃO REALIZADO** | O comportamento aparece no exemplo do README, mas não há registro de execução específica nos testes analisados |
| Perdas de pacotes simuladas | **APROVADO** | Lacunas de sequência do agente 5 identificadas |
| Mensagens duplicadas simuladas | **APROVADO** | Sequências repetidas do agente 7 identificadas |
| Datagramas inválidos | **APROVADO** | Servidor permaneceu operacional |
| Dez agentes durante 60 segundos | **APROVADO** | Simulação encerrada com código de saída 0 |
| Comunicação entre computadores físicos distintos | **NÃO REALIZADO** | Os testes registrados utilizaram `127.0.0.1` |

## 8. Conferência da documentação e do repositório

O comando de execução do simulador apresentado no README foi verificado utilizando a opção `-m`, tanto com `--help` quanto na simulação completa. Os scripts de testes também foram executados a partir da raiz de uma cópia clonada do projeto.

Na conferência do Git, `git status` indicou a branch `main` sincronizada com `origin/main` e sem alterações pendentes. O comando abaixo não retornou arquivos temporários rastreados:

```bash
git ls-files | grep -E '(__pycache__/|\.pyc$|(^|/)server\.log$)'
```

O arquivo `server.log` foi gerado localmente para registrar eventos do servidor, mas não estava incluído entre os arquivos rastreados pelo Git. Essa é uma verificação do estado do repositório no momento da consulta, não uma garantia sobre futuras alterações.

## 9. Limitações e observações

- Os testes de comunicação foram executados na própria máquina, usando `127.0.0.1`; não foi comprovado o funcionamento entre computadores físicos diferentes.
- O UDP não confirma individualmente a entrega de `METRICS`. O servidor identifica perdas e duplicações a partir dos números de sequência recebidos.
- Sequências menores ou iguais à última sequência aceita são tratadas como duplicadas ou fora de ordem.
- O servidor remove agentes após receber `BYE` ou detectar inatividade pelo período configurado.
- Os testes com omissão e duplicação intencional de datagramas verificam a lógica de tratamento do sistema, e não a qualidade da rede física.
- Os cenários que não tiveram execução específica registrada permanecem identificados como não realizados.

## 10. Conclusão

Os testes automatizados de protocolo, estado e painel foram concluídos com **26 de 26 aprovações**. O teste automatizado do servidor UDP confirmou o registro de agentes, a recusa de nomes duplicados, o tratamento de mensagens não autorizadas e inválidas, a identificação de perdas e duplicações e as remoções por `BYE` e *timeout*.

O teste com agente real demonstrou a coleta e o envio periódico de CPU e memória e a remoção após `Ctrl+C`. A simulação com dez agentes também foi concluída normalmente, com código de saída `0`, e confirmou os comportamentos especiais de perda, duplicação, registro repetido, datagramas inválidos e timeout.

A documentação de execução foi conferida, e a consulta ao Git não identificou arquivos temporários rastreados. Os resultados apresentados validam os cenários efetivamente testados, sem afirmar aprovação para os casos que não foram executados individualmente.
