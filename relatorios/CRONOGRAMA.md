# Cronograma - os dois tempos

Este documento existe porque são **duas coisas diferentes**, e misturá-las faz mal aos dois
lados:

| | **Tempo A - Cronograma humano** | **Tempo B - Sprint real no tempo de execução de IA** |
|---|---|---|
| **Serve para** | o cliente (Loghanth / Wagner) | Wagner, para saber quando fica pronto |
| **Unidade** | dias úteis | minutos de relógio |
| **O que mede** | trabalho de gente, com dependências externas, aprovações e esperas | tempo de parede de processos de IA rodando em paralelo, sem espera humana |
| **Status** | **proposta, pendente de aprovação** | **medido** nesta máquina, nesta fase - ondas fechadas, total em B.6 |

Os dois números **não são convertíveis entre si**. Um dia útil do Tempo A contém trabalho, espera
por terceiros, aprovação de marco e risco; um minuto do Tempo B é máquina rodando sozinha sem
pausa. Transformar um no outro seria inventar. Estão aqui lado a lado, **separados**, cada um com
sua base de medição declarada.

---

# TEMPO A - Cronograma humano (o que se promete ao cliente)

**Fonte:** `docs/06-plano-e-requisitos-cliente.md` (documento de planejamento, seções 1 a 6).
**Status de aprovação:** todas as linhas da tabela de aprovações do doc 06 estão **Pendentes**.
Nada aqui é prazo aprovado nem compromisso assumido - é proposta.

## A.1 Etapas e prazos

| # | Etapa | Entregável visível para o cliente | Duração | Acumulado | Depende do cliente? |
|---|---|---|---|---|---|
| E1 | Fundação e calibração | Relatório de leitura das amostras reais + escopo do MVP revisado | 3 dias úteis | D+3 | SIM - amostras no D+1 |
| E2 | Motor de extração de PDF | Lote de PDFs reais processados, com planilha de conferência lado a lado | 8 dias úteis | D+11 | SIM - provedor de IA aprovado |
| E3 | Canais WhatsApp e Telegram | Mensagens reais de teste virando registro extraído, com evidências | 6 dias úteis | D+17 | SIM - número WhatsApp verificado |
| E4 | Escrita na planilha e revisão humana | Linhas na planilha oficial + tela de revisão do que ficou em dúvida | 6 dias úteis | D+23 | SIM - planilha alvo e acessos |
| E5 | Homologação e entrada em operação | Rodada de aceite com volume real + treinamento curto | 5 dias úteis | D+28 | SIM - operador disponível |

- **Duração total: 28 dias úteis** (≈5,6 semanas corridas), em trabalho sequencial, a partir de D+0.
- **Com a reserva de risco: até 34 dias úteis** (+6 dias úteis, 20% de 28 arredondado). Usar a
  reserva é decisão conjunta do PO e do cliente.
- `D+0` = primeiro dia útil após o escopo aprovado **e** o checklist da seção 3 do doc 06 completo.

## A.2 Premissas que sustentam esse prazo

Sem estas premissas, os 28 dias úteis **não valem** - e o próprio doc 06 diz qual é a consequência
de cada uma falhar:

| # | Premissa | Consequência se não valer |
|---|---|---|
| P1 | Escopo do MVP aprovado em até 3 dias úteis | D+0 escorrega dia a dia; todo o cronograma desloca junto |
| P2 | Amostras reais até D+1: mínimo 30 PDFs (≥5 fornecedores) e 50 mensagens | E2 não pode ser dimensionada; bloqueia o início |
| P3 | WhatsApp Business verificado no início de E3 | E3 vira caminho crítico |
| P4 | Planilha alvo definida e acessível, com conta de serviço | E4 não inicia; bloqueia o início |
| P5 | Decisor e PO com resposta em até 1 dia útil; aprovação de marco em até 2 | Cada aprovação atrasada empurra a etapa seguinte na mesma medida |
| P6 | Ambientes, endpoint público e credenciais até o fim de E1 | Atraso concentrado em E1 e E3 |
| P7 | Volume declarado; premissa de até 200 documentos/dia e 500 mensagens/dia | Volume muito acima exige revisão de desenho e de prazo |
| P8 | Provedor de IA e nuvem aprovados pelo jurídico/LGPD até o início de E2 | E2 e E3 não iniciam |
| P9 | Jornada de 5 dias úteis/semana, sem feriados no período | 1 feriado = 1 dia útil adicionado |

**Premissas ainda não confirmadas pelo cliente:** todas. Em especial P2, P4, P6, P7 e P8, que
travam o início ou o meio do cronograma.

## A.3 Marcos de aceite

