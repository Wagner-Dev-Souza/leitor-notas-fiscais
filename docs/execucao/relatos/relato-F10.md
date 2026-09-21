# Relato da frente F10 - testes de configuracao, modo real e higiene de segredo

- Frente: **F10** - dona: **ira** (QA da fase 3). Card Linear **PROJ-23** (pai PROJ-19).
- Worktree: `<worktree>` (branch `squad-pecados`).
- Interpretador: `.venv/Scripts/python.exe` (CPython 3.12.14).
- Contrato lido inteiro: `docs/execucao/00b-contrato-fechamento.md` e `docs/execucao/spec-F10.md`.
- Escopo escrito: `tests/test_config.py`, `tests/test_canais.py`, `tests/test_producao.py` (novos) e
  `tests/evidencia/*`. **Nenhum arquivo de outro dono foi editado** e nenhum comando `git` de escrita
  foi executado (apenas `git ls-files`, `git check-ignore` e `git status`, como consulta).
- Sem rede externa: os canais foram exercitados contra **stub HTTP local em `127.0.0.1`** (permitido
  por D4) e o caminho real `transporte_urllib()` foi rodado de verdade contra esse stub.

## 1. Evidencia 1 - suite completa (`pytest -q`)

```
$ .venv/Scripts/python.exe -m pytest -q
........................................................................ [ 35%]
........................................................................ [ 53%]
........................................................................ [ 71%]
........................................................................ [ 89%]
.........................................                                [100%]
401 passed in 27.95s
```

**401 testes = 284 da fase 2 (intactos) + 117 novos da F10.** Zero falha, zero `xfail`, zero skip.
Saida crua: `tests/evidencia/f10-pytest-q.txt`.

## 2. Evidencia 2 - os tres arquivos novos (`pytest -v`)

```
$ .venv/Scripts/python.exe -m pytest tests/test_config.py tests/test_canais.py tests/test_producao.py -v
============================ 117 passed in 15.43s =============================
```

| Arquivo | Casos | Falhas |
| -- | -- | -- |
| `tests/test_config.py` | 70 | 0 |
| `tests/test_canais.py` | 28 | 0 |
| `tests/test_producao.py` | 19 | 0 |
| **Total novo** | **117** | **0** |

Saida crua (lista nominal completa): `tests/evidencia/f10-pytest-v.txt`.

### 2.1 Lista nominal dos testes novos

**tests/test_config.py** (70 testes, todos PASSED):

