# 06 - Plano por etapas e requisitos do cliente

Documento de planejamento para o cliente. Foco em **prazo e escopo**.
Nao contem preco, valor de hora nem proposta comercial - orcamento nao foi pedido nesta fase.

Como ler os marcadores deste documento:

- `[PROPOSTA]` = nossa sugestao. Precisa de aprovacao do PO e do cliente antes de virar compromisso.
- `[APROVACAO CLIENTE]` = item que so o cliente pode fornecer ou decidir.
- Toda duracao esta em **dias uteis** e vem acompanhada, na propria linha, da premissa que a sustenta.
- `D+0` = primeiro dia util apos o escopo aprovado e o checklist da secao 3 completo.

Documentos tecnicos que sustentam este plano (mesma pasta `docs/`): `01-arquitetura.md`,
`02-dados-e-ia.md`, `03-qualidade-riscos.md`, `04-devops-ops.md`, `05-ux-revisao-humana.md`.
O cronograma abaixo assume que o desenho desses documentos e o aprovado. Mudanca de desenho
depois da aprovacao entra como mudanca de prazo, seguindo o ritual da secao 4.

---

## 1. Cronograma por etapas

### 1.1 Resumo

| # | Etapa | Entregavel visivel para o cliente | Duracao | Acumulado | Depende do cliente? |
|---|-------|-----------------------------------|---------|-----------|---------------------|
| E1 | Fundacao e calibracao | Relatorio de leitura das amostras reais + escopo do MVP revisado | 3 dias uteis | D+3 | SIM - amostras no D+1 |
| E2 | Motor de extracao de PDF | Lote de PDFs reais processados, com planilha de conferencia lado a lado | 8 dias uteis | D+11 | SIM - provedor de IA aprovado |
| E3 | Canais WhatsApp e Telegram | Mensagens reais de teste virando registro extraido, com evidencias do fluxo | 6 dias uteis | D+17 | SIM - numero WhatsApp verificado |
| E4 | Escrita na planilha e revisao humana | Linhas na planilha oficial + tela de revisao do que ficou em duvida | 6 dias uteis | D+23 | SIM - planilha alvo e acessos |
| E5 | Homologacao e entrada em operacao | Rodada de aceite com volume real + treinamento curto do operador | 5 dias uteis | D+28 | SIM - operador disponivel |

**Duracao total: 28 dias uteis** (5,6 semanas corridas), em trabalho sequencial, contados a
partir de D+0. Com a reserva de risco opcional descrita na secao 6 (+6 dias uteis, premissa:
20% do total arredondado), o compromisso passa a **ate 34 dias uteis**. As premissas que
sustentam esse numero estao em 1.3.

### 1.2 Detalhamento por etapa

**E1 - Fundacao e calibracao (3 dias uteis) - [PROPOSTA]**
- Objetivo: ler documentos e mensagens reais do cliente, medir a variacao de formatos e
  confirmar o escopo do MVP com base em dado real, nao em suposicao.
- Entregavel visivel: relatorio curto (2 a 4 paginas) com o que existe hoje, quantos
  formatos/fornecedores diferentes aparecem, quais campos realmente existem em cada um e
  uma proposta de escopo priorizado revisada.
- Premissa de prazo: as amostras da secao 3 chegam ate o D+1 (P2). Sem elas, a etapa vira
  bloqueio, nao estimativa.
- Trabalho paralelo: subir o ambiente e o endpoint publico de recebimento (P6).

**E2 - Motor de extracao de PDF (8 dias uteis) - [PROPOSTA]**
- Objetivo: extrair numero do pedido, valores, datas e itens dos PDFs de nota fiscal e pedido,
  com tratamento separado de PDF digital e PDF escaneado, e com regra de confianca por campo.
- Entregavel visivel: os PDFs enviados pelo cliente processados de ponta a ponta e uma planilha
  de conferencia com o que foi extraido ao lado do valor esperado.
