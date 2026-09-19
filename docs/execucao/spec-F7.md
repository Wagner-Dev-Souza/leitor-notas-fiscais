# Spec F7 - configuracao `.env` e CLI (dono: avareza)

Contrato: `docs/execucao/00b-contrato-fechamento.md` (secoes 2, 3.1, 3.6, 5, 6). Leia inteiro
antes de comecar. Este spec nao repete o contrato: so diz o que fazer e o que provar.

## Entregar

1. `app/config.py` **novo**, exatamente com a interface da secao 3.1 (nomes, dataclasses,
   campos, funcoes e o catalogo de 16 variaveis). Somente biblioteca padrao.
2. `app/run.py` ajustado conforme a secao 3.6: `--real`, `--env`, `--check-config`, log em
   arquivo, mensagem clara de configuracao faltante (codigo 2, sem traceback), e o modo mock
   continua sendo o padrao e continua imprimindo o MESMO resumo de antes.

## Requisitos que o QA vai cobrar

* Sem `.env` nenhum: `python -m app.run --mock` roda igual a fase 2 (284 testes nao podem quebrar).
* `MODO_EXECUCAO=real` sem os segredos: erro que **cita pelo nome** cada variavel faltante,
  diz onde obter, sai 2 e nao roda o pipeline.
* Mensagem nunca imprime valor de variavel sensivel (use `mascarar`).
* `.env` com `export CHAVE=valor`, aspas, espacos em volta do `=` e comentario `#` e aceito.
* Ambiente do processo vence o arquivo `.env` (operador pode sobrescrever no shell).
* `--check-config` imprime o relatorio e sai 0 com configuracao valida.
* `Variavel`/`Config` sao `frozen` (dataclass imutavel) e `Config.modo_real` funciona.

## Fora do seu escopo (nao fazer)

* Nao criar `.env.example` (dono: preguica/F9, gerado do seu catalogo).
* Nao criar `app/canais.py` (dono: gula/F8). `run.py` chama a interface congelada da secao
  3.2; a importacao de `canais` deve ser defensiva (mensagem clara se o modulo faltar), como
  `pipeline.py` faz com `revisao`.
* Nao tocar em `app/pipeline.py`, `app/ingress.py`, `app/contratos.py`.
* Nao rodar git.

## Evidencia (obrigatoria)

`docs/execucao/_ids/relato-F7.md` com a saida literal colada de:
1. `python -m app.run --mock` (resumo completo);
2. `python -m app.run --real` sem `.env` (mensagem de falta + codigo de saida);
3. `python -m app.run --check-config` com um `.env` de teste (valores ficticios) mostrando a
   mascara nos sensiveis - use um `.env` em diretorio temporario e `--env`, **nao** crie `.env`
   na raiz do projeto (nao pode existir `.env` real versionado nem na arvore de trabalho);
4. `python -m pytest -q` mostrando que a suite anterior segue verde.
