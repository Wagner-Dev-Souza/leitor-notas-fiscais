# Spec F9 - gerador do `.env.example` e verificador de producao (dono: preguica)

Contrato: `docs/execucao/00b-contrato-fechamento.md` (secoes 2, 3.4, 3.5, 5, 6). Leia inteiro.
Esta frente comeca DEPOIS de `app/config.py` (F7) existir no worktree - se `app/config.py`
ainda nao estiver la quando voce comecar, espere/avise o PO em vez de inventar o catalogo.

## Entregar

1. `tools/gerar_env_example.py` **novo** (secao 3.4): gera o `.env.example` a partir de
   `app.config.VARIAVEIS`, com `--saida` e `--conferir`.
2. `.env.example` **versionado na raiz**, gerado pelo script (nao digitado a mao). Precisa ter:
   cada variavel do catalogo, **valor vazio** (`CHAVE=`) para as sensiveis e placeholder apenas
   onde o contrato manda, e **um comentario por variavel** dizendo o que e, se e obrigatoria
   (e em que modo) e **onde obter** (ex.: TELEGRAM_BOT_TOKEN -> @BotFather; TELEGRAM_CHAT_ID ->
   id do grupo; WHATSAPP_TOKEN -> Meta for Developers > WhatsApp > API Setup; VERIFY_TOKEN ->
   string que voce inventa e repete no painel da Meta).
3. `tools/verificar_producao.py` **novo** (secao 3.5): roda os 6 checks, imprime
   `PASSOU`/`FALHOU` por item, sai != 0 se algum falhar, trabalha em diretorio temporario e
   **nao** escreve em `data/`.

## Regra de ouro

O verificador tem de usar **execucao real** (`subprocess` chamando
`python -m app.run ...` com `--env`/`--real`/`--check-config`), nunca reimplementar a logica
de configuracao para "simular". Se um check depender de um comportamento que o codigo nao tem,
o check FALHA - e isso e a informacao que o cliente quer.

## Fora do seu escopo

* Nao editar `app/config.py`, `app/run.py`, `app/canais.py` (donos: F7/F8). Defeito achado por
  voce vira check FALHANDO + aviso no relato; a correcao e do dono.
* Nao criar `tests/` (dono: ira/F10).
* Nao rodar git.

## Evidencia (obrigatoria)

`docs/execucao/_ids/relato-F9.md` com a saida literal colada de:
1. `python tools/gerar_env_example.py` e depois `python tools/gerar_env_example.py --conferir`;
2. `python tools/verificar_producao.py` (todos os 6 checks com o resultado);
3. `head -40 .env.example` (ou equivalente) mostrando os comentarios;
4. `python -m pytest -q` mostrando a suite anterior verde.