- test_catalogo_tem_exatamente_as_variaveis_do_contrato
- test_variavel_tem_descricao_e_onde_obter_uteis[CANAIS_ATIVOS]
- test_variavel_tem_descricao_e_onde_obter_uteis[DB_PATH]
- test_variavel_tem_descricao_e_onde_obter_uteis[INBOX_DIR]
- test_variavel_tem_descricao_e_onde_obter_uteis[LOG_DIR]
- test_variavel_tem_descricao_e_onde_obter_uteis[LOG_LEVEL]
- test_variavel_tem_descricao_e_onde_obter_uteis[MODO_EXECUCAO]
- test_variavel_tem_descricao_e_onde_obter_uteis[OUT_DIR]
- test_variavel_tem_descricao_e_onde_obter_uteis[TELEGRAM_API_BASE]
- test_variavel_tem_descricao_e_onde_obter_uteis[TELEGRAM_BOT_TOKEN]
- test_variavel_tem_descricao_e_onde_obter_uteis[TELEGRAM_CHAT_ID]
- test_variavel_tem_descricao_e_onde_obter_uteis[TELEGRAM_TIMEOUT_S]
- test_variavel_tem_descricao_e_onde_obter_uteis[WHATSAPP_API_BASE]
- test_variavel_tem_descricao_e_onde_obter_uteis[WHATSAPP_PHONE_NUMBER_ID]
- test_variavel_tem_descricao_e_onde_obter_uteis[WHATSAPP_TOKEN]
- test_variavel_tem_descricao_e_onde_obter_uteis[WHATSAPP_VERIFY_TOKEN]
- test_variavel_tem_descricao_e_onde_obter_uteis[WHATSAPP_WEBHOOK_DIR]
- test_obrigatoriedade_sensibilidade_e_padrao_batem_com_o_contrato[CANAIS_ATIVOS]
- test_obrigatoriedade_sensibilidade_e_padrao_batem_com_o_contrato[DB_PATH]
- test_obrigatoriedade_sensibilidade_e_padrao_batem_com_o_contrato[INBOX_DIR]
- test_obrigatoriedade_sensibilidade_e_padrao_batem_com_o_contrato[LOG_DIR]
- test_obrigatoriedade_sensibilidade_e_padrao_batem_com_o_contrato[LOG_LEVEL]
- test_obrigatoriedade_sensibilidade_e_padrao_batem_com_o_contrato[MODO_EXECUCAO]
- test_obrigatoriedade_sensibilidade_e_padrao_batem_com_o_contrato[OUT_DIR]
- test_obrigatoriedade_sensibilidade_e_padrao_batem_com_o_contrato[TELEGRAM_API_BASE]
- test_obrigatoriedade_sensibilidade_e_padrao_batem_com_o_contrato[TELEGRAM_BOT_TOKEN]
- test_obrigatoriedade_sensibilidade_e_padrao_batem_com_o_contrato[TELEGRAM_CHAT_ID]
- test_obrigatoriedade_sensibilidade_e_padrao_batem_com_o_contrato[TELEGRAM_TIMEOUT_S]
- test_obrigatoriedade_sensibilidade_e_padrao_batem_com_o_contrato[WHATSAPP_API_BASE]
- test_obrigatoriedade_sensibilidade_e_padrao_batem_com_o_contrato[WHATSAPP_PHONE_NUMBER_ID]
- test_obrigatoriedade_sensibilidade_e_padrao_batem_com_o_contrato[WHATSAPP_TOKEN]
- test_obrigatoriedade_sensibilidade_e_padrao_batem_com_o_contrato[WHATSAPP_VERIFY_TOKEN]
- test_obrigatoriedade_sensibilidade_e_padrao_batem_com_o_contrato[WHATSAPP_WEBHOOK_DIR]
- test_variavel_sensivel_nunca_tem_padrao_nem_exemplo
- test_sensiveis_do_catalogo_sao_exatamente_os_tres_segredos_do_contrato
- test_env_aceita_comentario_linha_vazia_export_aspas_e_espacos
- test_env_com_bom_na_primeira_chave_e_lido
- test_ambiente_do_processo_vence_o_arquivo
- test_env_arquivo_inexistente_e_erro_explicito
- test_sem_env_nenhum_o_modo_padrao_e_mock_e_isso_nao_e_erro
- test_modo_real_com_credencial_do_canal_ativo_nao_acusa_falta
- test_modo_real_exige_so_as_variaveis_do_canal_ativo
- test_modo_real_com_os_dois_canais_exige_as_cinco_variaveis
- test_chave_com_valor_vazio_conta_como_nao_configurada
- test_configuracao_invalida_aponta_o_campo_e_sai_com_mensagem_clara[MODO_EXECUCAO=producao\n-MODO_EXECUCAO]
- test_configuracao_invalida_aponta_o_campo_e_sai_com_mensagem_clara[MODO_EXECUCAO=real\nCANAIS_ATIVOS=whatsapp,email\n-email]
- test_configuracao_invalida_aponta_o_campo_e_sai_com_mensagem_clara[MODO_EXECUCAO=real\nCANAIS_ATIVOS=,\n-CANAIS_ATIVOS]
- test_configuracao_invalida_aponta_o_campo_e_sai_com_mensagem_clara[LOG_LEVEL=VERBOSE\n-LOG_LEVEL]
- test_timeout_invalido_e_recusado
- test_caminhos_padrao_do_modo_real_e_do_mock
- test_caminho_absoluto_no_env_nao_e_rebaseado
- test_erro_cita_cada_variavel_faltante_pelo_nome
- test_mensagem_de_erro_nunca_vaza_valor_de_variavel_configurada
- test_mascarar_valor_longo_mostra_so_os_ultimos_quatro
- test_mascarar_vazio_devolve_vazio[]
- test_mascarar_vazio_devolve_vazio[None]
- test_mascarar_valor_curto_nao_revela_nada[a]
- test_mascarar_valor_curto_nao_revela_nada[abc]
- test_mascarar_valor_curto_nao_revela_nada[1234567]
- test_mascarar_nunca_devolve_o_valor_completo[segredo]
- test_mascarar_nunca_devolve_o_valor_completo[senha12345678]
- test_mascarar_nunca_devolve_o_valor_completo[EAAGxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx]
- test_mascarar_nunca_devolve_o_valor_completo[1111111111:yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy]
- test_relatorio_de_configuracao_mostra_segredo_apenas_mascarado
- test_exemplo_env_cita_todas_as_variaveis_do_catalogo
- test_exemplo_env_nao_traz_valor_nas_variaveis_sensiveis
- test_exemplo_env_usa_os_placeholders_do_catalogo
- test_flag_mock_da_cli_sobrepoe_env_em_modo_real
- test_flag_real_da_cli_sobrepoe_env_em_modo_mock
- test_check_config_sai_2_e_cita_as_variaveis_quando_a_configuracao_esta_incompleta

