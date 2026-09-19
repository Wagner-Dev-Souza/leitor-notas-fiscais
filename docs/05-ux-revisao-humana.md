# 05 - UX, Revisao Humana e Interface do MVP

Escopo: experiencia de quem revisa o que a IA extraiu de PDFs (notas/pedidos) e de mensagens de
WhatsApp/Telegram antes de virar linha na planilha de controle financeiro.

Premissas (P). Nenhum preco, prazo, volume ou escopo foi inventado - o que falta esta na secao 8.
P1: o revisor e uma pessoa de financeiro, nao tecnica, e ja usa a planilha hoje. P2: o MVP e uma
aplicacao web unica, sem app proprio. P3: volume diario, limiares de valor e quantidade de revisores
sao desconhecidos. P4: a planilha continua sendo o artefato visivel do financeiro; o sistema escreve
nela.

---

## 1. Principio de desenho: por que a revisao humana e obrigatoria

**Regra de ouro: a planilha e o livro-caixa. Ela so recebe linha que um humano aprovou.**

Erro de valor monetario e o pior modo de falha do projeto porque e **silencioso**: o numero errado
entra, soma com os outros, contamina o relatorio de caixa e aparece semanas depois na conciliacao,
quando o rastro esfriou. Erro visivel (documento travado, falha de escrita) custa minutos; erro
invisivel custa a confianca no projeto inteiro.

A IA trabalha com probabilidade, nao com garantia: PDF escaneado, layout de fornecedor novo, nota
com desconto/frete, mensagem de pedido sem valor explicito. Como o custo do erro e assimetrico, o
desenho assume que **a extracao e uma proposta, nao um fato**: o humano confirma o que e barato
confirmar e digita apenas o que a IA nao conseguiu ler.

### 1.1 Semaforo de confianca (unidade de decisao)

| Faixa | Cor | Acao |
|---|---|---|
| Confianca alta e todas as validacoes passam | Verde | Elegivel a aprovacao em lote (tela 4) |
| Confianca media OU 1 validacao falha | Ambar | Fila de revisao individual |
| Confianca baixa, campo obrigatorio ausente, conflito grave | Vermelho | Fila, campo destacado, sem lote |

Os numeros de corte de cada faixa vem do score definido na spec de dados/IA (02) e do aceite do
cliente (secao 8, pergunta 1). Nada aqui presume o valor.

### 1.2 O que NUNCA e escrito na planilha sem aprovacao humana explicita

Valor total, valor unitario e quantidade (qualquer numero que vire dinheiro); data de emissao e de
vencimento; emitente/CNPJ e chave de acesso da NF; criacao de linha nova, alteracao de linha ja
escrita e qualquer exclusao; e documento com baixa confianca, conflito de validacao ou suspeita de
duplicidade. Documento pendente ha muito tempo tambem nao entra: **timeout nunca aprova** -
pendencia velha continua pendente.

### 1.3 O que pode ser automatico (so com autorizacao do cliente)

Metadados de rastreio, nunca valores de negocio: ID interno, origem (WhatsApp/Telegram/PDF/e-mail),
data/hora de recebimento, nome e hash do arquivo, status da fila. Aprovacao automatica de grupo de
baixo risco, se autorizada, fica restrita a documentos verdes de fornecedor ja conhecido (secao 8,
pergunta 1).

### 1.4 Tres principios de interface que sustentam isso

**Explicabilidade**: todo campo mostra de onde veio (pagina do PDF ou trecho da mensagem) - o revisor
valida olhando, nao digitando. **Reversibilidade**: toda escrita tem origem registrada (ID de
revisao), autor e horario, e e desfazivel por operacao de compensacao; a planilha nao e editada a mao
pelo sistema. **Nao decidir pelo usuario**: o sistema nunca aprova, nunca resolve duplicidade em
silencio e nunca esconde campo que falhou.

---

## 2. Fluxo de revisao humana ponta a ponta

    RECEBIDO -> EXTRAIDO -> EM_REVISAO -> APROVADO -> ESCRITO
                                     \-> REJEITADO
                \-> DUPLICADO (sai da fila, consultavel)
                \-> ERRO_EXTRACAO (entra na fila como vermelho)
    APROVADO -> ESCRITA_FALHOU (volta para a fila com alerta)