- Premissa de prazo: escopo de campos aprovado em E1; provedor de IA aprovado pelo
  juridico/LGPD do cliente ate o inicio desta etapa (P8). Cada rodada de reprocessamento de
  amostra causada por correcao de regra depois do inicio consome 1 dia util.

**E3 - Canais WhatsApp e Telegram (6 dias uteis) - [PROPOSTA]**
- Objetivo: receber mensagens dos dois canais, identificar pedido, valores, datas e itens
  nelas, e tratar mensagem ambigua ou sem valor como excecao - nao como valor inventado.
- Entregavel visivel: demonstracao ao vivo em que mensagens reais de teste enviadas pelo
  cliente aparecem no sistema com os campos extraidos, e uma lista de mensagens que foram
  corretamente enviadas para revisao humana em vez de aceitas automaticamente.
- Premissa de prazo: numero de WhatsApp Business **ja verificado** no inicio da etapa (P3).
  Se a verificacao estiver em curso, esta etapa sera a primeira a escorregar.
- Nota: o Telegram nao depende de verificacao de conta empresarial e pode ser entregue antes.

**E4 - Escrita na planilha e revisao humana (6 dias uteis) - [PROPOSTA]**
- Objetivo: escrever as linhas na planilha de controle financeiro de forma idempotente (o
  mesmo documento reenviado nao duplica linha) e entregar a tela de revisao do que ficou
  abaixo do limite de confianca.
- Entregavel visivel: linhas reais aparecendo na planilha oficial do cliente, mais a tela de
  pendencias em que o operador confere, corrige e aprova.
- Premissa de prazo: planilha alvo real (arquivo existente, com os acessos da secao 3)
  disponivel ate o inicio da etapa (P4). Planilha nova, criada por nos, nao substitui a do
  cliente e desloca esta etapa para a discussao de escopo.

**E5 - Homologacao e entrada em operacao (5 dias uteis) - [PROPOSTA]**
- Objetivo: rodar com volume real por alguns dias, ajustar o que aparecer e deixar o operador
  treinado para usar o fluxo sem nos.
- Entregavel visivel: rodada de aceite formal sobre a planilha gerada, lista de pendencias
  resolvidas e um treinamento curto (sessao de 60 minutos) com material de apoio.
- Premissa de prazo: operador e validador do cliente disponiveis pelo menos 2 horas por dia
  nos 5 dias uteis da etapa (P5). Ausencia do validador nesta janela e a causa mais comum de
  etapa nao fechar.

### 1.3 Premissas que sustentam o prazo

| # | Premissa | Consequencia se nao valer |
|---|----------|---------------------------|
| P1 | Escopo do MVP aprovado em ate **3 dias uteis** apos o envio desta proposta. | D+0 escorrega dia a dia; todo o cronograma desloca junto. |
| P2 | Amostras reais disponiveis ate D+1: **minimo 30 PDFs** (mistura de digital e escaneado) de **pelo menos 5 fornecedores distintos** e **50 mensagens reais** anonimizadas. | E2 nao pode ser dimensionada nem estimada com honestidade. Bloqueia o inicio. |
| P3 | Numero de WhatsApp Business **verificado** no inicio de E3, ou verificacao ja iniciada junto a Meta no D+0. | E3 vira o caminho critico. Ver secao 5. |
| P4 | Planilha alvo definida e acessivel (Google Sheets ou Excel/OneDrive), com conta de servico autorizada. | E4 nao inicia. Bloqueia o inicio. |
| P5 | Um decisor do cliente e um PO interno disponiveis, com resposta em ate **1 dia util**; aprovacao de cada marco em ate **2 dias uteis**. | Cada aprovacao atrasada empurra a etapa seguinte na mesma quantidade. |
| P6 | Ambientes, endpoint publico e credenciais entregues ate o fim de E1. | Atraso concentrado em E1 e E3. |
| P7 | Volume de operacao declarado pelo cliente. Como premissa de dimensionamento do MVP, assumimos **ate 200 documentos/dia e ate 500 mensagens/dia** - numero a confirmar, nao medido por nos. | Volume muito acima disso exige revisao de desenho e de prazo (nao estimado aqui). |
| P8 | Provedor de IA e uso de nuvem aprovados pelo juridico/LGPD do cliente ate o inicio de E2. | E2 e E3 nao iniciam. |
| P9 | Jornada de 5 dias uteis por semana e ausencia de feriados nacionais no periodo. Feriados e ferias do time sao somados ao prazo. | 1 feriado = 1 dia util adicionado ao total. |

