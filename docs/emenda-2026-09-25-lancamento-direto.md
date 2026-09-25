# Emenda 2026-09-25 - lançamento direto na planilha (com destaque visual)

**Decisão do cliente (Wagner), substituindo o critério original do produto.** Registrado aqui
porque inverte a regra que o doc 05 (`docs/05-ux-revisao-humana.md`) chama de regra de ouro.

## O que mudou

| | Antes | Agora |
|---|---|---|
| Quem entra na planilha | só `auto_aprovado` / `validado` | **todo pedido** |
| Aprovação | aba `Revisao` da planilha (`APROVAR`/`REJEITAR`) | não existe: conferência visual |
| Falha de leitura | documento fora da planilha, na fila | linha entra **marcada** (cor na célula/linha) |
| Campo ausente | vazio | texto `NAO ENCONTRADO` |
| Documento ilegível | fora da planilha | linha com `ILEGIVEL` nos campos e status `ILEGIVEL` |
| Valor contraditório | fora da planilha | célula **vermelha**, valor **em branco** |

Razão dada pelo cliente: a operação precisa que a nota seja lida e lançada **sempre**, sem
revisar cada lançamento; a conferência passa a ser **visual**, procurando o destaque na planilha.

## Regras de destaque (implementadas em `app/persistencia.py`)

- `COR_CONFERIR` (`FFFFC000`, amarelo) - campo a conferir: `NAO ENCONTRADO`, `ILEGIVEL` ou valor
  lido por leitura fraca (OCR, DV torto, data dúbia, valor fora de faixa).
- `COR_CONTRADICAO` (`FFFF0000`, vermelho) na célula - valor que não fecha (divergência de soma,
  conflito com pedido conhecido, suspeita de duplicata): a célula fica **vazia**.
- `COR_CONTRADICAO` na LINHA - risco: instrução suspeita no documento ou suspeita de duplicidade.
- `COR_ATENCAO` (`FFFFF2CC`, amarelo claro) na LINHA - tem algo a conferir em algum campo.
- `status_validacao` passa a ser rótulo de negócio: `OK` / `CONFERIR` / `ILEGIVEL`.

## Consequência de engenharia (dita pelo desenho)

A planilha é **DESTINO regenerável**: o corpo é reescrito por inteiro a cada rodada, a partir do
banco. Antes o ledger só acrescentava/atualizava linhas, e uma linha que saísse do ledger (ex.:
mensagem sem texto) ficava de herança no arquivo - mostrando uma verdade que o banco não tinha mais.

## O que continua valendo

- **Nada é inventado**: valor duvidoso não é afirmado; campo ausente é dito ausente.
- **A fila de exceções continua existindo** como registro do que a leitura achou duvidoso - é dela
  que sai o destaque da linha, e é o que serve para tratar casos em lote.
- **O módulo `app/aprovacao.py` continua no repositório, dormente** (não é chamado pelo pipeline):
  se o fluxo de aprovação voltar, ele está testado em `tests/test_aprovacao.py`.

## Risco declarado (não escondido)

Valor errado passa a entrar no livro-caixa **sem bloqueio**, dependendo de alguém olhar o destaque.
Foi decisão consciente do cliente. O que o sistema faz para reduzir o dano: nunca inventa número,
nunca afirma valor contraditório e pinta tudo que ficou duvidoso - o resumo de cada rodada diz
quantas linhas pedem conferência e de que tipo.