**tests/test_canais.py** (28 testes, todos PASSED):

- test_coletar_telegram_grava_um_jsonl_por_coleta_no_formato_do_mock
- test_envelope_gravado_preserva_acentuacao
- test_update_sem_message_nao_vira_lixo_no_arquivo
- test_filtro_de_chat_id_descarta_conversa_nao_autorizada
- test_sem_update_do_chat_configurado_nao_grava_e_nao_e_erro
- test_sem_update_nenhum_nao_e_erro
- test_dois_updates_no_mesmo_segundo_nao_se_sobrescrevem
- test_montagem_da_requisicao_get_updates
- test_coleta_usa_urllib_real_contra_stub_local_127_0_0_1
- test_http_401_vira_erro_canal_claro_e_sem_vazar_token
- test_falha_de_rede_vira_erro_canal_sem_url_credenciada
- test_excecao_generica_do_transporte_vira_erro_canal_citando_as_variaveis
- test_resposta_ok_false_vira_erro_canal
- test_coletar_telegram_sem_token_na_configuracao_e_erro_explicito
- test_detalhe_de_sucesso_nunca_contem_o_token
- test_ler_webhook_grava_envelope_com_entry_e_move_o_arquivo
- test_envelope_de_status_sem_entry_e_descartado_com_explicacao
- test_mover_false_mantem_o_arquivo_na_pasta_do_webhook
- test_jsonl_com_varias_linhas_vira_varias_linhas_no_inbox
- test_linha_invalida_nao_derruba_a_coleta
- test_diretorio_de_webhook_ausente_nao_e_erro
- test_pasta_processados_nao_e_reconsumida
- test_detalhe_do_whatsapp_nunca_contem_o_token
- test_coletar_devolve_um_resultado_por_canal_e_ignora_desconhecido
- test_coletar_sem_canais_usa_a_configuracao
- test_coletar_whatsapp_usa_a_inbox_do_canal
- test_receptor_de_webhook_local_ciclo_completo
- test_modo_real_coleta_e_roda_o_pipeline_com_stub_local

**tests/test_producao.py** (19 testes, todos PASSED):

- test_env_real_nao_esta_versionado_e_esta_no_gitignore
- test_nao_existe_env_na_raiz_do_projeto
- test_nenhum_arquivo_versionado_com_nome_de_segredo
- test_env_example_existe_nao_e_ignorado_e_o_git_enxerga
- test_varredura_de_segredo_nos_arquivos_versionados
- test_scanner_de_segredo_tem_controle_positivo
- test_env_example_nao_tem_valor_em_variavel_sensivel
- test_env_example_bate_com_catalogo_e_com_o_gerador
- test_check_config_com_env_ficticio_sai_0_e_mascara_os_segredos
- test_check_config_nao_roda_o_pipeline
- test_check_config_com_env_inexistente_e_erro_claro
- test_mock_e_o_padrao_sem_env_e_nao_exige_credencial_nenhuma
- test_rodada_com_caminhos_temporarios_nao_toca_no_data_do_projeto
- test_log_em_arquivo_e_append_no_log_dir
- test_aviso_de_log_impossivel_nao_derruba_a_rodada
- test_real_sem_credencial_sai_nao_zero_citando_todas_as_variaveis
- test_real_sem_credencial_nao_vaza_valor_ja_configurado
- test_modo_real_com_um_canal_incompleto_nao_cobra_o_outro
- test_resumo_do_comando_unico_mostra_modo_e_trilha