Nao sustentam o prazo e por isso nao foram usadas: qualquer numero de preco, de volume de
clientes futuro, de escopo de fase 2 ou de equipe maior do que a atual.

### 1.4 O que NAO esta contado nos 28 dias uteis

- Tempo de espera do cliente (envio de amostras, aprovacoes, verificacao da Meta).
- Fase 2 (relatorios avancados, app proprio, multiusuario com perfis, conciliacao contabil).
- Integracao com ERP/contabilidade alem da planilha.
- Migracao de dados historicos de periodos anteriores.
- Suporte recorrente pos-entrega.

### 1.5 Escopo priorizado - [PROPOSTA, requer aprovacao do PO e do cliente]

- **MVP (E1 a E5):** PDF de nota fiscal e pedido (digital e escaneado), WhatsApp, Telegram,
  extracao de numero do pedido, valores, datas e itens, validacao de confianca, revisao humana
  do que ficou em duvida, escrita idempotente na planilha.
- **Fase 2 (nao estimada aqui):** relatorios e dashboards, alertas proativos, conciliacao entre
  nota e pedido, multiusuario com perfis, app proprio.
- **Fora de escopo ate segunda ordem:** substituir o sistema financeiro atual, emissao de nota,
  contabilidade, cobranca nos canais e qualquer escrita na planilha sem registro de auditoria.

Este escopo e uma proposta: itens que o cliente quiser mover entre MVP e fase 2 mudam o prazo
e precisam de aprovacao conjunta do PO e do cliente.

---

## 2. Marcos de aceite

O que o cliente consegue verificar sozinho no fim de cada etapa. Aprovacao de cada marco segue
a secao 4.

| Marco | Etapa | O que o cliente verifica | Quem valida |
|-------|-------|--------------------------|-------------|
| M1 | E1 | Abre o relatorio e confere se os formatos e campos listados correspondem ao que ele recebe na pratica. Confirma que o escopo priorizado de 1.5 e o dele. | Decisor do cliente + PO |
| M2 | E2 | Pega a planilha de conferencia, escolhe 10 PDFs a esmo, compara campo a campo com o documento original e conta quantos valores divergem. | Decisor + operador |
| M3 | E3 | Envia ele mesmo 5 mensagens de teste (2 ambigua, 1 sem valor, 1 com pedido completo, 1 duplicada) e confere o resultado de cada uma, incluindo as que foram para revisao. | Decisor + operador |
| M4 | E4 | Abre a planilha oficial e confere que as linhas existem, que reenviar o mesmo documento nao duplica e que a tela de revisao mostra documento e campo extraido lado a lado. | Operador + PO |
| M5 | E5 | Roda o fluxo sozinho por um dia util, com apoio, e assina a rodada de aceite sobre a planilha gerada nesse dia. | Decisor do cliente |

Regra geral de aceite: etapa so e aceita com evidencia executavel. "Ficou bom" nao e aceite;
numero conferido contra o original e aceite.

---

## 3. Checklist do que precisamos do cliente para comecar

`Trava o inicio` = sem isso, D+0 nao existe e o cronograma nao comeca a contar.