1. **Chegada**: PDF ou mensagem entra pela ingestao (WhatsApp/Telegram/upload/e-mail).
2. **Deduplicacao**: valida chave de acesso, hash do arquivo e numero do pedido; repetido vai para
   DUPLICADO, sem gerar pendencia nova, e fica registrado para auditoria.
3. **Extracao**: o extrator produz campos + score por campo + trecho de origem.
4. **Validacao**: soma dos itens vs total, CNPJ, datas plausiveis, campo obrigatorio, formato de
   moeda/data. Falha nao bloqueia: rebaixa para ambar/vermelho e mostra o motivo em linguagem de
   negocio ("a soma dos itens nao bate com o total").
5. **Fila**: documento entra no painel (tela 1), ordenado por risco e depois por antiguidade.
6. **Aviso**: notificacao agrupada (secao 4); o sistema nao interrompe por documento individual.
7. **Revisao**: abre o detalhe (tela 2), confere o original lado a lado, corrige o necessario (tela
   3) e le os motivos das pendencias.
8. **Decisao**: Aprovar, Rejeitar (motivo obrigatorio) ou "deixar para depois" (sem penalidade, mas o
   documento envelhece e aparece no resumo diario).
9. **Pre-escrita**: revalida duplicidade e confere se o documento mudou desde a aprovacao; se mudou,
   volta para a fila em vez de escrever.
10. **Escrita**: o escritor grava a linha e devolve o ID/linha criada.
11. **Registro**: historico com extraido vs final, campo por campo, autor, horario e ID da linha.
12. **Retorno**: sucesso sai da fila; falha de escrita volta para a fila com alerta imediato.

Regras de comportamento:

- **Toda edicao e auditada** (campo, valor extraido, valor final, autor, timestamp); o valor original
  nunca e apagado - depois o revisor precisa poder ver "a IA dizia 1.234,00".
- **Rejeicao exige motivo** de lista curta: nao e documento financeiro / duplicado / valor ilegivel
  / nao e do cliente / outro (texto livre); rejeitar sem motivo nao conclui a acao.
- **Reabertura** livre antes da escrita; depois dela, so por correcao registrada (nunca editar celula
  na mao), gerando novo registro no historico.
- **Concorrencia**: lock leve ("em revisao por Fulano, desde 10:12"), sem impedir leitura por outro.
- **Aprovar nao e escrever**: a escrita pode falhar depois; a interface mostra o estado real
  (aprovado, escrito, falha) e nunca assume.

---

## 3. Wireframes textuais das telas do MVP

Cinco telas e um modal - e so isso. Descricao elemento por elemento.

### Tela 1 - Painel de pendencias (home)

Objetivo: responder em 5 segundos "tem trabalho meu hoje, e qual e o pior caso?".

    [Logo]  Pendencias            Resumo diario (sino)        [Fulano] [Sair]
      PENDENTES 27    |    ALTO RISCO 4    |    MAIS ANTIGA ha 2 dias
    Origem: [Todos][PDF][WhatsApp][Telegram]   Motivo: [Total][Valor][CNPJ]...
    Buscar: [n.pedido / CNPJ / valor]                     Ordenar: [Risco v]
    -------------------------------------------------------------------------
    [x] Tipo   | Emitente      | N.pedido | Valor      | Conf | Motivo pendencia
    [ ] NF     | Acme LTDA     | 4412     | R$1.234,00 |  62% | Soma nao bate
    [ ] Pedido | Distrib. Beta | 4418     | R$  890,00 |  91% | Sem data venc.
    [ ] Msg    | ---           | 4420     | R$  150,00 |  35% | Valor ilegivel
                                                          [ Revisar > ]
    -------------------------------------------------------------------------
    3 selecionados  [Aprovar selecionados] [Atribuir]   Pagina 1 de 4  < >

