# 04 - Operacao, deploy e automacao

Documento de operacao do sistema de ingestao de documentos (PDF de NF/pedido, WhatsApp,
Telegram) -> extracao por IA -> escrita em planilha de controle financeiro.
Escopo: onde roda, rede, entrega, observabilidade, resiliencia, backup, runbook, esforco
e riscos. Nenhum comando aqui foi executado; este documento e apenas proposta.

---

## 1. Onde o sistema roda

Opcoes consideradas. Custos em faixa relativa (sem valores), conforme restricao.

### Opcao A - VPS unica com Docker Compose
- Custo: faixa baixa e previsivel (1 VM pequena, mensal fixo).
- Esforco de setup: medio. Voce cuida de SO, firewall, TLS, atualizacoes, disco.
- Adequacao a projeto pequeno: alta. Tudo em uma maquina: API, worker, banco, fila, storage.
- Riscos: e voce quem reinicia quando cai; sem redundancia; disco enche e derruba tudo.
- Bom quando: volume baixo/medio, time confortavel com Linux, quer previsibilidade e controle.

### Opcao B - Container gerenciado (PaaS com deploy por imagem)
- Custo: faixa media e por consumo (CPU/RAM/tempo de execucao), escala sozinho no pico.
- Esforco de setup: baixo. Push da imagem, variaveis de ambiente, dominio, pronto.
- Adequacao a projeto pequeno: alta, com menos manutencao que A.
- Riscos: disco efemero por padrao (PDF precisa de storage externo), timeout de request
  curto para processamento longo, lock-in moderado do provedor.
- Bom quando: o cliente quer nao ter trabalho de servidor e aceita consumo variavel.

### Opcao C - Serverless por funcao
- Custo: faixa muito baixa em volume pequeno, dificil de prever em volume alto/longo.
- Esforco de setup: medio-alto. Webhook, fila, storage e banco gerenciados separados;
  empacotamento de dependencias de PDF/OCR e o ponto chato.
- Adequacao a projeto pequeno: media. Complexidade de pecas dispersas para pouco ganho.
- Riscos: limite de tempo de execucao, cold start, debug distribuido mais dificil,
  custo surpresa se o volume crescer.
- Bom quando: trafego muito irregular, picos raros e longos periodos parados.

### Opcao D (variante de A) - VPS com Docker + banco/fila gerenciados
- Custo: VPS pequena + servico gerenciado de banco (faixa baixa a media).
- Esforco de setup: medio. Mantem SO na mao, mas tira backup/PITR das costas.
- Indicada como evolucao de A quando a planilha e o banco passam a ser criticos.

### Recomendacao para o MVP
**Opcao A - VPS unica com Docker Compose**: API + worker + Postgres + Redis + MinIO/pasta de
PDFs em uma VM, com TLS automatico (reverse proxy), backup diario externalizado (secao 6).
Motivo: e a opcao de menor esforco total por real gasto em projeto pequeno, mantem tudo
observavel em um lugar e permite migrar para B ou D depois, sem reescrever nada, porque o
sistema ja estara containerizado.
Premissa da escolha: volume de ate ~200 documentos/dia e picos eventuais, time com
conhecimento basico de Linux/Docker.

---

## 2. Rede e integracao externa

### Endpoint publico exigido
- 1 dominio proprio (ex.: `agentes.empresa.com.br`) apontando para a VM.
- Rotas expostas:
  - `POST /webhooks/whatsapp` - verificacao (challenge) + recebimento de mensagens.
  - `POST /webhooks/telegram` - update do bot (recomendado: `setWebhook` com
    `secret_token` e validacao do header `X-Telegram-Bot-Api-Secret-Token`).
  - `POST /ingest/pdf` - upload/deposito de PDF (opcional se o PDF chega por e-mail/pasta).
  - `GET /health` e `GET /ready` - liveness/readiness (sem dado sensivel).
- Fora desses, nada deve ficar exposto. Painel/planilha sao saida, nao entrada.

### Certificado e borda
- TLS obrigatorio (Let's Encrypt via reverse proxy automatico: Caddy/Traefik/Nginx Proxy
  Manager ou ACME no container). Renovacao automatica e verificada por alerta (secao 4).
- HTTP deve redirecionar para HTTPS. Webhooks de provedores exigem HTTPS valido.
- Firewall: liberar 80/443 publicos; SSH apenas por chave, porta restrita a IP conhecido se
  possivel. Banco, Redis e storage NUNCA expostos na internet.
- Rate limit e limite de tamanho de corpo no webhook (protege contra abuso e upload gigante).