| Marco | Etapa | Quem valida | Status |
|---|---|---|---|
| M1 | E1 | Decisor do cliente + PO | Pendente |
| M2 | E2 | Decisor + operador | Pendente |
| M3 | E3 | Decisor + operador | Pendente |
| M4 | E4 | Operador + PO | Pendente |
| M5 | E5 (aceite final) | Decisor do cliente | Pendente |

Regra do doc 06: **etapa só é aceita com evidência executável** - número conferido contra o
original, não "ficou bom".

## A.4 O que NÃO está contado nos 28 dias úteis

Tempo de espera do cliente (amostras, aprovações, verificação da Meta); fase 2; integração com
ERP/contabilidade além da planilha; migração de histórico; suporte recorrente pós-entrega.

## A.5 Riscos de prazo (do doc 06, com impacto estimado)

R1 verificação da Meta (+5 a 15 du em E3); R2 amostras ruins (+2 a 8 du); R3 layout novo de
fornecedor (+1 a 3 du por lote - **o risco mais provável**); R4 volume acima da premissa (+5 a
10 du); R5 acesso à planilha corporativa (bloqueia E4); R6 extração errada silenciosa (o pior
modo de falha, mitigado pelo desenho de revisão humana); R7 decisor indisponível (+2 du por
ocorrência); R8 provedor de IA fora do ar (+0 a 2 du por evento).

> **Ponto que esta fase altera:** R8 e a premissa P8 (provedor de IA) **saem da conta de risco
> desta entrega**, porque a solução entregue extrai por regras determinísticas, local, sem
> provedor de IA e sem nuvem. Se a extração por IA for reintroduzida depois, R8 e P8 voltam.

---

# TEMPO B - Sprint real no tempo de execução de IA

## B.1 Como foi medido (base declarada)

Não é estimativa: é a diferença entre carimbos de tempo registrados no próprio repositório.

| Fonte | O que fornece |
|---|---|
| `docs/execucao/_ids/sprint_inicio.txt` | O instante de início da sprint de execução, **gravado pelo PO**: `2026-09-19 12:40:46 -0300` |
| `docs/execucao/_ids/run.json` | Criação do run de orquestração: `2026-09-19T15:40:19Z` (= 12:40:19 -03) |
| `docs/execucao/_ids/monitor.log` | Instante de cada `worker_done` das frentes (carimbos em **UTC**, convertidos para -03) |
| `docs/execucao/_ids/dispatch_F1b.json` | Instante do despacho da onda 2 (`dispatched_at`) |
| mtime dos arquivos (`stat`) | Quando cada arquivo de código e cada artefato foi escrito |

**Conversão usada:** os carimbos do `monitor.log` estão em UTC; o horário local é UTC-3.
Exemplo: `15:56:47Z` no log = **12:56:47** no horário de Brasília.

**Limites desta medição, declarados:**
- É tempo de **parede** (relógio de parede), não tempo de trabalho somado. Em cada onda, as frentes
  rodaram **ao mesmo tempo**; o intervalo medido é a duração total do trabalho paralelo, não a soma
  do esforço de cada frente.
- A medição **fecha em 13:20:50**, o último `worker_done` de frente de produção. A onda de
  fechamento desta documentação (F6b, despachada às 13:25:40) abriu depois e **não está incluída** -
  ver B.7.
- Não medi custo de máquina, consumo de tokens nem trabalho humano de supervisão.

## B.2 Fase de planejamento (anterior à execução)

Os seis documentos de planejamento (`docs/01-arquitetura.md` a
`docs/06-plano-e-requisitos-cliente.md`) foram escritos em **2026-09-18**, entre **18:00:34** e
**18:04:49** por mtime - menos de **5 minutos** para a consolidação visível dos arquivos, no dia
anterior à execução. Isso é o registro de escrita dos arquivos; o desenho que os originou precedeu
essa gravação e **não foi medido aqui**.

## B.3 Onda 1 - execução das frentes em paralelo: **16 min 01 s**

Quatro frentes rodaram simultaneamente (núcleo, dados, dados sintéticos, revisão).

| Instante (horário de Brasília) | Marco | Origem |
|---|---|---|
| 12:40:19 | Run de orquestração criado | `run.json` (`15:40:19Z`) |
| **12:40:46** | **Início da sprint de execução** (registrado pelo PO) | `sprint_inicio.txt` |
| 12:47:50 | F4 (revisão humana) concluída | `monitor.log` (`15:47:50Z`) |
| 12:50:11 | F3 (dados sintéticos) concluída | `monitor.log` (`15:50:11Z`) |
| 12:51:23 | F2 (normalização/persistência) concluída | `monitor.log` (`15:51:23Z`) |
| **12:56:47** | **F1 (núcleo) concluída - última frente da onda 1** | `monitor.log` (`15:56:47Z`) |

**Intervalo medido: 12:40:46 -> 12:56:47 = 961 segundos = 16 min 01 s.**