| Elemento | Onde | Para que serve |
|---|---|---|
| Cabecalho fixo | Topo | Nome do produto, contador de pendencias, botao de resumo diario e usuario - a rolagem e longa, o contexto fica visivel |
| 3 cards de KPI | Sob o cabecalho | Pendentes totais, alto risco (vermelhos) e idade da mais antiga: a meta diaria e fila zero; sem graficos no MVP |
| Chips de origem | Linha de filtros | PDF, WhatsApp, Telegram, e-mail; um clique, sem menu |
| Chips de motivo | Linha de filtros | Total divergente, CNPJ invalido, data implausivel, campo obrigatorio ausente, duplicidade suspeita - e o filtro mais usado ("so o que esta errado de valor") |
| Busca | Linha de filtros | Numero do pedido, CNPJ, emitente ou valor: acha o documento na hora quando alguem liga cobrando |
| Ordenacao | Canto da linha de filtros | Risco alto primeiro, depois o mais antigo - nunca so por data de chegada |
| Lista de pendencias | Corpo | Checkbox (para o lote), tipo, emitente, numero do pedido, valor, badge de confianca (numero + cor), motivo da pendencia em uma linha e botao "Revisar"; o motivo e o texto mais importante da tela, diz o que procurar no documento |
| Faixas de aviso | Topo da lista | Pendencia acima de X dias (X combinado com o cliente) e falha de escrita na planilha |
| Rodape de acoes | Rodape | Contador de selecionados, "Aprovar selecionados" (habilitado so se todos forem elegiveis - tela 4) e "Atribuir" |
| Estado vazio | Corpo | "Nada pendente. Ultima atualizacao 14:03." - fila vazia e sistema quebrado precisam ser distinguiveis a olho nu |
| Fora de escopo aqui | - | Somatorio financeiro da fila, graficos, exportacao, cadastro de fornecedor e configuracao de regras |

### Tela 2 - Detalhe do documento (extraido ao lado do original)

Objetivo: validar olhando, nao digitando. Esta e a tela que decide se o projeto da certo.

    < Voltar   NF 4412 - Acme LTDA       [Em revisao por Fulano]   [Pendente v]
    -------------------------------+-------------------------------------
    ORIGINAL [PDF] [Mensagem] [Arq] | CAMPOS EXTRAIDOS
    +----------------------------+ | Campo           | Valor     |Conf|Ori
    | pagina 1 de 2  [<][>][zoom] | | N. pedido       | 4412      | 98%|p.1
    |  ..trecho realcado em      | | Emitente/CNPJ   | Acme LTDA | 95%|p.1
    |    amarelo ao clicar no    | | Data emissao    | 02/03/26  | 90%|p.1
    |    campo a direita..       | | Data vencimento | 02/04/26  | 71%|p.1
    +----------------------------+ | Valor total   ! | R$1.234,00| 62%|p.1
                                   | Itens           | 2 itens   | 88%|p.1
                                   | Forma pagamento | Boleto    | 80%|p.1
                                   | Chave da NF     | 3526...   | 99%|p.1
                                   | [!] Soma dos itens R$1.434,00 difere do
                                   |     total em R$200,00
    -------------------------------+-------------------------------------
    Observacao do revisor: [________________________________________]
    [Aprovar]  [Rejeitar]      [Salvar e proximo]  [Salvar e voltar]

| Elemento | Onde | Para que serve |
|---|---|---|
| Barra superior | Topo | Voltar para a fila, identificacao do documento, aviso de lock ("em revisao por X") e status atual |
| Abas do original | Coluna esquerda | PDF renderizado / mensagem bruta (remetente, data/hora, texto integral, anexo) / arquivo para download |
| Navegacao do original | Coluna esquerda | Trocar de pagina e aplicar zoom |
| Realce do trecho de origem | Coluna esquerda | Clicar no campo da direita acende o trecho no documento: e o mecanismo antierro mais importante da tela, porque o revisor ve o numero no documento, nao o numero da IA |
| Tabela de campos extraidos | Coluna direita | Uma linha por campo com rotulo, valor extraido, confianca %, origem (pagina/trecho/mensagem) e icone de status; campo com falha leva marcador `!` e fundo ambar/vermelho, nunca so cor diferente |
| Bloco de itens | Coluna direita | Descricao, quantidade e valor unitario, com editar/adicionar/remover: itens sao a origem mais comum de divergencia de soma |
| Alerta de soma | Sob a tabela de campos | Total dos itens vs total do documento, com a diferenca em reais, em linguagem de negocio |
| Preview da linha | Link sob a tabela | "Ver a linha que sera escrita na planilha", com colunas e valores finais - mata a surpresa de "onde isso foi parar" |
| Observacao do revisor | Acima da barra de decisao | Texto livre que vai para o historico; usado em casos de borda |
| Barra de decisao fixa | Rodape | Aprovar (primario), Rejeitar (pede motivo), Salvar e proximo, Salvar e voltar; fixa porque decidir nunca pode exigir rolagem |
| No celular | - | Colunas empilham (original primeiro) e a barra de decisao permanece fixa |