### Segredos - regra nao negociavel
- NUNCA em texto no repositorio. Sem excecao, inclusive em `docker-compose.yml`, README,
  teste ou notebook.
- `.gitignore` cobrindo `.env`, `*.pem`, `*.key`, `credentials*.json`; `.env.example` apenas
  com nomes de variavel e valores vazios.
- Guardar em: (a) variaveis de ambiente injetadas pelo runtime (Docker secrets / env do
  PaaS), ou (b) gerenciador de segredos (Vault, AWS Secrets Manager, Doppler, SOPS+age).
  Para projeto pequeno: `.env` fora do repositorio + `docker compose --env-file` e aceitavel.
- Segredos do sistema: token WhatsApp Cloud API, token do bot Telegram, chave da API do
  provedor de IA, credencial da conta de servico do Google Sheets, senha do banco,
  `SESSION/JWT` do painel se existir.
- Conta de servico da planilha: compartilhar apenas a planilha de destino com o e-mail dela
  (menor privilegio). Nada de credencial de usuario pessoal.
- Rotacao: trimestral ou imediata em suspeita. Trocar segredo = atualizar emissor + reiniciar
  servico (procedimento no runbook, secao 7).
- Nunca logar segredo nem payload completo de autorizacao; mascarar tokens em log e erro.

### Saidas (egress)
- Provedor de IA (HTTPS), API do Google Sheets, e-mail (se houver), NTP.
- Se o ambiente bloquear egress, liberar apenas esses destinos por allowlist.

---

## 3. Pipeline minimo de entrega

### Repositorio
- 1 repositorio Git, branch `main` protegida (PR obrigatorio), commits pequenos.
- Estrutura sugerida: `src/`, `migrations/`, `tests/`, `deploy/` (compose, proxy),
  `docs/`, `.env.example`.
- Dockerfile unico com `multi-stage`; a imagem e o artefato imutavel (tag = commit SHA).
- Nenhum segredo no repositorio (secao 2) e nenhum dado real de cliente em fixtures.

### Ambiente de teste (staging)
- Duas instancias dos mesmos containers: `staging` e `prod`, na mesma VM no MVP
  (compose profiles ou projeto separado), portas e bancos distintos.
- Staging com:
  - bots/webhooks de teste (bot Telegram de teste; numero WhatsApp de teste);
  - planilha de teste separada (nunca a de producao);
  - provedor de IA real, com limite de gasto/volume, OU mock gravado para teste de pipeline;
  - banco proprio, descartavel.
- CI (GitHub Actions ou equivalente) a cada push: lint, testes unitarios, testes de contrato
  dos payloads, build da imagem. Push da imagem somente apos verde.
- Deploy de staging automatico no merge para `main`. Deploy de producao manual (aprovacao).

### Processo de deploy (producao)
1. CI verde e imagem publicada com tag do commit.
2. Build das dependencias e migrations: rodar `migrate` como passo separado e idempotente
   antes de subir a aplicacao; migrations sempre retrocompativeis (adicionar antes de remover).
3. Subir containers novos ao lado dos antigos (rolling/`up -d` com healthcheck).
4. Healthcheck `/ready` deve passar antes de receber trafego no proxy.
5. Verificacao pos-deploy: 1 documento de teste real -> conferir linha na planilha.
6. Janela: fora do horario de pico de notas; deploy evitado em fechamento de mes.

### Rollback
- Rollback = subir a imagem anterior (tag do SHA anterior). Alvo: < 15 min.
- Migrations: aplicar sempre a estrategia expand/contract para que o codigo anterior
  continue funcionando com o schema novo. Se a migration for irreversivel, o plano de
  rollback inclui restaurar o backup pre-deploy (secao 6) e e explicitado no PR.
- Manter as 3 ultimas imagens na VM/local registry.
- Pos-rollback: reprocessar documentos que falharam da fila (secao 5). Nenhum documento e
  perdido porque o original fica no storage + banco.

---

## 4. Observabilidade

### Logs estruturados
- JSON por linha, com campos fixos: `ts`, `level`, `service` (api|worker|writer),
  `event`, `doc_id`, `source` (pdf|whatsapp|telegram), `provider`, `model`,
  `latency_ms`, `attempt`, `outcome`, `error_code`.
- Nunca logar conteudo integral do PDF/mensagem nem segredo; logar hash/id, tamanho e as
  primeiras chaves de identificacao.
- Correlacao: `trace_id` gerado no webhook e propagado por fila -> extrator -> validador ->
  escritor, para reconstruir um documento ponta a ponta.