| # | Item | Quem entrega no cliente | Trava o inicio? | Trava qual etapa |
|---|------|-------------------------|-----------------|------------------|
| 1 | Amostras de PDFs: 30 arquivos reais, incluindo pelo menos 3 escaneados de baixa qualidade | Financeiro / administrativo | **SIM** | E2 |
| 2 | Amostras de mensagens: 50 mensagens reais (WhatsApp e Telegram) com dados pessoais anonimizados | Comercial / atendimento | **SIM** | E3 |
| 3 | Planilha alvo: arquivo real de controle financeiro (Google Sheets ou Excel/OneDrive) | Financeiro | **SIM** | E4 |
| 4 | Definicao dos campos obrigatorios e de quem e o dono da planilha | Decisor | **SIM** | E1/E2 |
| 5 | Contato decisor (nome, e-mail, telefone) e contato tecnico/operador do dia a dia | Decisor | **SIM** | Todos |
| 6 | Numero de WhatsApp e acesso ao Business Manager / processo de verificacao iniciado junto a Meta | TI / marketing | **SIM** (E3) | E3 |
| 7 | Bot do Telegram criado e token entregue por canal seguro | TI | NAO (fazemos juntos) | E3 |
| 8 | Credencial ou conta de servico para escrita na planilha | TI / admin Google Workspace ou Microsoft 365 | **SIM** | E4 |
| 9 | Credencial do provedor de IA aprovado (chave de API entregue por canal seguro, nunca por e-mail em texto) | TI / compras | **SIM** (E2) | E2/E3 |
| 10 | Confirmacao de uso de nuvem e dado financeiro pelo juridico/LGPD | Juridico | **SIM** (E2) | E2 |
| 11 | Volume real de operacao: documentos/dia e mensagens/dia, com media e pico | Operacao | **SIM** (dimensionamento) | E1 |
| 12 | Endpoint publico, dominio e regras de firewall para receber webhook | TI | NAO (E1) | E3 |
| 13 | Agendas: ferias, feriados e janelas de congelamento no periodo | Decisor | NAO | Todos |

**Leitura direta:** os itens 1, 2, 3, 5, 6, 8, 9, 10 e 11 travam o inicio. Itens 4 e 7 podem
ser resolvidos em E1 sem parar o trabalho, mas item 4 sem resposta faz E1 entregar um escopo
que o cliente nao reconhece.

Regra de seguranca: chaves, tokens e senhas sao entregues por canal seguro e nunca ficam em
texto no repositorio nem em mensagem de grupo.

---

## 4. Ritual de comunicacao

- **Canal unico:** grupo do projeto no WhatsApp ou Telegram (a definir pelo cliente, `[APROVACAO
  CLIENTE]`). Nada de decisao por comentario em documento ou por conversa paralela.
- **Atualizacao assincrona:** resumo curto no grupo 2 vezes por semana (segunda e quinta), em
  5 linhas, ate 18h: o que foi feito, o que vem, o que esta travado, o que precisamos.
- **Checkpoint semanal:** reuniao de 30 minutos, dia e hora fixos (`[APROVACAO CLIENTE]`), com
  pauta fixa: bloqueios, decisoes pendentes, riscos da secao 6, e aceite de marcos vencidos.
- **Demonstracao de fim de etapa:** sessao de 45 minutos ao fechar cada etapa, apresentando o
  entregavel da tabela 1.1 sobre dado real do cliente. E nesta sessao que o marco da secao 2
  e aceito.
- **Status de 1 pagina** quinzenal para o decisor que nao participa do dia a dia.
- **Bloqueio:** escalada explicita em ate 1 dia util, com a frase "isto esta travando o trabalho
  X e o impacto estimado e N dias uteis".
- **Regra de silencio:** sem resposta do decisor em 2 dias uteis sobre um item marcado como
  decisao pendente, o item entra no canal como risco de prazo e o relogio da etapa que depende
  dele para de contar.

**Quem aprova o que:**

| Marco | Aprovacao tecnica | Aprovacao de negocio | Efeito da aprovacao |
|-------|-------------------|----------------------|---------------------|
| Escopo priorizado (1.5) | PO | Decisor do cliente | Libera D+0 e o cronograma de 28 dias uteis |
| M1 a M4 | PO | Operador e/ou decisor | Libera o inicio da etapa seguinte |
| M5 (aceite final) | PO | Decisor do cliente | Encerra o MVP e habilita a fase 2 |
| Mudanca de escopo ou prazo | PO | Decisor do cliente | Recongela o cronograma e a reserva de risco |