### Tela 3 - Edicao de campo (modal do detalhe)

Objetivo: corrigir em no maximo 3 interacoes, sem sair do contexto.

    +---------------------------------------------------------+
    | Corrigir campo: Valor total                        [x]  |
    |---------------------------------------------------------|
    | Extraido pela IA: R$ 1.234,00        (somente leitura)  |
    | Origem: pagina 1, linha 12   [ver no original]          |
    |                                                         |
    | Valor correto:    [ R$ 1.434,00            ]            |
    |                   aviso: agora confere com a soma itens |
    | Motivo: [digitacao][extracao][divergencia][outro]        |
    |---------------------------------------------------------|
    |                        [Cancelar]  [Salvar correcao]    |
    +---------------------------------------------------------+

| Elemento | Onde | Para que serve |
|---|---|---|
| Cabecalho com o nome do campo | Topo do modal | Modal pequeno e fechado: corrigir um numero nao exige trocar de tela |
| Valor extraido | Primeira linha | Somente leitura, estilo apagado; preservar o original e requisito de auditoria (secao 2), nao detalhe estetico |
| Origem + "ver no original" | Segunda linha | Confere o trecho do documento sem fechar o modal |
| Entrada com mascara e validacao | Centro | Moeda BR (1.234,56), data (dd/mm/aaaa), CNPJ com digito verificador, quantidade inteira/decimal; valida em tempo real valor > 0, data plausivel, CNPJ valido e soma coerente |
| Motivo da correcao | Sob o campo | Chips (digitacao, extracao, divergencia, outro); opcional no MVP, mas e a materia-prima do relatorio de qualidade da extracao |
| Acoes | Rodape | Cancelar e Salvar correcao; ao salvar, a linha volta marcada "editado por humano" (a confianca passa a ser a do humano), a correcao entra no historico e o alerta de soma recalcula na hora |

### Tela 4 - Aprovacao em lote

Objetivo: tirar do caminho o que e seguro, sem cegar o revisor no que e perigoso.

Elegibilidade (aplicada na tela 1 antes de habilitar o botao): todos os campos obrigatorios
presentes e acima do limiar; nenhum campo vermelho; nenhuma falha de validacao; nenhuma suspeita de
duplicidade; nenhum documento em revisao aberta por outro revisor.

    +------------------------------------------------------------+
    | Aprovar 8 documentos                                       |
    |------------------------------------------------------------|
    | [ ] Eu revisei a lista abaixo                              |
    | N.pedido | Emitente     | Valor    | Editados | Confianca   |
    | 4412     | Acme LTDA    | 1.434,00 | 1 campo  | 94%         |
    | 4418     | Distrib Beta |   890,00 | nenhum   | 96%         |
    |------------------------------------------------------------|
    | Total dos 8 documentos: R$ 7.402,00                        |
    | Se o total parecer fora do normal, revise antes de aprovar. |
    |                            [Cancelar]   [Aprovar 8]        |
    +------------------------------------------------------------+

| Elemento | Onde | Para que serve |
|---|---|---|
| Lista de confirmacao | Corpo | Numero do pedido, emitente, valor, quantos campos o humano editou e confianca; a coluna "Editados" aponta onde houve intervencao manual - dado sensivel para quem aprova |
| Total somado | Rodape da lista | Soma dos selecionados: da a chance de notar um erro grosseiro (uma nota 10x acima do normal aparece na soma) |
| Checkbox de ciencia | Antes do botao | Barreira minima contra clique por reflexo, obrigatoria no lote |
| Botao de acao | Rodape | Numero explicito ("Aprovar 8"), nunca "OK" ou "Confirmar" |
| Resultado por documento | Apos a acao | Sucesso parcial permitido: escrito (com ID/linha) ou falhou (com motivo); o que falhou fica na fila com o motivo visivel - nada falha em silencio |
| Fora do MVP | - | Lote por expressao, regra automatica ("aprovar tudo do fornecedor X") e agendamento |

### Tela 5 - Historico de aprovacoes