## 3. Evidencia 3 - arquivos de saida salvos em `tests/evidencia/`

| Arquivo | Conteudo |
| -- | -- |
| `f10-pytest-q.txt` | suite completa em `-q` (401 passed) |
| `f10-pytest-v.txt` | os 3 arquivos novos com nome de cada teste (117 passed) |
| `f10-comando-unico-mock.txt` | saida real do comando unico congelado (`app.run --mock`) |
| `f10-verificar-producao.txt` | saida real de `tools/verificar_producao.py` (F9) |

O que cada arquivo novo cobre, em uma linha: `test_config.py` fecha o catalogo do contrato 3.1
(nomes, obrigatoriedade, sensibilidade, padrao), o parser do `.env` (comentario, linha vazia,
`export`, aspas, espacos, BOM), a precedencia ambiente > arquivo > padrao, o `ConfigError`
(faltando exato, sem traceback, sem valor de segredo) e o `mascarar()`; `test_canais.py` cobre a
coleta dos dois canais com envelope no formato do mock, o filtro de `chat_id`, o descarte de
envelope de status, o move para `processados/`, os erros (`ErroCanal`) sem vazar token, o receptor
de webhook real em 127.0.0.1 e o **ciclo completo do modo real** (`--real` -> coleta -> inbox ->
pipeline -> planilha/fila) contra stub local; `test_producao.py` cobre higiene de git/segredo,
`.env.example` x catalogo, `--check-config` mascarando segredo, o modo real sem credencial saindo
!= 0 citando cada variavel, o mock como padrao e o log em arquivo.

## 4. Comando unico (criterio 1 do aceite) - saida real

```
$ .venv/Scripts/python.exe -m app.run --mock
==============================================================
Pipeline de leitura de NF/pedidos - resumo da rodada
==============================================================
Modo     : mock | config: nenhum .env (padrao)
Inbox    : data\mocks
Saida    : data\out
Banco    : data\out\pipeline.db
Rodada   : 20260919-141317
--------------------------------------------------------------
Artefatos ingeridos : 20 (pdf 12 | mensagens 8)
Auto-aprovados      : 0
Em revisao humana   : 0
Rejeitados          : 0
Deduplicados        : 20
Linhas na planilha  : 7
--------------------------------------------------------------
Leitura por motor   : ocr_simulado 1 | parser 8 | pdfplumber 11
OCR                 : 1 artefato(s) lido(s) por OCR SIMULADO (sidecar .ocr.txt): a leitura nao vem de motor de OCR real e esta marcada como simulada.
Auditoria           : 20 linha(s) nesta rodada | trilha cumulativa: 1300 linha(s)
--------------------------------------------------------------
Arquivos gerados:
   xlsx              data\out\controle_financeiro.xlsx
   csv               data\out\controle_financeiro.csv
   auditoria         data\out\auditoria.jsonl
   auditoria_rodada  data\out\auditoria_rodada_20260919-141317.jsonl
   fila_excecoes     data\out\fila_excecoes.json
   painel            data\out\painel.html
   resumo            data\out\resumo.json
   db                data\out\pipeline.db
==============================================================
Rodada concluida em 0.771s
```

Exit code **0**. As linhas `Auto-aprovados/Em revisao/Rejeitados = 0` e `Deduplicados = 20`
sao o comportamento correto nesta maquina: o banco `data/out/pipeline.db` ja conhece os 20
artefatos das rodadas anteriores, entao esta rodada deduplica tudo - e a planilha continua com as
mesmas **7** linhas (idempotencia da fase 2, coberta pelos testes de `test_idempotencia.py`).

