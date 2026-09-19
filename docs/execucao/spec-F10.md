# Spec F10 - testes da configuracao, do modo real e da higiene de segredo (dono: ira)

Contrato: `docs/execucao/00b-contrato-fechamento.md` (secoes 2, 3.1, 3.2, 5, 6). Leia inteiro.
Esta frente comeca DEPOIS de F7 (config/run) e F8 (canais) estarem no worktree.

## Entregar

Tres arquivos novos, escritos no padrao que voce ja usou na fase 2 (mesmo estilo, mesma
fixture, `pytest` real, nada de teste que passa sem exercitar nada):

1. `tests/test_config.py`
   - catalogo: toda variavel do contrato existe em `VARIAVEIS`, com `descricao` e `onde_obter`
     preenchidos; nomes exatamente como no contrato (nenhum a mais, nenhum a menos);
   - `.env` de teste em diretorio temporario: comentario, linha vazia, `export `, aspas,
     espacos em volta do `=`; ambiente do processo vence o arquivo;
   - `ConfigError`: `faltando` contem exatamente as obrigatorias do modo/canal, a mensagem cita
     o nome de cada uma, `str(erro)` nao contem valor de segredo nem "Traceback";
   - `mascarar()`: nao devolve o valor completo de um valor longo, devolve `""` para vazio;
   - modo padrao sem `.env` = `mock` (requisito 4 do cliente);
   - `exemplo_env()` cita todas as variaveis do catalogo.
2. `tests/test_canais.py`
   - `coletar_telegram` com `TransporteHTTP` falso (sem rede): grava `.jsonl` no formato do
     mock e o numero de linhas bate com o numero de updates; update sem `message` nao vira lixo;
   - filtro por `chat_id` descarta conversa nao autorizada;
   - `ler_webhook_whatsapp`: envelope com `entry` vira linha no `.jsonl`; envelope de status
     (sem `entry`) e descartado; `mover=True` move o arquivo para `processados/`;
   - `ErroCanal`: transporte que levanta excecao -> `ErroCanal` com mensagem clara; e o
     `detalhe` de sucesso NAO contem o token;
   - **ponta a ponta do modo real (sem credencial real)**: envelope coletado ->
     `app.run --inbox <temp> --out <temp>` -> o resumo conta as mensagens e a planilha ganha
     as linhas. Este e o teste que prova o requisito "o modo real liga pela configuracao".
3. `tests/test_producao.py`
   - `git ls-files` nao lista `.env` nem arquivo com nome de segredo; `.env` esta no
     `.gitignore` (leia o arquivo de verdade);
   - `.env.example` existe, esta versionado (`git ls-files`) e **nao** contem valor plausivel
     de segredo (token/numero real) nas variaveis sensiveis;
   - varredura de segredo em `app/`, `tools/`, `tests/`, `docs/`, `README.md` versionados:
     padroes de token/chave/número de telefone real nao podem aparecer;
   - `--check-config` com `.env` de teste: sai 0 e a saida nao contem o token de teste;
   - `--real` sem `.env`: sai != 0 citando todas as variaveis obrigatorias do modo real.
   - Os testes que invocam CLI usam `subprocess` com `cwd` temporario e `--env` explicito,
     para nao depender de `.env` na raiz (que nao pode existir).

## Regras

* Teste que depende de rede externa: proibido. Stub local `127.0.0.1` e permitido.
* Nao usar `monkeypatch` para "provar" o que o codigo faz quando da para executar de verdade.
* Teste que falha por defeito real do codigo: reporte o defeito (arquivo, linha, evidencia) em
  `docs/execucao/_ids/relato-F10.md`. Nao conserte o codigo dos outros - nao e seu arquivo.
* Nao editar nada fora de `tests/`. Nao rodar git.

## Evidencia (obrigatoria)

`docs/execucao/_ids/relato-F10.md` com:
1. `python -m pytest -q` completo (rodada final, com a contagem: 284 da fase 2 + os novos);
2. `python -m pytest tests/test_config.py tests/test_canais.py tests/test_producao.py -v`
   (lista nominal dos testes novos);
3. saida salva em `tests/evidencia/` (arquivo texto), como voce fez na fase 2;
4. declaracao explicita do que NAO foi testado contra servico real (a chamada credenciada a
   Telegram/Meta) e por que.