Objetivo: rastrear o que virou linha na planilha, quem aprovou e o que a IA errou.

    Historico   Periodo: [01/03/26-31/03/26]  Usuario:[Todos]  Origem:[Todos]
    Rapidos: [Hoje][7 dias][Este mes]                          [Exportar CSV]
    -------------------------------------------------------------------------
    Data/hora   | Documento | N.pedido | Valor escrito | Aprovou | Editados
    02/03 14:12 | NF 4412   | 4412     | 1.434,00      | Fulano  | 1 campo
      > expande: valor total 1.234,00 -> 1.434,00 (Fulano, 02/03 14:12)
    Status: escrito / falha de escrita / revertido / rejeitado

| Elemento | Onde | Para que serve |
|---|---|---|
| Filtros | Topo | Periodo com atalhos, usuario, origem, status, emitente e busca por numero do pedido |
| Colunas | Corpo | Data/hora da escrita, documento, numero do pedido, valor efetivamente escrito, quem aprovou, quantos campos o humano editou, status e ID/linha na planilha (acha a linha sem abrir a planilha) |
| Expansao do registro | Sob a linha | Diff campo a campo (extraido -> final), autor e horario de cada correcao: e onde se responde "de quem foi esse numero" |
| Exportar CSV | Topo | Ponte para auditoria externa e contabilidade, sem construir relatorio no MVP |
| Sinal de qualidade | Topo | Contador de documentos escritos no periodo e quantos precisaram de edicao humana - a metrica honesta de valor do projeto e o argumento contra o risco 1 da secao 7 |
| Rejeitados | Corpo | Mesmo historico, com status e motivo proprios: rejeicao tambem e trabalho do operador e precisa ser visivel |

### O que fica de fora do MVP (cortes deliberados)

Login com multiplos perfis, cadastro de fornecedores/templates, edicao de regras pela interface,
graficos e dashboards, chat/comentarios no documento, anexar novos documentos pela interface (salvo
reenvio simples), busca avancada, tema escuro, notificacao por documento (padrao desligado),
integracao com contabilidade/ERP e app nativo. Cada corte e reversivel; cada tela a mais e uma semana
a mais mantendo algo que talvez ninguem use.

---

## 4. Notificacoes: avisar sem virar spam

Principio: **notificacao e para o operador agir, nao para o sistema se exibir.** Aviso que chega
quando nao ha nada a fazer treina o operador a ignorar todos os avisos. Canais: **Telegram** como
principal (o operador ja vive no mensageiro, leitura imediata, custo zero de infraestrutura) e
**e-mail** apenas para o resumo diario (arquivo que se guarda) e falhas de integracao.

| Evento | Canal | Frequencia | Conteudo |
|---|---|---|---|
| Resumo diario de pendencias | E-mail (e Telegram, se acordado) | 1x por dia util, horario comercial combinado | Total, quantos alto risco, idade da mais antiga, link direto |
| Falha de escrita na planilha | Telegram, imediato | Por incidente, com cooldown | O que falhou, quantos documentos, acao esperada |
| Integracao caida (token, permissao, webhook parado) | Telegram, imediato | Por incidente | O que esta parado, desde quando, quem resolve |
| Fila acima do limiar combinado | Telegram | Maximo 1x por periodo | Quantidade, tendencia, link |
| Documento acima do valor de corte (opcional, se o cliente definir) | Telegram | Por documento | Valor, emitente, link |

Nao e enviado: nada por documento individual no fluxo normal (a fila agrupada e o canal); nenhum
aviso de "documento aprovado" (o operador acabou de fazer isso - no maximo um recibo na tela); e
nenhum lembrete repetido do mesmo item.

Regras antispam (obrigatorias): agrupamento de eventos do mesmo tipo no mesmo periodo; cooldown de 1
alerta por tipo por hora, com no maximo 3 alertas nao criticos por dia; notificar apenas mudanca de
estado; horario silencioso fora do expediente, exceto falha critica de escrita/integracao que impede
trabalho; toda mensagem com link direto para a fila ou o documento e uma frase dizendo o que fazer;
controle na mao do usuario - "silenciar por 24h" no rodape da mensagem e preferencia de canal por
tipo de evento.

Opcao a decidir com o cliente (secao 8, pergunta 2): o operador encaminha a nota para o bot no
Telegram, o sistema ingere, extrai e responde na mesma conversa com o resultado e o link de
aprovacao - aproveita o comportamento que ele ja tem (mandar nota no WhatsApp) e encurta a distancia
entre receber e aprovar. Registrar toda notificacao enviada (canal, destinatario, horario, evento)
para auditoria: assim "nao me avisaram" e verificavel.

---

## 5. Padrao visual minimo da entrega