## 5. Achados

### 5.1 ACHADO (F9, `tools/verificar_producao.py`): sai != 0 dizendo "6/6 PASSOU"

- Arquivo: `tools/verificar_producao.py` (dono: preguica/F9). Itens: `retrato_data()`
  (linhas 133-146) e a conferencia final (linhas 578-586).
- Comando e saida real (arquivo completo em `tests/evidencia/f10-verificar-producao.txt`):

```
$ .venv/Scripts/python.exe tools/verificar_producao.py
[1/6] ... PASSOU   [2/6] ... PASSOU   [3/6] ... PASSOU
[4/6] ... PASSOU   [5/6] ... PASSOU   [6/6] ... PASSOU
data/ intacto (retrato de 84 arquivos, tamanho e mtime): False
  ATENCAO: mudou ['data/out/auditoria_rodada_20260919-141057.jsonl', 'data/out/pipeline.db-shm', 'data/out/pipeline.db-wal']
RESULTADO: 6/6 PASSOU
$ echo $?
1
```

- Mecanismo, provado com experimento controlado **meu** (nao atribuo a causa a F9): o guarda
  compara tamanho+mtime de **todo** arquivo sob `data/` antes e depois da rodada. O comando
  congelado `app.run --mock` - que e o criterio 1 do aceite, rodado pelo proprio cliente - altera
  arquivos de runtime:

```
$ (experimento) retrato de data/ antes -> roda app.run --mock -> retrato depois
rc do comando congelado: 0
arquivos alterados pelo comando congelado: 7
    data/out/auditoria.jsonl
    data/out/auditoria_rodada_20260919-141131.jsonl
    data/out/controle_financeiro.csv
    data/out/controle_financeiro.xlsx
    data/out/fila_excecoes.json
    data/out/painel.html
    data/out/resumo.json
somente arquivos de runtime (data/out/): True
```

- Impacto: qualquer atividade legitima do pipeline (a rodada do cliente, o proprio
  `tools/verificar.py` da fase 2, ou outra frente no mesmo worktree) faz o verificador sair com
  codigo **1** enquanto imprime "6/6 PASSOU". O cliente que olhar o exit code ve "reprovado"; quem
  ler o texto ve "aprovado". Nao e um item de verificacao que falhou - e a guarda de integridade
  de `data/` reagindo a artefato regeneravel.
- Sugestao (decisao do dono, nao corrigi): no retrato, ignorar o que e DESTINO/regeneravel
  (`data/out/**`, `*.db-wal`, `*.db-shm`) ou tratar a mudanca como aviso, mantendo o exit code
  coerente com o "RESULTADO". Alternativa mais simples: apontar todos os passos que rodam o app
  para um `--out`/`--db` temporarios - o que os passos 3 e 4 ja fazem - e limitar o retrato a
  `data/mocks`.

### 5.2 DEFEITO NENHUM nos arquivos da onda 1 (F7/F8/F9) nos 117 testes

Os 117 testes novos passam contra `app/config.py`, `app/canais.py`, `app/run.py`,
`tools/receber_webhook_whatsapp.py`, `tools/gerar_env_example.py` e `.env.example`. Em especial,
o que foi conferido de verdade (nao por leitura): o catalogo tem exatamente as 16 variaveis do
contrato com obrigatoriedade/sensibilidade/padrao iguais a tabela 3.1; `.env.example` e
**byte a byte** igual a `config.exemplo_env()` e `tools/gerar_env_example.py --conferir` sai 0; o
`ConfigError` cita cada variavel faltante pelo nome e nao vaza valor configurado; `--check-config`
mascara os 3 segredos; `--real` sem credencial sai 2 sem traceback e sem rodar o pipeline; o
receptor de webhook responde 403 com token errado, 200 com o desafio certo e grava o envelope sem
imprimir o token.

### 5.3 Observacoes (nao sao defeito - registro para o PO)