Nenhuma etapa comeca sem a aprovacao do marco anterior. Se o cliente quiser comecar a proxima
etapa antes do aceite, isso e uma decisao explicita do decisor e assume o risco de retrabalho.

---

## 5. Dependencias externas que podem atrasar o projeto

| # | Dependencia | Por que atrasa | Espera tipica (premissa) | Onde provavelmente impacta |
|---|-------------|----------------|--------------------------|----------------------------|
| D1 | Verificacao da conta WhatsApp Business junto a Meta | Processo e analise sao da Meta; nao controlamos fila nem pedido de documentacao complementar | 2 a 15 dias uteis, podendo passar disso se a Meta pedir mais documento | Caminho critico de E3 |
| D2 | Limites e cotas da API do provedor de IA (rate limit, tokens/dia, fila em horario de pico) | Volume acima do plano causa espera ou reprocessamento | Ajuste de cota em 1 a 3 dias uteis apos pedido | E2 a E5 |
| D3 | Aprovacao do provedor de IA e do uso de nuvem pelo juridico/LGPD do cliente | Depende de area que nao esta no dia a dia do projeto | 3 a 10 dias uteis | Bloqueia E2 |
| D4 | Acesso a planilha corporativa (conta de servico, politica de compartilhamento, admin de TI) | Liberacao costuma passar por TI terceirizada | 2 a 7 dias uteis | Bloqueia E4 |
| D5 | Verificacao de dominio, endpoint publico, firewall e certificado | Liberacao de rede em empresa com TI terceirizada | 2 a 10 dias uteis | E3 |
| D6 | Qualidade dos PDFs escaneados fornecidos | Scan ruim reduz acuracia e exige mais calibracao | Nao e atraso externo; e esforco extra em E2 (1 a 3 dias uteis) | E2 |
| D7 | Criacao/liberacao da bot do Telegram e do token de API | Baixo risco, mas depende de alguem com acesso | 0 a 2 dias uteis | E3 |
| D8 | Feriados, ferias e janela de fechamento financeiro do cliente | Reduzem disponibilidade de validador | 1 dia util por feriado | Todas |

**Acao preventiva recomendada:** iniciar D1 (Meta) e D3 (juridico) no D+0, antes mesmo de
E1 terminar, porque sao as duas que nao dependem de nos e tem a maior variacao.

---

## 6. Riscos de prazo com impacto estimado

| # | Risco | Probabilidade | Impacto estimado | Sinal de que esta acontecendo | O que fazer |
|---|-------|---------------|------------------|-------------------------------|-------------|
| R1 | Verificacao da Meta demora mais que o previsto | Media | +5 a 15 dias uteis em E3 | Sem retorno da Meta no 5o dia util | Entregar Telegram primeiro, manter E3 aberta so para WhatsApp e renegociar o marco M3; E4 pode adiantar se a planilha estiver acessivel |
| R2 | Amostras chegam incompletas, velhas ou pouco variadas | Alta | +2 a 8 dias uteis | Menos de 5 fornecedores distintos nas amostras | Pausar E2, refazer a coleta com o cliente e tratar o atraso como mudanca de prazo; nao calibrar com amostra pobre |
| R3 | Layout novo de fornecedor nao previsto | Alta (e esperado) | +1 a 3 dias uteis por lote novo | Campo extraido vazio ou divergente em PDF de fornecedor novo | Fluxo de excecao obrigatorio: nada entra em silencio, entra em revisao; calibrar o novo layout em ate 3 dias uteis |
| R4 | Volume real muito acima da premissa de P7 | Media | +5 a 10 dias uteis | Fila crescendo ou estourando cota da API | Ajustar cota, priorizar fila e, se persistir, rediscutir escopo do MVP com o PO e o cliente |
| R5 | Acesso a planilha corporativa nao liberado | Media | Bloqueia E4, +3 a 10 dias uteis | Sem conta de servico no inicio de E4 | Escrever em planilha espelho no ambiente de teste para validar a logica e trocar para a oficial quando liberar |
| R6 | Extracao errada silenciosa (valor entra na planilha sem ninguem notar) | Baixa a media, impacto alto | Nao e prazo, mas e o pior modo de falha | Divergencia de total ou de campo critico no aceite | Nenhum valor acima do limite de confianca entra sem aprovacao humana; soma de itens contra total, CNPJ e data plausivel como validacao automatica |
| R7 | Decisor indisponivel para aprovar marco | Media | +2 dias uteis por ocorrencia | Marco vencido sem resposta em 2 dias uteis | Aplicar a regra de silencio da secao 4 e reatribuir a aprovacao ao PO com registro |
| R8 | Provedor de IA fora do ar ou com mudanca de preco/limite | Baixa a media | +0 a 2 dias uteis por evento | Falha repetida de chamada de API | Fila com retry e backoff; reprocessamento automatico quando voltar; manter a opcao de um segundo provedor homologado no desenho |