Premissa (P2): interface web unica. A recomendacao de biblioteca deve casar com a stack da spec de
arquitetura (01); com outra biblioteca, paleta, tipografia e componentes valem igual - muda o nome
da classe.

**Paleta**: fundo branco/cinza muito claro, texto cinza quase preto, primaria azul sobrio reservada a
acao principal e foco (nunca decoracao) e semanticas verde (aprovado/escrito), ambar (revisar) e
vermelho (erro/rejeitado) - **sempre com icone e texto**, porque cor nunca pode ser o unico portador
da informacao (daltonismo, impressao em preto e branco). Contraste minimo AA (4.5:1); valores
monetarios em peso maior, alinhados a direita e com numeros tabulares.

**Tipografia**: familia sem serifa (Inter ou a fonte de sistema) em 2-3 pesos, numeros tabulares
obrigatorios em tabelas e valores, escala curta de 12 (apoio), 14 (tabela), 16 (corpo), 20
(subtitulo) e 28 (titulo). Densidade alta e desejavel: o operador quer muitos documentos por tela,
nao respiro visual. Abreviar com reticencias e aceitavel; quebrar linha em valor, nao.

**Componentes basicos**: cabecalho fixo com titulo e contador; cards de KPI; chips de filtro; tabela
densa com zebra e hover; badge de confianca (numero + cor); faixa de alerta; modal de edicao; toast
de resultado; botoes primario/secundario/terciario; campo com label visivel e erro abaixo; paginacao;
estado vazio desenhado (nao tela branca); barra de acoes fixa; indicador de carregamento.

**Se for Bootstrap 5**: reaproveitar grid/flex e utilitarios de espacamento, `.table` com densidade
ajustada, `form-control`/`input-group`/`is-invalid`, `modal`, `alert`, `badge`, `toast`, variantes de
`btn`, `spinner-border`, `progress`, `accordion` (expansao do historico), `nav`/`tabs` (abas do
original) e os breakpoints responsivos. Nao usar temas prontos com cores saturadas, icones
decorativos nem animacoes chamativas; sobrescrever as variaveis de cor do Bootstrap com a paleta
acima, nunca o contrario. Ganho concreto: menos CSS proprio, componentes acessiveis de fabrica
(foco, teclado, ARIA) e menos bug de layout em tela pequena.

