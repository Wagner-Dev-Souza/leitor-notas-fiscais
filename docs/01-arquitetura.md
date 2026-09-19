# 01 - Arquitetura da Solucao

Documento de arquitetura. Escopo: entrada de PDFs (notas fiscais e pedidos) e de mensagens
(WhatsApp e Telegram), extração dos campos de controle financeiro e gravação automática em
planilha. Objetivo do cliente: reduzir entrada manual de dados. Este documento cobre somente o
desenho; não define preço, prazo, escopo final nem volume.

Premissas deste documento (bloco não numerado):
- P1: projeto pequeno, um cliente, uma empresa, equipe técnica mínima.
- P2: o volume diário não foi informado. O desenho assume dezenas de documentos/mensagens por dia (ordem de grandeza, a confirmar na seção 8).
- P3: a planilha de destino existe ou será criada pelo cliente; não cabe ao sistema definir o modelo financeiro dela.
- P4: existem amostras reais de PDFs e mensagens para calibrar a extração. Sem amostras a arquitetura continua válida, mas a acurácia não pode ser medida.
- P5: nenhum limite de API, preço de modelo ou valor de hospedagem é afirmado aqui sem verificação; o que depende de terceiro está marcado como "a confirmar na doc vigente".
- P6: toda estimativa de esforço/complexidade aparece com a premissa ao lado.

## 1. Visao de componentes

Oito componentes, cada um com responsabilidade única e fronteira clara ("não faz"), para permitir
teste por partes e troca por partes.

| ID | Componente | Responsabilidade | Não faz |
|----|-----------|------------------|---------|
| C1 | Ingestão PDF | Receber o arquivo (upload HTTP, pasta monitorada ou anexo de e-mail), validar tipo/tamanho, calcular hash, guardar o original, criar o registro e enfileirar | Não extrai campo, não escreve na planilha |
| C2 | Ingestão WhatsApp | Receber o webhook do provedor, validar assinatura, responder 2xx rápido, baixar mídia (imagem/PDF), normalizar para o contrato interno de mensagem e enfileirar | Não interpreta o texto, não decide se é pedido |
| C3 | Ingestão Telegram | Mesma função do C2 no canal Telegram (webhook do Bot API, validação de segredo, download por file_id) | Não interpreta, não decide |
| C4 | Fila | Ordenar e desacoplar o trabalho: entrada responde rápido, processamento tem retry e dead-letter | Não contém regra de negócio nem estado financeiro |
| C5 | Extrator IA | Converter documento/mensagem bruto em JSON estruturado: classificar o tipo (NF, pedido, desconhecido), rodar OCR quando necessário e chamar o modelo com saída estruturada | Não valida regra financeira, não grava na planilha, não decide aprovação |
| C6 | Validador | Aplicar regras determinísticas (soma de itens vs total, dígito verificador de CNPJ, data plausível, campos obrigatórios) e definir o status: auto_aprovado, revisao_humana ou rejeitado | Não inventa valor ausente, não corrige dado por conta própria |
| C7 | Escritor da planilha | Inserir uma linha por pedido/documento no destino escolhido (seção 5), de forma idempotente, e confirmar a gravação | Não reprocessa, não valida, não decide regra de negócio |
| C8 | Banco | Guardar documentos, mensagens, pedidos, itens, fornecedores, log de extração, fila de exceções e o estado da fila; garantir idempotência e auditoria | Não é a fonte de verdade financeira (essa é a planilha do cliente) |

Dois complementos que não viram componentes, para não inflar o desenho: (a) detecção de PDF digital
vs escaneado é etapa interna do C5 - PDF com camada de texto vai direto ao modelo, sem camada passa
por OCR antes; (b) o normalizador de entrada (reduzir PDF, imagem de WhatsApp e mensagem de Telegram
ao mesmo envelope) fica dentro de C1/C2/C3.

## 2. Fluxo ponta a ponta

Do recebimento até a linha na planilha. Cada passo cita o componente responsável; a rastreabilidade
consolidada está em 2.5.

