# Spec F8 - coleta real dos canais (dono: gula)

Contrato: `docs/execucao/00b-contrato-fechamento.md` (secoes 2, 3.2, 3.3, 5, 6). Leia inteiro.
Este spec nao repete o contrato.

## Entregar

1. `app/canais.py` **novo**, com a interface exata da secao 3.2: `ErroCanal`,
   `ResultadoColeta`, `TransporteHTTP` (Protocol), `transporte_urllib()`,
   `envelopes_telegram()`, `coletar_telegram()`, `ler_webhook_whatsapp()`, `coletar()`.
   Somente biblioteca padrao (`urllib.request`, `json`, `pathlib`, `datetime`).
2. `tools/receber_webhook_whatsapp.py` **novo**, conforme a secao 3.3 (`http.server`).

## Regras de ouro

* Os envelopes gravados tem de ser **byte a byte compativeis com o que `app/ingress.py` ja
  le**: WhatsApp = envelope completo `{"object":"whatsapp_business_account","entry":[...]}`,
  uma linha por envelope; Telegram = um update por linha, exatamente como
  `data/mocks/telegram/*.jsonl`. Compare com os mocks de verdade antes de codar.
* `coletar()` nunca levanta por canal desabilitado; levanta `ErroCanal` com mensagem clara
  para falha real de rede/HTTP (inclua o status quando houver).
* Nenhum segredo em `detalhe`, nome de arquivo ou linha de log. Mensagem de erro cita o
  NOME da variavel, nunca o valor.
* Sem update novo ou sem arquivo no diretorio de webhook: `ResultadoColeta` vazio e
  explicativo. Nao e erro.
* O transporte tem de ser injetavel: os testes do QA vao apontar `TransporteHTTP` para um
  stub local em `127.0.0.1`. **Nao faca chamada de rede para api.telegram.org nem para
  graph.facebook.com em nenhum momento** - nao ha credencial real (decisao D4).

## Fora do seu escopo

* Nao tocar `app/run.py` (dono: avareza/F7), `app/ingress.py`, `app/pipeline.py`.
* Nao criar `.env.example` (dono: preguica/F9).
* Nao rodar git.

## Evidencia (obrigatoria)

`docs/execucao/_ids/relato-F8.md` com a saida literal colada de:
1. prova de gravacao de envelope Telegram usando um **stub HTTP local** (ex.: suba um
   `http.server` em `127.0.0.1` que devolve um JSON no formato de `getUpdates`, aponte o
   transporte para ele e mostre o `.jsonl` gravado - o `cat` do arquivo);
2. prova do receptor de webhook: suba `tools/receber_webhook_whatsapp.py`, faca o `GET` de
   verificacao (token certo e token errado) e um `POST` com um envelope do mock, e mostre o
   arquivo gravado no diretorio de webhook;
3. prova de que o inbox gerado e digerivel pelo pipeline: rode
   `python -m app.run --inbox <seu diretorio de teste> --out <dir temporario> --db <temp.db>`
   com os envelopes coletados e mostre o resumo (deve contar as mensagens);
4. `python -m pytest -q` mostrando a suite anterior verde.