**Reserva de risco:** 6 dias uteis (20% de 28, arredondado). Se nenhum risco relevante se
materializar, a entrega fecha em 28 dias uteis; a reserva evita que um risco medio vire
descumprimento de prazo. Usar a reserva e decisao conjunta do PO e do cliente.

---

## 7. Pontos em aberto para o cliente decidir

Maximo de 10. Todas precisam de resposta antes de D+0, ou serao registradas como risco de
prazo na secao 6.

1. **Aprovacao do escopo priorizado (1.5):** aprova como esta, quer mover algum item de MVP
   para fase 2, ou quer incluir algo agora? (aprovar / mover item X / incluir item Y)
2. **Canal de WhatsApp:** e um numero novo de WhatsApp Business, ou ja existe um numero em uso
   que sera migrado para a API? O numero atual ja passou por verificacao na Meta?
3. **Volume real:** quantos documentos e quantas mensagens por dia, em media e no pico?
   (a confirmar com numero, nao com estimativa)
4. **Destino da planilha:** Google Sheets, Excel/OneDrive, ou CSV em pasta sincronizada?
   Quem e o dono do arquivo e quem mais escreve nele hoje?
5. **A quem pertence a decisao de aceite:** uma pessoa ou um comite? Qual o nome e o prazo
   maximo de resposta que ela assume (sugerimos 2 dias uteis)?
6. **Tratamento de dado pessoal:** as mensagens de WhatsApp/Telegram podem ser enviadas a um
   provedor de IA na nuvem? Ha restricao do juridico quanto a PII em documento financeiro?
7. **Comportamento em caso de duvida:** quando o valor extraido divergir, preferimos registrar
   a linha e marcar para revisao, ou simplesmente nao escrever e notificar? (recomendamos
   registrar em area de revisao, nunca na planilha final sem aprovacao)
8. **Idempotencia:** se o mesmo pedido chegar em PDF e tambem por mensagem, deve virar uma
   linha so (documento principal) ou duas linhas distintas? Qual e a regra de ouro?
9. **Historico:** o cliente quer recuperar notas e pedidos de meses anteriores, ou comeca a
   partir do go-live? (isso define se ha trabalho de migracao, nao estimado aqui)
10. **Fase 2:** qual e a proxima dor depois deste MVP, para priorizarmos com dado real em vez
    de suposicao? (relatorios / conciliacao / alertas / multiusuario / outro)

---

## Aprovacoes necessarias

| Item | Aprova por | Status |
|------|------------|--------|
| Escopo priorizado (1.5) | PO + decisor do cliente | Pendente |
| Cronograma de 28 dias uteis e premissas P1 a P9 | PO + decisor do cliente | Pendente |
| Reserva de risco de 6 dias uteis | PO + decisor do cliente | Pendente |
| Checklist da secao 3 como condicao de inicio | Decisor do cliente | Pendente |
| Ritual de comunicacao (4) e responsaveis de aprovacao | PO + decisor do cliente | Pendente |