2.1 Caminho A - documento PDF (upload, pasta monitorada ou anexo)
- F1 (C1): o PDF chega por `POST /v1/documentos` (ou por varredura de pasta / anexo de e-mail). A ingestão valida extensão, tamanho máximo configurado e se o arquivo abre como PDF.
- F2 (C1): calcula `hash_conteudo` (SHA-256) e consulta o C8. Se o mesmo hash já foi processado com sucesso, responde 200 com o resultado existente e não reprocessa.
- F3 (C1): grava o original em armazenamento de arquivo (pasta local ou bucket), cria o registro em `documentos` no C8 com status `na_fila` e devolve `202 Accepted` com `documento_id`.
- F4 (C4): o item entra na fila. O processador reserva por transação (`UPDATE fila SET status='processando' WHERE status='pendente'`), o que impede dois workers pegarem o mesmo item.
- F5 (C5): abre o documento e decide a leitura - PDF com camada de texto extrai texto direto; PDF escaneado passa por OCR para gerar texto.
- F6 (C5): monta o prompt versionado com o texto (ou a imagem paginada) mais o JSON Schema esperado e chama o modelo com temperatura 0.
- F7 (C5): valida a resposta contra o schema. JSON inválido tem no máximo N tentativas (premissa: N=2) antes de ir para a fila de exceções no C8.
- F8 (C8): grava o resultado bruto em `log_extracao` (modelo, versão do prompt, tokens, custo estimado, texto usado) - e o rastro de auditoria de cada campo.
- F9 (C6): aplica as regras determinísticas e calcula confiança por campo e geral. O que bate nas regras vira `auto_aprovado`; divergência de soma, CNPJ inválido ou campo obrigatório ausente vira `revisao_humana`; documento ilegível ou não reconhecido vira `rejeitado`.
- F10 (C8): normaliza e persiste em `pedidos`, `itens` e `fornecedores`, ligados a `documentos`. A partir daqui o pedido tem identidade própria e chave de deduplicação.
- F11 (C7): se o status for `auto_aprovado`, o escritor insere a linha na planilha com chave de idempotência (verificação do `id_pedido` na aba) e grava o `id_linha` de volta no C8.
- F12 (C8): fecha o item da fila como `concluido` e registra a escrita. O ciclo termina com a linha visível no controle financeiro.

2.2 Caminho B - mensagem de WhatsApp
- F13 (C2): o provedor entrega o evento em `POST /v1/webhooks/whatsapp`; a ingestão valida a assinatura do corpo bruto e responde 2xx imediatamente (resposta rápida e requisito do provedor).
- F14 (C2): normaliza o evento para o contrato interno de mensagem e baixa a mídia, se houver. Se a mídia for PDF, ela entra no Caminho A a partir de F2.
- F15 (C4): a mensagem normalizada entra na fila, em trilha separada dos documentos.
- F16 (C5): classifica a mensagem: pedido com dados, pedido sem valor, ajuste de pedido existente, mensagem irrelevante ou dúvida. Só as duas primeiras viram extração de campos; o resto é arquivado sem gerar linha na planilha.
- F17 (C5): extrai os campos do texto (número do pedido, valores, datas, itens) em JSON, no mesmo contrato de saída do Caminho A.
- F18 (C6): valida. Mensagem é formato mais frágil que PDF: a regra padrão exige número de pedido E valor total para auto-aprovação; faltando qualquer um, vai para `revisao_humana` em vez de virar linha.
- F19 (C8): persiste a mensagem em `mensagens` e o pedido extraído em `pedidos`, ligando o pedido a mensagem de origem.

2.3 Caminho C - mensagem de Telegram
- F20 (C3): o Telegram entrega o update em `POST /v1/webhooks/telegram`; a ingestão valida o segredo do webhook, responde 2xx e normaliza (inclusive `file_id` -> download do arquivo).
- F21 (C4): a mensagem entra na mesma fila e no mesmo contrato interno de C2, mudando apenas o campo `canal`. O processamento a partir daqui é idêntico ao Caminho B (F16 a F19): o canal não altera regra de extração nem de validação.
- F22 (C4, C8): falha transitória do extrator (API fora, timeout) devolve o item a fila com backoff progressivo; após o limite de tentativas vai para dead-letter em `fila_excecoes` no C8 e aparece na tela de pendências.

2.4 Ponto de junção dos três caminhos
- F23 (C6): toda saída normalizada, de PDF, WhatsApp ou Telegram, converge para a mesma validação. É aqui que se trata a deduplicação entre canais: a mesma NF enviada em PDF e citada em mensagem gera um pedido, não dois, pela chave (emitente + número + série/valor + data).
- F24 (C7, C8): o escritor da planilha nunca é chamado direto pela ingestão nem pelo extrator. Ele só executa sobre registro `auto_aprovado` (ou aprovado por humano na tela de revisão) e a fila registra a escrita. Isso mantém uma única porta de escrita no controle financeiro.

