
Roteiro de Testes ? Equipe 06
1. Objetivo
Este documento registra os testes realizados no sistema de monitoramento de desempenho da Equipe 06, que utiliza comunicação UDP entre agentes e servidor.

O objetivo é verificar o registro dos agentes, o recebimento das métricas, a identificação de pacotes perdidos e duplicados, a remoção de agentes por mensagem BYE ou por timeout e o tratamento de datagramas inválidos.

Os resultados descritos como Aprovado foram observados nos logs e nas saídas de terminal compartilhadas durante a execução. Os cenários identificados como Não realizado ainda precisam ser executados para completar toda a cobertura solicitada no planejamento da APS.

2. Ambiente de testes
Linguagem: Python.
Protocolo: UDP.
Sistema operacional utilizado: Windows.
Endereço local de teste: 127.0.0.1.
Porta padrão do servidor: 5000.
Intervalo utilizado na simulação: 5 segundos.
Quantidade de agentes na simulação principal: 10.
Duração configurada para a simulação principal: 60 segundos.
Painel desativado durante os testes do servidor, utilizando --no-dashboard.

3. Como executar os testes
3.1. Iniciar o servidor manualmente
Em um terminal, na raiz do repositório, executar:

python -m server.server --no-dashboard
3.2. Executar a simulação com dez agentes
Em outro terminal, na raiz do repositório, executar:

python -m tests.simulate_agents --agents 10 --duration 60 --interval 5 --host 127.0.0.1 --port 5000
3.3. Executar os testes automáticos do servidor
O script tests/check_server.py inicia e encerra o processo do servidor automaticamente. Portanto, não é necessário iniciar outro servidor antes de executar:

python tests/check_server.py

4. Testes automatizados do servidor (tarefa 4.2)
Os testes foram executados com o comando python tests/check_server.py. O script iniciou o servidor em uma porta UDP disponível (porta 58666 na execução registrada), enviou as mensagens de teste e verificou as respostas e os logs do servidor.

Caso	Como executar	Resultado esperado	Resultado obtido
Registro de agente novo	Executar python tests/check_server.py	O servidor responde com OK para um nome ainda não registrado.	Aprovado. O terminal apresentou [OK] Registro de agente novo.
Nome repetido em outro endereço	Executar python tests/check_server.py	O servidor responde com ERROR e motivo name already in use.	Aprovado. O terminal apresentou [OK] Nome repetido foi recusado.
METRICS de agente não registrado	Executar python tests/check_server.py	O servidor responde com ERROR e motivo not registered.	Aprovado. O terminal apresentou [OK] METRICS de agente nao registrado.
Pacotes perdidos	Registrar um agente e enviar as sequências 1, 2 e 5.	O servidor contabiliza dois pacotes perdidos.	Aprovado. O log do servidor registrou 2 pacote(s) perdido(s) e o teste confirmou essa ocorrência.
Mensagem duplicada	Após enviar seq=5, enviar novamente seq=5.	A segunda mensagem é descartada e identificada como duplicada ou fora de ordem.	Aprovado. O log registrou seq 5 duplicado ou fora de ordem.
Remoção por BYE	Registrar um agente, enviar BYE e depois tentar enviar METRICS pelo mesmo socket.	O agente é removido; a métrica posterior recebe ERROR not registered.	Aprovado. O teste confirmou a resposta not registered após o envio de BYE.
Remoção por timeout	Registrar um agente com intervalo de 1 segundo, interromper os envios e aguardar mais de 3 intervalos.	O servidor remove o agente por timeout; uma métrica posterior recebe ERROR not registered.	Aprovado. Após a espera de aproximadamente 4,5 segundos, o teste confirmou ERROR not registered. O log também registrou a remoção por timeout.
Datagramas inválidos	Enviar bytes que não representam JSON válido e, em seguida, tentar registrar outro agente.	O servidor ignora o datagrama inválido, permanece ativo e aceita o novo registro.	Aprovado. O registro posterior foi aceito e o servidor continuou ativo. O log registrou o datagrama inválido.
4.1. Saída observada dos testes automáticos
A execução terminou com a mensagem:

TODOS OS TESTES PASSARAM!
Também foram apresentadas confirmações para o registro novo, nome repetido, agente não registrado, perdas, duplicação, BYE, timeout e datagrama inválido.

5. Simulação com múltiplos agentes (tarefa 4.1)
A simulação principal foi executada com dez agentes, duração configurada de 60 segundos e intervalo de 5 segundos, utilizando os comandos da seção 3.2.

5.1. Resultados observados
Caso	Comportamento esperado	Resultado obtido
Registro dos dez agentes	Os dez agentes devem ser registrados no servidor.	Aprovado. Os agentes agent-1 até agent-10 apareceram no log como registrados.
Agente 3 ? timeout	O agente para de enviar mensagens e não envia BYE; o servidor deve removê-lo por timeout.	Aprovado. O servidor registrou agent-3 ficou sem enviar nada, removendo (timeout).
Agente 5 ? perda de mensagens	O agente deixa de transmitir aproximadamente 30% das mensagens, mas continua incrementando o número de sequência.	Aprovado. O servidor identificou três ocorrências de um pacote perdido, totalizando três pacotes perdidos nas mensagens observadas até os seq 4, 7 e 10.
Agente 7 ? duplicação	O agente retransmite ocasionalmente uma mensagem com o mesmo número de sequência.	Aprovado. O servidor identificou duplicações nos seq 4, 8 e 12, totalizando três mensagens duplicadas.
Agente 8 ? REGISTER repetido	O agente envia REGISTER duas vezes pelo mesmo socket; o servidor aceita o registro repetido sem criar outro agente.	Aprovado quanto à aceitação do registro repetido. O log mostrou o mesmo agente registrado duas vezes com o mesmo endereço e porta. A preservação dos contadores não foi verificada separadamente nessa simulação.
Agente 9 ? datagrama inválido	O agente envia ocasionalmente dados que não são um JSON válido; o servidor não deve cair.	Aprovado. O servidor registrou datagramas inválidos e continuou processando os demais agentes.
Demais agentes ? encerramento	Os agentes normais devem encerrar enviando BYE.	Aprovado. O log registrou a saída por BYE dos agentes agent-1, agent-2, agent-4, agent-5, agent-6, agent-7, agent-8, agent-9 e agent-10.
5.2. Trechos dos logs observados
Exemplos de mensagens registradas pelo servidor durante a simulação:

agent-3 ficou sem enviar nada, removendo (timeout)
agent-5: 1 pacote(s) perdido(s) até o seq 4
agent-5: 1 pacote(s) perdido(s) até o seq 7
agent-5: 1 pacote(s) perdido(s) até o seq 10
agent-7: seq 4 duplicado ou fora de ordem
agent-7: seq 8 duplicado ou fora de ordem
agent-7: seq 12 duplicado ou fora de ordem
datagrama inválido de 127.0.0.1
O endereço e a porta de origem do datagrama inválido podem variar entre execuções.

6. Testes complementares previstos no roteiro da APS
Os casos abaixo fazem parte do roteiro solicitado para a tarefa 4.3. Eles não foram todos demonstrados nos logs e saídas compartilhados até a elaboração deste documento. Por isso, os resultados não foram marcados como aprovados sem evidência.