- Retencao de log de aplicacao: 30 dias (ou conforme politica do cliente).

### O que monitorar (metricas de negocio e tecnicas)
- Documentos recebidos por fonte (pdf/whatsapp/telegram) - contador por hora/dia.
- Documentos processados com sucesso x falha, por etapa (ingestao, extracao, validacao,
  escrita). Taxa de sucesso por fonte e por fornecedor de documento.
- Taxa de campos criticos ausentes (`numero_pedido`, `valor_total`, `data`) - dado de
  qualidade da extracao, nao so tecnico.
- Taxa de reprocessamento e de correcao manual (documento que precisou de intervencao) -
  melhor indicador de valor real do sistema.
- Linhas escritas na planilha por dia e divergencia entre `linhas_enfileiradas` e
  `linhas_escritas` (se diverge, algo esta travado no meio).
- Latencia p95 ponta a ponta (webhook -> linha na planilha) e fila: tamanho da fila,
  idade do item mais antigo, profundidade da dead-letter.
- Erros por provedor de IA (429, 5xx, timeout) e custo/tokens por documento.
- Infra: CPU/RAM/disco, uso de disco por PDFs, validade do certificado TLS,
  sucesso dos jobs de backup, uptime dos containers.

### Alertas que importam (evitar ruido)
- Fila parada: itens com idade > 30 min (indica worker morto) - alerta critico.
- Fila crescendo continuamente por 1 h em horario comercial - alerta.
- Taxa de falha de extracao > 20% em 1 h - alerta (provedor de IA ou formato novo).
- Dead-letter com novos itens > 5 em 24 h - alerta com resumo diario.
- Backup falhou 2 dias seguidos - alerta critico.
- Certificado TLS expirando em < 14 dias - alerta.
- Disco > 85% - alerta (PDFs crescem rapido).
- Divergencia diaria entre enfileirados e escritos > 1% - alerta.
- Sem alerta para cada erro individual: agrupar (dedupe) e ter canal unico para o time
  (ex.: e-mail/Telegram de operacao), com a queda de heartbeat do proprio monitor.
- Baixo ruido: alertas "criticos" com acao clara; o resto vira relatorio diario de 1 tela.

---

## 5. Resiliencia

### Fila
- Todo documento/mensagem entra em fila persistente antes de qualquer chamada de IA (Redis
  com BullMQ/BeeQueue no Node, ou tabela `jobs` no Postgres). Nunca processar inline no
  handler do webhook: ele deve responder 200 rapido e enfileirar.
- Idempotencia obrigatoria: chave `source + external_id` (message_id do WhatsApp/Telegram,
  hash do PDF) com unique constraint. Reprocessar nao pode gerar linha duplicada.
- Concorrencia limitada e configuravel (nada de 50 chamadas simultaneas de IA).
- Ordem: por documento e irrelevante; sem requisito de ordenacao global.

### Retries com backoff
- Retry com backoff exponencial + jitter: ~1s, 5s, 30s, 2min, 10min (5 tentativas).
- Distinguir erro:
  - Transitorio (timeout, 429, 5xx do provedor, indisponibilidade da planilha) -> retry.
  - Permanente (arquivo corrompido, formato nao suportado, payload invalido) -> nao
    retry, vai para dead-letter + registro para tratamento humano.
- Limite de duracao do item na fila (se travar, volta para a fila).

### Dead-letter e reprocesso
- Dead-letter com o payload original, o erro, o `trace_id` e o numero de tentativas.
- Reprocesso: comando/endpoint administrativo que reenfileira por id ou por janela de
  tempo, sem editar o original. Sempre idempotente.
- Itens que precisam de decisao humana: fila de revisao (ex.: numero do pedido ilegivel,
  valores que nao fecham, fornecedor novo). Documento nao vai para a planilha com dado
  duvidoso: fica pendente e alerta.

### Falha do provedor de IA
- Timeout curto por chamada + retry (acima). Se o provedor cair por completo:
  1. Fila segura os itens (nada se perde), backoff aumenta.
  2. Se houver 2 provedores configurados, fallback automatico para o secundario.
  3. Todos os provedores fora: circuit breaker abre, alerta critico, fila acumula com
     limite de retencao (secao 6) e o sistema volta sozinho quando o provedor voltar.
- Documento que falhou na IA nunca e descartado: original permanece no storage.
- Nao reprocessar em loop infinito: apos o limite de tentativas, dead-letter.