2.5 Rastreabilidade (componente -> passos do fluxo)

| Componente | Passos em que aparece |
|-----------|-----------------------|
| C1 Ingestão PDF | F1, F2, F3 |
| C2 Ingestão WhatsApp | F13, F14 |
| C3 Ingestão Telegram | F20 |
| C4 Fila | F4, F15, F21, F22 |
| C5 Extrator IA | F5, F6, F7, F16, F17 |
| C6 Validador | F9, F18, F23 |
| C7 Escritor da planilha | F11, F24 |
| C8 Banco | F2, F3, F8, F10, F12, F19, F22, F23, F24 |

## 3. Contratos de interface

3.1 Entrada de documentos

```
POST /v1/documentos
Authorization: Bearer <token-servico>
Idempotency-Key: <uuid-ou-hash>
Content-Type: multipart/form-data | application/json

Body (multipart): arquivo=<binario pdf/jpg/png>; origem=upload|email|pasta; canal_id=<opcional>
Body (json):      { "url": "<url-temporaria>", "origem": "upload",
                    "nome_arquivo": "nf-1234.pdf", "recebido_em": "2026-09-18T10:00:00-03:00" }
```

| Código | Quando | Corpo |
|--------|--------|-------|
| 202 | aceito e enfileirado | `{ "documento_id": "...", "status": "na_fila", "dedupe": false }` |
| 200 | hash/Idempotency-Key já processado | `{ "documento_id": "<existente>", "status": "<atual>", "dedupe": true }` |
| 400 | tipo não suportado, PDF corrompido ou acima do tamanho máximo configurado | `{ "erro": "arquivo_invalido", "detalhe": "..." }` |
| 401 | token ausente ou inválido | `{ "erro": "nao_autorizado" }` |
| 413 | excede o limite de tamanho configurado | `{ "erro": "muito_grande" }` |

Auxiliares mínimos: `GET /v1/documentos/{id}` (status + extração) e `POST /v1/documentos/{id}/revisao`
(correção/aprovação humana, detalhada no documento de UX).

3.2 Entrada de mensagens (contrato interno único dos canais)

```
POST /v1/webhooks/whatsapp        # GET com hub.challenge para verificacao; POST com o evento
POST /v1/webhooks/telegram        # segredo do webhook validado a cada chamada
```

Os dois webhooks são finos: validam, respondem 2xx e entregam ao normalizador. O contrato interno que
segue para a fila é o mesmo nos dois canais:

```json
{
  "canal": "whatsapp",
  "mensagem_id": "wamid.XXXX",
  "conversa_id": "5511999999999",
  "remetente": { "id": "5511999999999", "nome": "Fulano" },
  "timestamp": "2026-09-18T10:00:00-03:00",
  "tipo": "texto",
  "texto": "Pedido 4471 confirmado, 12 caixas, total 1.234,56",
  "midia": { "tipo": "pdf", "url_temporaria": "...", "nome": "pedido.pdf" },
  "reply_to": null
}
```

`tipo` aceita `texto|imagem|documento|audio`; `midia` é nulo em mensagem de texto. Áudio está previsto
no contrato mas fica fora do MVP (seção 6). Há também `POST /v1/mensagens` para envio manual/backfill,
com exatamente o mesmo payload.

3.3 Payload de saída normalizado (JSON extraído)

Contrato central do sistema: é a saída do C5, a entrada do C6 e a base da linha na planilha. Nenhum
componente troca dado fora deste formato.