Corroboração por mtime dos arquivos de código entregues na janela: `app/contratos.py` 12:37:52,
`app/revisao.py` 12:45:48, `app/normaliza.py` 12:46:16, `tools/verificar.py` 12:47:37,
`app/persistencia.py` 12:48:44, `tools/gerar_mocks.py` 12:49:30, `app/run.py` 12:52:47,
`app/extracao.py` e `app/ingress.py` 12:54:28 - todos dentro (ou imediatamente antes) do intervalo
acima, consistente com a ordem dos `worker_done`.

Resultado da onda 1, pelas próprias frentes (relatos em `docs/execucao/_ids/relatos_worker_done.md`):
núcleo entregou o pipeline ponta a ponta; dados entregou normalização e persistência;
dados sintéticos entregou os 23 arquivos de material com determinismo byte a byte; revisão entregou
fila e painel.

## B.4 Onda 2 - correção de auditoria, testes e documentação: **9 min 14 s**

Três frentes despachadas em 12:59.

| Instante (BRT) | Marco | Frente | Fonte |
|---|---|---|---|
| **12:59:21** | Despacho da onda 2 (F1b) - **início da onda** | F1b | `dispatch_F1b.json` |
| 12:59:23 | Despacho | F5 - suíte de testes | `dispatch_F5.json` |
| 12:59:24 | Despacho | F6 - documentação (primeira versão) | `dispatch_F6.json` |
| 13:02:03 | Concluída: trilha de auditoria cumulativa (20/40/60) com planilha estável 7/7/7 | F1b | `monitor.log` (`16:02:03Z`) |
| 13:04:55 | Concluída: primeira versão do README e dos relatórios | F6 | `monitor.log` (`16:04:55Z`) |
| 13:08:17 | `status`: 3 defeitos roteados aos donos (F3 x2, F1, F2) | F5 | `monitor.log` (`16:08:17Z`) |
| **13:08:35** | **Concluída: 284 testes escritos, 280 passed / 4 failed** - última frente da onda | F5 | `monitor.log` (`16:08:35Z`) |

**Duração medida: 12:59:21 -> 13:08:35 = 554 segundos = 9 min 14 s.**

A onda 2 entregou duas coisas que mudaram o produto: a trilha de auditoria passou a ser
**cumulativa** (com `rodada_id` e o arquivo `auditoria_rodada_<id>.jsonl`, emendado na seção 4.1 do
contrato) e a suíte de 284 testes passou a existir. Ela **não nasceu verde**: entregou 4 falhas
apontando 3 defeitos reais - ver B.5.

## B.5 Onda 3 - correções apontadas pelo QA: **6 min 14 s**

Antes dos despachos houve **triagem do PO**: entre 13:08:35 (F5 concluída) e 13:14:36 (primeiro
despacho da onda 3) correram **6 min 01 s**, em que os defeitos foram roteados aos donos e as specs
`spec-F2b.md`, `spec-F3b.md` e `spec-F1c.md` foram escritas (mtime 13:14:16-13:14:24).

| Instante (BRT) | Marco | Frente | Fonte |
|---|---|---|---|
| **13:14:36** | Despacho da onda 3 (F3b) - **início da onda** | F3b - corrige D1 e D2 | `dispatch_F3b.json` |
| 13:14:38 | Despacho | F2b - corrige D3 | `dispatch_F2b.json` |
| 13:14:39 | Despacho | F1c - corrige `tem_camada_texto` | `dispatch_F1c.json` |
| 13:17:13 | D3 corrigido: B6 passou a `total_sem_detalhamento` (284 testes verdes, ledger 7 e 7) | F2b | `monitor.log` (`16:17:13Z`) |
| 13:19:46 | D1 (`manifest` da cópia B4) e D2 (OCR restrito a `0/O, 1/l/I, 5/S, 2/Z`) corrigidos | F3b | `monitor.log` (`16:19:46Z`) |
| **13:20:50** | **`tem_camada_texto=False` no caminho de OCR** - última frente desta onda | F1c | `monitor.log` (`16:20:50Z`) |

**Duração medida: 13:14:36 -> 13:20:50 = 374 segundos = 6 min 14 s.**

Corroboração por mtime: `tools/gerar_mocks.py` 13:18:37 e os mocks regenerados até 13:18:42 (efeito
de D1/D2), `app/persistencia.py` 13:15:26 (efeito de D3), `app/ingress.py` 13:15:12 (efeito do
`tem_camada_texto`). O código de produção parou de ser escrito às **13:18:42**; o último carimbo de
conclusão é 13:20:50.

O detalhamento dos 4 defeitos, quem corrigiu cada um e a verificação está em
`relatorios/RELATORIO-ENTREGA.md`, seção 6.3.

## B.6 Total da fase de execução: **40 min 04 s**