### Falha da planilha (Google Sheets / Excel / OneDrive)
- Erro de quota (429), permissao ou planilha movida/bloqueada -> retry com backoff.
- A escrita e a ultima etapa: a extracao fica salva no banco. Se a planilha falhar, o dado
  nao se perde; reprocessa-se apenas a escrita (etapa separada e idempotente).
- Dedupe na escrita: coluna de chave (`external_id`) na planilha evita linha duplicada
  quando o retry acontece depois de um sucesso parcial.
- Planilha indisponivel por muito tempo: alerta e opcao de exportar CSV do banco como
  plano B manual, para o cliente nao ficar sem o controle financeiro.

---

## 6. Backup e retencao

Premissa geral: frequencia dimensionada para projeto pequeno; RPO alvo de 1 dia, RTO alvo
de algumas horas. Ambos a confirmar com o cliente.

### Banco (Postgres)
- Backup logico diario (`pg_dump`) com retencao de 14 dias, mais backups semanais mantidos
  8 semanas.
- Se possivel, PITR (WAL archiving) para RPO de minutos - recomendado se o banco for
  gerenciado.
- Destino do backup fora da VM (storage em nuvem com versionamento + criptografia).
- Teste de restauracao mensal em ambiente de teste. Backup nao testado nao e backup.

### PDFs originais
- Guardar o original de todo documento (auditoria, reprocesso, conferencia e disputa com
  fornecedor). Storage de objetos (S3-compativel) ou pasta versionada.
- Versionamento/immutability ligado; nunca sobrescrever o original.
- Retencao: a definir com o cliente (sugestao: 12 a 60 meses conforme obrigacao fiscal).
  Pergunta na secao 9.
- Custo: e o principal consumidor de disco - monitorar e alertar (secao 4).
- Diretorio de PDFs tambem entra no backup (metadados no banco + objetos no storage).

### Planilha
- Historico de versoes nativo do Google Sheets/OneDrive deve ficar ligado.
- Export diario da planilha para CSV/arquivo no mesmo bucket de backup (protege contra
  edicao manual que quebra formulas ou apaga linhas).
- Snapshot mensal congelado do arquivo para auditoria.

### Restauracao (procedimento minimo)
1. Avisar o cliente e parar a ingestao (modo manutencao: webhook responde 200 e enfileira,
   sem processar - nada se perde).
2. Restaurar banco do ultimo dump bom, subir a aplicacao com a imagem correspondente.
3. Restaurar PDFs do storage (se o problema foi no storage).
4. Reprocessar os itens da fila/dead-letter; a chave de idempotencia evita duplicar linhas
   que ja estavam na planilha.
5. Conferir contagens (documentos recebidos x processados x linhas escritas) e liberar a
   ingestao.
- Guardar o runbook de restauracao no repositorio (`docs/`), nao na cabeca de uma pessoa.

---

## 7. Runbook operacional (5 incidentes mais provaveis)

1. **Fila parada / documento nao aparece na planilha ha > 30 min**
   - Checar `/health` e `/ready`; ver se o container do worker esta de pe (`docker ps`).
   - Ler log do worker filtrando por `event=fila_parada` e `attempt`.
   - Reiniciar apenas o worker (`docker compose up -d worker`); se voltar, os itens
     pendentes processam sozinhos.
   - Se nao voltar: ver disco cheio, memoria e credenciais expiradas, nessa ordem.
   - Escalar se > 2 h de parada com fila acumulada.

2. **Provedor de IA falhando (429/5xx/timeout em serie)**
   - Confirmar pela metrica de erro por provedor; checar status page do provedor.
   - Ativar fallback para o provedor secundario (se configurado).
   - Nao aumentar retries manualmente em massa; a fila segura o volume.
   - Se persistir > 4 h, avisar o cliente sobre atraso e avaliar reducao temporaria de
     escopo (ex.: processar so PDF, deixar WhatsApp para depois).

3. **Escrita na planilha falhando (quota, permissao, planilha movida)**
   - Identificar erro exato (401 permissao, 403, 404 planilha inexistente, 429 quota).
   - Compartilhar a planilha de novo com a conta de servico se permissao revogada.
   - 429/quota: aguardar janela e reduzir concorrencia da escrita; retry reprocessa.
   - Enquanto isso, extracoes seguem salvas no banco; nada se perde.

4. **Extracao errada/duvidosa em volume (formato novo de documento)**
   - Amostrar 5 documentos do lote; comparar campos extraidos com o original.
   - Nao "consertar" linha a linha na planilha sem registrar: corrigir na fila de revisao e
     reprocessar para manter rastreabilidade.
   - Se o formato e novo e recorrente: abrir item de melhoria de prompt/parser, com os
     exemplos anexados (dado do cliente, cuidado com exposicao).
   - Avisar o cliente sobre pendencias e pedir amostra representativa do novo formato.