```json
{
  "schema_version": "1.0",
  "documento_id": "doc_01H...",
  "origem": {
    "canal": "pdf|whatsapp|telegram",
    "remetente": "5511999999999",
    "recebido_em": "2026-09-18T10:00:00-03:00"
  },
  "tipo_documento": "nf|pedido|desconhecido",
  "campos": {
    "numero_pedido": "4471",
    "chave_acesso_nf": "35260912345678000199550010000044711000044710",
    "emitente": { "nome": "Fornecedor X LTDA", "cnpj": "12345678000199" },
    "data_emissao": "2026-09-18",
    "data_vencimento": "2026-10-18",
    "valor_total_centavos": 123456,
    "forma_pagamento": "boleto",
    "observacoes": null
  },
  "itens": [
    {
      "descricao": "Caixa de parafuso 5mm",
      "quantidade": "12",
      "unidade": "CX",
      "valor_unitario_centavos": 10288,
      "valor_total_centavos": 123456
    }
  ],
  "moeda": "BRL",
  "confianca": {
    "geral": 0.93,
    "por_campo": { "numero_pedido": 0.99, "valor_total_centavos": 0.88, "data_vencimento": 0.61 }
  },
  "validacao": {
    "status": "auto_aprovado|revisao_humana|rejeitado",
    "motivos": ["soma_itens_confere", "cnpj_dv_valido"]
  },
  "extracao": {
    "modelo": "<nome-do-modelo>",
    "versao_prompt": "extrator-v1",
    "ocr_usado": false,
    "tokens_entrada": 0,
    "tokens_saida": 0
  },
  "hash_conteudo": "<sha256>"
}
```

Decisões de contrato que valem registrar:
- Valores monetários são INTEIROS em centavos. Ponto flutuante para dinheiro é proibido, para eliminar erro de arredondamento na soma dos itens contra o total.
- Datas em ISO 8601 (`YYYY-MM-DD`), já convertidas de `dd/mm/aaaa`, no fuso local -03:00.
- Campo não encontrado é `null` e reduz a confiança daquele campo. O extrator nunca preenche campo por inferência silenciosa; quando muito, sugere valor em `validacao.motivos`.
- `confianca.por_campo` é o que separa auto-aprovação de revisão humana: campo obrigatório abaixo do limite configurado rebaixa o documento inteiro para `revisao_humana`.
- `hash_conteudo` é a chave de idempotência de ponta a ponta.

## 4. Stack recomendada

Uma linha de justificativa por escolha. Versões e limites de terceiros: a confirmar na doc vigente
antes de começar.

| Camada | Escolha | Justificativa (uma linha) |
|--------|---------|---------------------------|
| Linguagem | Python 3.12 | Ecossistema de PDF, OCR e SDK de LLM é o mais maduro para este tipo de pipeline. |
| API / HTTP | FastAPI + Uvicorn | Assíncrono (webhook precisa responder rápido) e schema derivado de tipos. |
| Validação de schema | Pydantic | O mesmo modelo define o contrato 3.3 e valida a resposta do modelo, sem duplicar regra. |
| Parsing de PDF digital | pdfplumber | Extrai texto e tabela de PDF com camada de texto sem custo de OCR. |
| OCR | Tesseract local + modelo multimodal como fallback | Tesseract cobre o volume barato; o modelo multimodal resolve escaneado ruim sem manter serviço extra. |
| Extração IA | LLM com saída estruturada (JSON Schema), temperatura 0 | Saída estruturada elimina parsing de texto livre, que é onde nasce erro silencioso de valor. |
| Orquestração do agente | Pipeline explícito, 1 chamada por documento, sem framework de agentes | Projeto pequeno: framework agrega abstração e curva de aprendizado sem resolver o problema. |
| Banco | SQLite (arquivo único) no MVP | Um processo e um cliente: SQLite atende e o backup é copiar um arquivo. |
| Fila | Tabela `fila` no próprio banco, com reserva por transação | Evita subir e operar Redis para dezenas de itens/dia (premissa P2). |
| Escrita na planilha | Google Sheets API (lib `gspread`) | Ver seção 5: menor atrito quando a planilha já é Google. |
| Armazenamento do original | Pasta local versionada com backup no MVP | Guardar o PDF original é requisito de auditoria e pasta simples atende o volume assumido. |
| Logs | Log estruturado em JSON, arquivo rotacionado | Permite contar documentos processados, falhas e linhas escritas sem plataforma extra. |
| Deploy | Um processo/container único com reinício automático | Menos peças móveis; sem orquestrador de containers para um cliente. |

Custo de complexidade assumido: sem framework de agentes, o retry, o roteamento por tipo de documento e
o versionamento de prompt são escritos a mão. Premissa: esse código cabe em poucas centenas de linhas.
Se o número de formatos de documento crescer muito, esse custo cresce e o item vira candidato a framework.

## 5. Destino da planilha: Google Sheets API vs Excel/OneDrive vs CSV