| Onda | Início | Fim | Duração | Como foi medida |
|---|---|---|---|---|
| Onda 1 - produto (F1-F4 em paralelo) | 12:40:46 | 12:56:47 | **16 min 01 s** | `sprint_inicio.txt` -> último `worker_done` da onda |
| Intervalo entre ondas | 12:56:47 | 12:59:21 | 2 min 34 s | reaproveitamento dos terminais / despacho da onda 2 |
| Onda 2 - correção + testes + doc (F1b, F5, F6) | 12:59:21 | 13:08:35 | **9 min 14 s** | primeiro despacho da onda -> último `worker_done` |
| Intervalo entre ondas | 13:08:35 | 13:14:36 | 6 min 01 s | **triagem do PO** e escrita das specs de correção |
| Onda 3 - correções do QA (F1c, F2b, F3b) | 13:14:36 | 13:20:50 | **6 min 14 s** | primeiro despacho da onda -> último `worker_done` |
| **TOTAL** | **12:40:46** | **13:20:50** | **40 min 04 s** | `sprint_inicio.txt` -> último `worker_done` do `monitor.log` (`16:20:50Z`) |

Conferência da soma: 16 min 01 s + 2 min 34 s + 9 min 14 s + 6 min 01 s + 6 min 14 s = **40 min 04 s**
(2.404 segundos). As três ondas de trabalho ativo somam **31 min 29 s**; os dois intervalos entre
elas somam **8 min 35 s**.

## B.7 Resumo do Tempo B

| Medida | Valor | Base |
|---|---|---|
| **Tempo total da fase de execução** | **40 min 04 s** | `sprint_inicio.txt` -> último `worker_done` (`monitor.log`) |
| Onda 1 - produto | **16 min 01 s** | 12:40:46 -> 12:56:47 |
| Onda 2 - correção + testes + doc | **9 min 14 s** | 12:59:21 -> 13:08:35 |
| Onda 3 - correções do QA | **6 min 14 s** | 13:14:36 -> 13:20:50 |
| Trabalho ativo somado | **31 min 29 s** | soma das 3 ondas |
| Intervalos (reaproveitamento + triagem do PO) | **8 min 35 s** | 2 min 34 s + 6 min 01 s |
| `worker_done` registrados no `monitor.log` | **10** | F1, F2, F3, F4, F1b, F5, F6, F2b, F3b, F1c |
| Frentes de produção concluídas | **7 de 7** (F1-F5 + 3 correções) | `monitor.log` |
| Defeitos encontrados pelo QA e fechados | **4** | `RELATORIO-ENTREGA.md`, seção 6.3 |
| Testes automatizados | **284** (284 passando) | `pytest -q` executado por esta frente |
| Execução do pipeline (uma rodada) | **0,872 s** | saída real do comando (`README.md`, seção 5) |
| **Fora do total:** onda de fechamento da documentação (F6b) | **não medida** | despachada às 13:25:40, depois do fim da janela |

**O que o número de 40 min 04 s é, e o que ele não é.** É o intervalo de relógio de parede entre o
início registrado da sprint e o último carimbo de conclusão de frente de produção - com trabalho
paralelo nas três ondas. **Não é** a soma do esforço das frentes (que seria maior, e não medida
aqui), **não é** custo de máquina, **não é** tempo de supervisão humana. A onda de fechamento desta
documentação (F6b) foi despachada depois do fim da janela e seu tempo **não está incluído**, porque
no instante desta medição ela não tinha `worker_done` - declarar esse valor seria estimar sem base.

Os 4 min 45 s entre 13:20:50 (última conclusão) e 13:25:40 (despacho da F6b) **não são medíveis** com
as fontes disponíveis: é o intervalo entre o fim das frentes de produção e a decisão do PO de abrir
a onda de fechamento. Não há artefato que registre o que aconteceu nessa janela.

---

## Por que os dois tempos não se misturam

O cronograma humano de 28 dias úteis foi construído com premissas que **não existem** na execução
de IA: espera por amostra do cliente, verificação de conta na Meta, aprovação jurídica, conta de
serviço de planilha, disponibilidade de operador para aceite, feriados. Nada disso foi exercido
nesta fase - a execução de IA não recebeu material do cliente (o material é sintético, gerado por
script) e não teve nenhuma aprovação intermediária.

O que o Tempo B prova é o que ele mede: **quanto o squad leva para produzir, rodando como IA,
quando não há dependência externa.** O que ele **não** prova: que o trabalho de homologação com
dado real do cliente caiba nas mesmas 28 etapas do doc 06, nem que a curva de ajuste para
layouts reais (risco R3) se comporte como o previsto.

Os números dos dois tempos ficam aqui separados, cada um com sua base, para quem precisar
confrontá-los depois - sem que esta fase transforme um no outro por conta própria.