5. **Disco cheio / backup falhando / certificado expirando**
   - Disco: limpar logs antigos, ajustar rotacao, mover PDFs antigos para storage frio e
     ampliar volume. Nunca apagar PDF que ainda esta na janela de retencao.
   - Backup falhou: checar credencial do destino e espaco; rodar o backup manualmente e
     confirmar no destino. Dois dias seguidos = tratado como incidente serio.
   - TLS: renovar forcando o proxy e validar; se falhar, checar DNS e porta 80 aberta.

Formato de registro de incidente: data/hora, sintoma, causa, acao, tempo parado,
documentos afetados, se precisou de reprocesso e quantos itens vieram da dead-letter.

---

## 8. Esforco de setup por opcao (dias uteis)

Premissas (explicitas):
- Time: 1 desenvolvedor em tempo parcial, ja familiarizado com Node/Docker, sem trabalho
  de terceiros para liberar credenciais.
- Nao inclui tempo de espera do cliente (aprovacao de numero WhatsApp, conta de servico,
  acesso a planilha, definicao de retencao).
- Nao inclui desenvolvimento do extrator/validacao (tratado nos documentos 01 a 03).
- Faixas, nao datas; a confirmar apos a secao 9.

| Opcao | Setup inicial | Observacao |
|---|---|---|
| A - VPS + Docker Compose | 3 a 5 dias | Inclui TLS, proxy, backup diario, observabilidade basica. Faixa mais provavel: 4 dias. |
| B - Container gerenciado | 2 a 4 dias | Menos infra manual; some tempo em storage externo e limites de timeout. |
| C - Serverless | 5 a 8 dias | Mais pecas para amarrar (fila, storage, banco, empacotamento); maior custo de debug. |
| D - A + banco/fila gerenciados | 4 a 6 dias | Custa mais tempo de setup que A, economiza manutencao depois. |

Esforco recorrente estimado (operacao, nao setup):
- Opcao A: ~2 a 4 h/mes de manutencao (SO, patch, monitoramento) - a confirmar.
- Opcao B/C: menor manutencao de servidor, mas exige acompanhar consumo e limites.
- Qualquer opcao: ~1 a 2 h/mes de on-call leve (alertas, dead-letter, revisao).

Fase 2 possivel (nao no MVP): segundo provedor de IA com fallback automatico, painel de
revisao manual, alertas para o cliente, ambiente de staging dedicado em outra VM.

---

## 9. Riscos operacionais e perguntas ao cliente

### Riscos operacionais (ordem decrescente)
- Dependencia de um provedor de IA: indisponibilidade ou mudanca de preco/limite afeta o
  fluxo inteiro. Mitigacao: fila persistente + fallback na fase 2.
- Variacao de formato dos documentos: e a causa mais provavel de erro de extracao em
  producao, e nao um evento tecnico unico. Mitigacao: fila de revisao + monitorar taxa de
  campo critico ausente.
- Segredo vazado (token de bot/planilha no repositorio). Mitigacao: secao 2 + varredura no
  CI + rotacao rapida.
- Planilha como sistema de registro fragil: edicao manual pode quebrar formulas/linhas.
  Mitigacao: banco como fonte de verdade + export diario + historico de versoes.
- Volume de PDFs crescendo sem controle de retencao. Mitigacao: politica de retencao
  definida com o cliente e alerta de disco.
- Perda de acesso a conta de servico/numero do WhatsApp do cliente. Mitigacao: registrar
  a titularidade como do cliente e documentar como trocar a credencial.

### Perguntas ao cliente (maximo 6)
1. A planilha de controle e Google Sheets, Excel/OneDrive ou CSV? Quem e o dono da conta e
   podemos usar uma conta de servico do cliente?
2. Qual o volume esperado de documentos por dia (media e pico) e quantos formatos de nota
   diferentes existem hoje?
3. Quanto tempo os PDFs originais precisam ficar guardados e existe exigencia fiscal de
   retencao?
4. O numero de WhatsApp e Business API oficial (Cloud API) ou nao-oficial? Quem e o
   titular da conta e do numero?
5. Qual e a tolerancia a erro aceitavel: documento duvidoso deve ficar pendente para
   revisao humana ou seguir direto para a planilha?
6. Precisamos de PITR/RPO de minutos no banco (custo maior) ou backup diario e suficiente?