| Critério | Google Sheets API | Excel no OneDrive (Graph API) | CSV em pasta sincronizada |
|----------|-------------------|-------------------------------|---------------------------|
| Escrita incremental por linha | Sim, direta por range/append | Sim, porém o append preciso exige ler e reescrever a planilha (via sessão do Graph) | Sim: abre, acrescenta linha, fecha o arquivo |
| Concorrência com usuário editando | Boa (a API lida com edição simultânea) | Fraca: conflito de versão/arquivo aberto é erro comum | Muito fraca: arquivo aberto pelo Excel bloqueia ou gera cópia |
| Risco de sobrescrever dado do cliente | Baixo (append em range) | Médio/alto se o fluxo reescrever o arquivo inteiro | Alto (regravação integral do CSV) |
| Fórmula e formato condicional | Preservados | Preservados | Perdidos (CSV não guarda formato) |
| Auditoria de quem escreveu | Histórico de versão da própria planilha | Histórico do OneDrive | Nenhuma |
| Atrito de acesso | Conta de serviço + compartilhar a planilha com ela | App registrado no Entra ID + permissão de arquivo | Nenhum (só o caminho da pasta) |
| Dependência externa | Internet + Google | Internet + Microsoft Graph | Nenhuma, mas depende do cliente sincronizar |
| Esforço de implementação (premissa: 1 destino, sem multi-aba) | Baixo | Alto | Muito baixo |

Recomendação para o MVP: Google Sheets API. É o único dos três em que "acrescentar uma linha" é operação
nativa da API, sem ler e reescrever o arquivo inteiro - o que elimina a principal causa de perda de dado
do cliente e o principal gerador de retrabalho.

Fallback quando o cliente não puder usar Google: CSV em pasta sincronizada, aceitando explicitamente a
perda de formato, a ausência de auditoria e o risco de conflito com arquivo aberto. Nesse caso o escritor
grava arquivo por dia (`lancamentos-YYYY-MM-DD.csv`) para reduzir colisão, e o cliente deve ser avisado de
que a planilha dele passa a ser leitura, não edição. Excel/OneDrive só se justifica se o controle já for
Excel e não houver migração possível; o custo é a complexidade da Graph API e o risco de sobrescrita.

## 6. MVP e fase 2

6.1 MVP (entrega mínima que já reduz entrada manual)
- C1: ingestão de PDF por upload HTTP e por pasta monitorada (e-mail entra aqui se já existir caixa dedicada; senão, fase 2).
- C2 e C3: webhook de WhatsApp e de Telegram com download de mídia.
- C4: fila em tabela no banco, com retry e dead-letter.
- C5: extração de NF e pedido, PDF digital e escaneado, mensagem de texto com pedido.
- C6: validador com soma, CNPJ, datas, campos obrigatórios e score de confiança.
- C7: escritor da planilha em UM destino (Google Sheets), uma linha por pedido/documento, idempotente.
- C8: banco com documentos, mensagens, pedidos, itens, fornecedores, log de extração e fila de exceções.
- Tela mínima de pendências para revisão humana (detalhada no documento de UX) e um único fluxo de aprovação: auto_aprovado escreve, o resto vai para revisão.
- Fora do MVP por decisão de escopo, não por limitação técnica: áudio, multiempresa, multiusuário com perfis, dashboards, edição da planilha pelo sistema e integração com ERP.

6.2 Fase 2 (depois do MVP rodando e medido)
- Transcrição de áudio de WhatsApp/Telegram como nova entrada do mesmo contrato: muda a ingestão, não o extrator.
- Banco para Postgres se concorrência, volume ou backup online exigirem.
- Fila externa (Redis/SQS) se o volume tornar a fila em banco gargalo.
- Segundo destino de planilha (Excel/OneDrive) para cliente que não possa usar Google.
- Aprendizado de template por fornecedor: cachear layout e pular o modelo em formato conhecido, reduzindo custo e latência.
- Painel de acurácia por campo e por fornecedor, alimentado pelo log de extração.
- Aprovação em lote mais elaborada, histórico de aprovações e multiusuário com perfis.
- Regras de negócio do cliente sobre o dado (ex.: classificação contábil), só depois que o cliente definir.

Critério de passagem: o MVP só está pronto quando houver volume real processado, taxa de erro por campo
medida na amostra do cliente e pendência de revisão humana em nível que o operador absorva na rotina diária.