Caso	Como executar	Resultado esperado	Resultado obtido
Um agente	Iniciar o servidor e executar python -m agent.agent --host 127.0.0.1 --port 5000 --name agente-unico --interval 5.	O agente registra, envia métricas e pode encerrar normalmente com Ctrl+C, enviando BYE.	Não realizado isoladamente / sem resultado registrado. A simulação com dez agentes foi executada, mas não substitui este cenário individual.
Três agentes	Iniciar o servidor e executar três instâncias de agent.agent, cada uma com um nome diferente.	Os três agentes aparecem registrados e enviam métricas simultaneamente.	Não realizado isoladamente / sem resultado registrado.
Ctrl+C no agente	Com um agente individual em execução, pressionar Ctrl+C no terminal do agente.	O agente envia BYE e o servidor o remove imediatamente.	Não realizado isoladamente / sem resultado registrado. A saída por BYE foi observada nos agentes normais do simulador.
Encerramento abrupto (kill -9 ou equivalente no Windows)	Iniciar um agente e encerrar seu processo abruptamente, sem permitir o envio de BYE.	O servidor remove o agente após três vezes o intervalo configurado.	Não realizado isoladamente / sem resultado registrado. O timeout foi comprovado pelo agente 3 da simulação e pelo teste automático, mas não por encerramento forçado de um processo de agente.
Nome repetido	Registrar um nome já utilizado a partir de outro socket/endereço.	O servidor responde ERROR com motivo name already in use.	Aprovado. Cenário verificado pelo teste automático check_server.py.
Servidor reiniciado	Iniciar um agente, reiniciar o servidor e observar as tentativas de registro do agente.	Ao receber ERROR not registered, o agente deve realizar novo REGISTER, preservando o número de sequência.	Não realizado / sem resultado registrado.
Sem servidor	Executar o agente enquanto não há servidor ativo no endereço e porta informados.	O agente realiza até três tentativas de registro, aguarda a resposta e encerra com uma mensagem clara se não houver resposta.	Não realizado / sem resultado registrado.
Simulador com perda	Executar o simulador com dez agentes e observar o agente 5.	O servidor identifica lacunas nos números de sequência do agente 5.	Aprovado. Foram identificados três pacotes perdidos nos eventos observados.
Simulador com duplicados	Executar o simulador com dez agentes e observar o agente 7.	O servidor identifica e descarta mensagens com número de sequência repetido.	Aprovado. Foram identificadas duplicações nos seq 4, 8 e 12.
Mensagens inválidas	Executar o simulador e observar o agente 9; também enviar um datagrama inválido no teste automático.	O servidor registra e ignora o datagrama sem encerrar o processo.	Aprovado. Os logs registraram datagramas inválidos e o servidor continuou funcionando.
Dez agentes	Executar o comando de simulação com --agents 10 --duration 60 --interval 5.	Dez agentes são registrados e os comportamentos especiais aparecem no log.	Aprovado. Os dez registros e os cinco comportamentos especiais foram observados.
Máquinas diferentes	Executar o servidor em um computador e um ou mais agentes em outro computador, usando o IP da máquina servidora.	O agente remoto consegue registrar e enviar métricas ao servidor, respeitando a configuração de rede e firewall.	Não realizado. Não foi registrada uma execução em computadores diferentes. O teste foi feito localmente em 127.0.0.1.
7. Limitações e observações dos testes
Os testes foram realizados localmente, utilizando 127.0.0.1; a comunicação entre computadores diferentes não foi comprovada.
O protocolo não prevê resposta do servidor para uma mensagem METRICS válida. Por isso, a verificação de perdas e duplicações foi feita pelos logs do servidor.
O teste de duplicação considera uma mensagem com número de sequência igual ou inferior ao último número recebido como duplicada ou fora de ordem, conforme a implementação do State.
O agente 3 da simulação não envia BYE, permitindo verificar a remoção por timeout.
O teste automatizado de timeout utiliza intervalo de 1 segundo e aguarda aproximadamente 4,5 segundos antes de verificar a remoção.
A aceitação do REGISTER repetido pelo agente 8 foi observada. A preservação dos contadores em um registro repetido não foi medida separadamente na simulação apresentada.
Os cenários marcados como Não realizado precisam ser executados e atualizados nesta documentação antes de afirmar que toda a lista de testes complementares foi concluída.

8. Conclusão
Os testes automatizados do servidor e a simulação com dez agentes foram executados com sucesso nos cenários registrados neste documento. Foram verificadas a resposta ao registro, a recusa de nome repetido, a rejeição de métricas de agentes não registrados, a identificação de perdas e duplicações, a remoção por BYE, a remoção por timeout e a tolerância a datagramas inválidos.

A simulação também demonstrou os comportamentos especiais dos agentes 3, 5, 7, 8 e 9, além do encerramento por BYE dos demais agentes.

Ainda existem testes complementares sem execução registrada, especialmente os cenários isolados com um e três agentes, Ctrl+C, encerramento abrupto, reinicialização do servidor, ausência de servidor e comunicação entre máquinas diferentes. Esses resultados devem ser atualizados após a execução correspondente.