**Acessibilidade e responsividade** (nao negociaveis, mesmo no MVP): foco visivel e navegacao por
teclado para **tomar a decisao** (aprovar/rejeitar/salvar), porque operador de financeiro
frequentemente e usuario de teclado; `aria-live` anunciando o resultado da aprovacao em lote; telas
1, 4 e 5 no computador e telas 2 e 3 tambem no celular (aprovar fora do escritorio e caso de uso
real do dono); sem scroll horizontal em nenhuma tela; linguagem sem jargao de IA ("confianca 62% -
confira o valor" comunica, "score 0.62" nao).

---

## 6. O que fica para a fase 2

| Item | Por que espera | Gatilho para comecar |
|---|---|---|
| App proprio / mobile nativo e captura por camera | O web responsivo resolve a maior parte do caso; OCR de foto e frente tecnica propria (angulo, sombra) | Acesso majoritario por celular e demanda real de campo |
| Dashboards avancados (series, por fornecedor, projecao de caixa) | Grafico bonito sobre dado sujo e pior que nenhum | Alguns meses de dados escritos e limpos |
| Multiusuario com perfis e alcadas | Sem saber quantos revisores existem, e especulacao | Mais de uma pessoa revisando (secao 8, pergunta 3) |
| Aprovacao por alcada de valor (acima de X, decide o gestor) | Depende de regra que ainda nao existe | Definicao do valor de corte |
| Gestao de templates/regras pela interface | Regex por fornecedor e melhor mantida pelo time tecnico no inicio | Volume de layouts novos acima da capacidade do time |
| Conciliacao com extrato bancario / ERP / contabilidade | Integracao desproporcional ao MVP | Contabilidade pedir formato especifico |
| Aviso automatico de vencimento de titulo | E uma segunda funcionalidade, nao revisao | Titulos com vencimento rastreados por meses |
| Relatorio de qualidade da extracao (acuracia por campo) | A base ja existe no historico; o relatorio vem depois | Primeira meta de acuracia acordada |
| Painel admin da integracao (reprocessar, limpar fila) | Operavel por script no MVP | Frequencia de incidentes acima do tolerado |

Regra de corte: nada desta tabela entra no MVP "de carona". O que nao esta nas 5 telas nao existe.

---

## 7. Riscos de usabilidade e adocao

Ordenados pelo que mais ameaca o projeto - o fracasso aqui raramente e tecnico.

1. **O operador volta a digitar tudo a mao (risco numero 1).** Causas: desconfianca da IA, medo de
   assinar um erro e friccao para corrigir. Mitigacao: correcao em 3 interacoes (tela 3), lote,
   original sempre ao lado (validar por leitura e mais rapido que digitar), planilha intacta onde
   sempre esteve e visibilidade de quanto trabalho manual foi evitado; comecar com escopo estreito
   e de alto volume, para o ganho aparecer na primeira semana e nao estrear com 100% dos formatos.
2. **A fila virar cemiterio.** Pendencia acumula, a pessoa adia e desiste. Mitigacao: resumo diario
   com a idade da mais antiga, meta de fila zero e lote para o que e verde; volume acima da
   capacidade e problema de escopo do piloto, nao do operador.
3. **Aprovacao por reflexo**, quando o revisor clica sem ler e o erro da IA entra na planilha.
   Mitigacao: alto risco nunca entra em lote, coluna de campos editados, total somado dos
   selecionados, motivo obrigatorio na rejeicao e checkbox de ciencia no lote.
4. **Caixa-preta** ("isso apareceu do nada"). Mitigacao: origem de cada campo, realce no trecho
   original, motivo da pendencia em linguagem de negocio e preview da linha que sera escrita.
5. **Perda de autoria / "a IA errou e sobrou para mim".** Mitigacao: registrar quem aprovou e quem
   corrigiu, com relatorio que evidencia o trabalho humano (a coluna "editados" e elogio, nao
   acusacao), e nunca esconder erro de extracao - erro visivel e tratado gera confianca; erro
   escondido destroi.
6. **Aumento temporario de trabalho** nos primeiros dias. Mitigacao: enquadrar como periodo de
   calibracao com dupla checagem combinada, comecar pelos formatos de maior volume e usar o motivo
   da correcao para ajustar templates, reduzindo a fila de forma visivel.
7. **Excesso de notificacao e opt-out.** Mitigacao: secao 4 inteira (agrupamento, cooldown, horario
   silencioso, "silenciar por 24h").
8. **Conflito de revisao simultanea.** Mitigacao: lock leve com aviso de quem esta revisando e
   revalidacao pre-escrita (secao 2).
9. **Edicao manual da planilha por fora do sistema**, quebrando rastreabilidade e permitindo
   duplicidade. Mitigacao: definir com o cliente (secao 8, pergunta 6); no minimo, a linha gerada
   carrega um ID de revisao, distinguindo origem manual de origem sistema.
10. **Interface bonita e dado ruim.** Extracao fraca enche a fila de vermelho e devolve o operador ao
    manual. Mitigacao: meta de acuracia e qualidade de extracao como pre-requisito de lancamento,
    nao como detalhe posterior (specs 02 e 03).

---

## 8. Perguntas ao cliente (6)

1. O sistema pode escrever algo na planilha sem revisao humana no MVP? Se sim, qual o limiar de
   confianca e quais campos ficam de fora (recomendacao: nenhum valor)?
2. Qual canal e horario para o resumo diario (Telegram, e-mail, ambos) e para quem ele vai? O
   operador aprova pelo celular ou so no computador?
3. Quantas pessoas vao revisar e aprovar? Uma pessoa so (login dispensavel no MVP) ou ja precisa de
   login e registro de quem aprovou?
4. Existe valor a partir do qual o documento precisa de aprovacao de outra pessoa (gerente/dono)? Se
   sim, qual e o valor?
5. Qual o volume esperado por dia (notas + pedidos + mensagens) e quantos fornecedores/layouts
   diferentes ja sao conhecidos? E a base para dimensionar fila, lote e tempo de revisao.
6. Depois do sistema no ar, a planilha continua podendo ser editada a mao, ou passa a ser escrita
   somente pelo sistema? Isso define se precisamos de controle de duplicidade na planilha.

---

A IA propoe, o humano confirma, a planilha so recebe o que foi confirmado - e todo o padrao visual
existe para tornar essa confirmacao rapida o bastante para o operador nao voltar a digitar.