## 7. Riscos tecnicos (ordem decrescente de impacto) e mitigacao

1. Extração errada e silenciosa de valor (gravar 1.234,56 onde era 12.345,60): impacto financeiro direto. Mitigação: centavos inteiros, soma dos itens contra o total, faixa de plausibilidade por fornecedor, confiança por campo com corte para revisão e rastro em `log_extracao`; valor acima do limite definido pelo cliente nunca é auto-aprovado.
2. Variedade de layout de documento: cada fornecedor emite um PDF diferente. Mitigação: extração por schema, não por regex de posição; amostra real por fornecedor no conjunto de avaliação; layout novo entra na amostra em vez de virar exceção manual recorrente.
3. Formatos de mensagem muito variáveis (texto livre, abreviado, sem valor, com emoji, vários pedidos numa mensagem). Mitigação: classificar antes de extrair; regra mais conservadora que a do PDF; pedido sem valor nunca é auto-aprovado.
4. Duplicidade: documento reenviado, ou a mesma NF em PDF e citada em mensagem. Mitigação: hash do arquivo + chave de negócio (emitente + número + série/valor + data) + verificação do `id_pedido` antes de inserir a linha.
5. OCR ruim em PDF escaneado de baixa qualidade. Mitigação: limite mínimo de qualidade de imagem, fallback para modelo multimodal e campo `ocr_usado` explícito no payload, para o revisor saber que o dado veio de leitura imperfeita.
6. Instrução maliciosa embutida em PDF ou mensagem tentando desviar o agente (prompt injection). Mitigação: o texto do documento é dado, nunca instrução; o modelo só responde no schema; validação determinística roda depois do modelo; nenhum dado de pagamento ou de outro cliente vem da fonte.
7. Indisponibilidade ou limite de API de terceiro (provedor de IA, WhatsApp, Telegram, Sheets). Mitigação: retry com backoff, dead-letter, resposta pública sempre rápida e escrita na planilha em lote curto para reduzir chamadas.
8. Falha de escrita na planilha depois da aprovação (linha perdida). Mitigação: estado `pendente_escrita` no C8, retry idempotente e conferência de contagem no fim do dia.
9. Divergência entre banco e planilha. Mitigação: a planilha é a fonte de verdade financeira e toda divergência é reconciliada a favor dela.
10. LGPD e exposição de dado sensível (dado bancário, CPF em documento, conversa de WhatsApp). Mitigação: definir com o cliente antes de começar o que pode sair para API de terceiro, minimizar o que vai ao modelo, controlar quem vê a planilha e fixar retenção do PDF original e do log.
11. Custo por documento fora de controle. Mitigação: registrar tokens e custo em `log_extracao`, definir teto de páginas por documento e alertar quando a média diária subir.
12. Dependência do número de WhatsApp já verificado junto a Meta. Se não estiver, o Caminho B trava e o MVP nasce só com PDF + Telegram; é dependência de início, não item de implementação.
13. Fila em banco virando gargalo com o tempo. Mitigação: medir tempo de espera e tamanho de fila no log e migrar para fila externa na fase 2 se houver evidência.

## 8. Perguntas ao cliente (8)

1. Quais são os 3 a 5 formatos de PDF mais frequentes (por fornecedor) e podemos receber amostras reais de cada um, incluindo ao menos um escaneado?
2. A planilha de destino já existe? Se sim, quantas abas, qual coluna identifica o pedido e ela precisa ser lida por outra pessoa ou ferramenta?
3. WhatsApp: qual provedor será usado (API oficial da Meta ou outro) e o número já está verificado? Quem envia os pedidos - fornecedores, vendedores internos ou ambos?
4. Telegram: quem usa (interno ou fornecedor) e o que costuma chegar por ele - texto, foto de nota, PDF?
5. Qual o volume médio e o pico por dia de documentos e de mensagens, já que a premissa P2 assume apenas dezenas por dia por falta desse número?
6. Quem revisa os casos de baixa confiança, quantas pessoas, e a revisão precisa registrar o nome de quem aprovou?
7. O que NUNCA pode ser enviado para uma API de IA externa: documento inteiro, dado de cliente, dado bancário? E qual a regra de retenção do PDF original e das conversas?
8. Quando um dado já escrito na planilha estiver errado: o sistema deve corrigir a linha automaticamente ou a correção é sempre manual e registrada?