1. `.env.example` e os dois tools novos de F9 estao **no disco e nao no indice do git**
   (`git status --porcelain` -> `?? .env.example`), e nao estao ignorados (`git check-ignore`
   sai != 0). Ou seja: o criterio 4 do aceite ("versionado") depende do commit do PO no fim da
   onda, como o proprio F9 declarou. Medido, nao suposto.
2. **Modo real com ordem vinda so de mensagem nao gera linha na planilha.** No teste de ponta a
   ponta do modo real, a ordem coletada do Telegram vira artefato e vai para a fila de revisao
   humana (`acao=revisao`), enquanto a NF do corpus entra na planilha (`acao=inserido`). Nao e
   defeito de F8: e a regra **congelada** da fase 2 (`decidir()`: sem itens para reconciliar o
   total cai em `total_sem_detalhamento` -> `revisao_humana`), coerente com os 284 testes e com o
   manifest (todas as mensagens do corpus ficam em revisao). Registro porque o pedido do cliente
   fala em "a planilha ganha as linhas" no modo real: para ordem so por mensagem, quem publica e
   a revisao humana (F4), nao o automatico.
3. **Receptor de webhook sem validacao de assinatura**: `tools/receber_webhook_whatsapp.py`
   aceita qualquer POST no caminho do webhook - o proprio arquivo declara que
   `X-Hub-Signature-256` nao e validado porque o catalogo congelado nao tem o app secret da Meta.
   Com `--host 0.0.0.0` (nao e o padrao; o padrao e `127.0.0.1`) isso expoe a gravacao de
   envelope a qualquer origem. Depende de variavel nova no catalogo -> decisao do PO, nao de F10.
4. A suite `tests/**` da propria fase 2 executa o comando congelado na raiz do projeto em um
   teste (heranca do aceite da fase 2), e por isso rodar `pytest` tambem altera `data/out/`. Isso
   explica qualquer aviso do tipo "data/ mudou" enquanto a suite roda - nao vem dos testes
   novos da F10, que trabalham em `tmp_path` (ha teste proprio provando isso:
   `test_rodada_com_caminhos_temporarios_nao_toca_no_data_do_projeto`).

## 6. O que NAO foi testado contra servico real, e por que

1. **Chamada credenciada real a `api.telegram.org`** - nao existe token nem numero real
   autorizado nesta entrega (decisao **D4** do contrato). O que foi provado: a montagem da
   requisicao (`GET {api_base}/bot{token}/getUpdates`, conferida no stub pelo caminho exato da
   URL e pelos `params` de `offset`), a gravacao do envelope, o comportamento de erro (401, 404,
   `ok=false`, rede) e o ciclo completo do modo real contra stub local `127.0.0.1`. Nada disso e
   apresentado como chamada real.
2. **Chamada real a `graph.facebook.com`** - pelo mesmo motivo. O caminho do WhatsApp provado foi
   o que o produto realmente usa: webhook local (`http.server` real em `127.0.0.1`) -> envelope
   em `WHATSAPP_WEBHOOK_DIR` -> `canais.ler_webhook_whatsapp` -> inbox no formato do mock.
3. **Validacao da assinatura `X-Hub-Signature-256`** - nao implementada (sem app secret no
   catalogo congelado); ver observacao 5.3.3.
4. **Tesseract/OCR real** - segue o caminho simulado declarado desde a fase 2 (`ocr_simulado`),
   sem binario na maquina.
5. **Carga/concorrencia (AD-12/AD-13) e envio de mensagem real** - fora do escopo do card F10.
6. **Push/commit no `origin`** - so o PO roda git; a F10 nao toca em versionamento.

## 7. Como reproduzir

```
cd <worktree>
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m pytest tests/test_config.py tests/test_canais.py tests/test_producao.py -v
.venv/Scripts/python.exe -m app.run --mock
```

Os testes novos usam `tmp_path` para `.env`, inbox, saida, banco, log e webhook; os unicos
subprocessos sao a CLI do projeto (com `cwd` temporario, `--env` explicito e `PYTHONPATH` da raiz)
e o receptor de webhook em porta local efemera. Ha um controle positivo no scanner de segredo
(`test_scanner_de_segredo_tem_controle_positivo`) justamente para que a varredura nao possa
passar sem varrer nada.
