# Demanda do cliente

Contratante (ponto de contato: Loghanth). Projeto de tamanho **pequeno**, categoria TI/Programação - IA.
Habilidades pedidas pelo cliente: Machine Learning, Python, NLP, API, Database, Scripts & Utilities.

## Problema a resolver

O cliente recebe documentos financeiros em dois canais e digita tudo à mão:

- PDFs de **notas fiscais** e **pedidos**;
- mensagens de **WhatsApp** e **Telegram**.

Precisa que dados (número do pedido, valores, datas, itens) sejam extraídos automaticamente e inseridos numa **planilha de controle financeiro**. Requisitos declarados: precisão na extração e robustez a formatos variados de documento e de mensagem. Objetivo: reduzir entrada manual de dados.

## Escopo priorizado (visão do PO)

Prioridade definida por risco decrescente: primeiro o que gera valor sem depender de terceiros, depois o que depende de aprovação externa.

**P0 - MVP (valor direto, sem dependência externa bloqueante)**
1. Ingestão de PDF (upload na interface e/ou pasta monitorada) de nota fiscal e pedido.
2. Extração estruturada dos campos-chave: número do pedido, emitente/CNPJ, data de emissão, valor total, itens (descrição, quantidade, valor unitário).
3. Escrita na planilha financeira com **chave de idempotência** (mesmo documento duas vezes não gera duas linhas).
4. Trilha de auditoria: guardar o que foi extraído, de qual arquivo/mensagem e com que confiança.
5. Revisão humana obrigatória quando a confiança da extração for baixa (nada de valor duvidoso entrando na planilha silenciosamente).

**P1 - Segundo canal e operação assistida**
6. Ingestão de mensagens de **Telegram** (Bot API - acesso técnico direto, sem verificação de negócio).
7. Ingestão de **WhatsApp**. Depende de decisão do cliente (ver riscos): a via oficial (WhatsApp Business Cloud API) exige conta Business verificada na Meta; a via não oficial viola os termos da Meta e expõe o número a bloqueio.
8. Fila de exceções com tela de correção e reprocessamento.

**P2 - Evolução (não faz parte do MVP)**
9. Dashboards gerenciais, multiusuário com perfis, app mobile, integração com ERP.

**Fora de escopo nesta contratação:** emissão de nota fiscal, conciliação bancária, leitura de manuscrito/OCR de baixa qualidade extrema, integração com sistema fiscal do cliente.

## Critérios de aceite macro

Cada etapa só é considerada entregue com evidência real, não com demonstração de tela:

1. Um lote de PDFs reais fornecidos pelo cliente é processado e a extração de **valor total** atinge a meta acordada (meta proposta pelo time, a validar com o cliente).
2. Reenviar o mesmo documento não duplica linha na planilha.
3. Documento fora do padrão vai para revisão humana em vez de gerar linha errada.
4. Toda linha escrita na planilha é rastreável até o arquivo/mensagem de origem.
5. Nenhum segredo (token, senha) em texto no repositório.

## Riscos identificados na abertura

1. **WhatsApp**: canal oficial exige verificação de negócio na Meta e cobra por conversa; a alternativa não oficial põe o número em risco. Decisão do cliente, não do time.
2. **Qualidade da extração em PDF escaneado**: valor lido errado em documento financeiro é o pior modo de falha; exige validação cruzada e revisão humana.
3. **Layouts de fornecedor diferentes**: sem amostras reais o prazo não pode ser fechado com confiança.
4. **Dados sensíveis (LGPD)**: documentos financeiros trafegando por API de terceiro exige decisão explícita do cliente sobre o que pode sair da infraestrutura dele.

## O que precisamos do cliente para começar

Amostras reais (PDFs de pelo menos 3 fornecedores diferentes e mensagens de pedido reais, anonimizadas se necessário), a planilha financeira alvo e permissão de escrita nela, definição sobre o número de WhatsApp, e um decisor único para aprovar marcos.

---

_Issue-mãe do projeto. O plano por etapas, os pareceres técnicos e o desenho da solução são produzidos pelo squad e ficam anexados aqui conforme as etapas fecham._
