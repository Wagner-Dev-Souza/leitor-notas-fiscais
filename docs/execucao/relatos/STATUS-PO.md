# Status do PO - fase 3 (fechamento) - PARCIAL, trabalho em curso

Registrado por soberba (PO) em 2026-09-19 ~14:20 -03, ao fim do orcamento de execucao da
sessao. Este arquivo existe para o proximo turno continuar sem repesquisar nada.

## Onde as coisas estao

Run da orquestracao: `run_3f31ccb914fa` (Orca). Coordenador: `term_1d23b48f-7417-485e-ad32-dd2c9e385b7d`.

| Frente | Dono | Dispatch | Card | Estado |
| -- | -- | -- | -- | -- |
| F7 | avareza | ctx_302ddd789520 | PROJ-20 | entregue (worker_done succeeded), PO conferiu |
| F8 | gula | ctx_c568803589be | PROJ-21 | entregue (worker_done succeeded) |
| F9 | preguica | ctx_8f803903d89b | PROJ-22 | entregue (worker_done succeeded), com defeito aberto abaixo |
| F10 | ira | ctx_a727cc62bdde | PROJ-23 | entregue (worker_done succeeded, auto-relato: 401 passed) |
| F11 | luxuria | ctx_571c95c1662c | PROJ-24 | **AINDA RODANDO** quando o orcamento acabou |

Arquivos no worktree (nao commitados): `app/config.py`, `app/run.py` (modificado),
`app/canais.py`, `tools/receber_webhook_whatsapp.py`, `tools/gerar_env_example.py`,
`tools/verificar_producao.py`, `.env.example`, `tests/test_config.py`, `tests/test_canais.py`,
`tests/test_producao.py`, `tests/evidencia/*`, relatos em `docs/execucao/_ids/relato-F7..F10.md`.

## Verificado pelo PO (execucao real na sessao do PO)

* `.venv/Scripts/python.exe -m pytest -q` -> `284 passed in 13.06s` (suite da fase 2 intacta).
* `.venv/Scripts/python.exe -m app.run --mock` -> exit 0, 7 linhas na planilha, trilha 920 linhas.
* `.venv/Scripts/python.exe -m app.run --real` sem `.env` -> exit 2, citando pelo nome as 5
  obrigatorias, com "onde obter" e sem traceback.

## Pendencia aberta (defeito real declarado pelo QA)

`tools/verificar_producao.py` imprime "RESULTADO 6/6 PASSOU" e sai com codigo 1 (guarda
`retrato_data()`). Ou seja: o verificador de producao esta inconsistente entre o que imprime e o
que devolve ao shell. Dono do arquivo: preguica (F9) - a correcao e dele, nao de outro agente.

## Nao feito ainda (nao maquiar)

1. F11 (README de producao + `AGENTS.md` + relatorio de fechamento) - em execucao.
2. Refazer a contagem final dos testes pelo PO (a marca de 401 passed e auto-relato do F10).
3. Rodada final de `tools/verificar_producao.py` apos a correcao do defeito acima.
4. `git add/commit` e `git push origin squad-pecados` - **nao executados**: o PO nao publica
   estado parcial como se fosse entrega fechada.
5. Comentario de fechamento no Linear (PROJ-19 e filhas) com a evidencia final.

## Desvio de escopo declarado

`app/canais.py` fez uma chamada real a `https://api.telegram.org` durante um teste do F7 com um
`.env` **ficticio** (token inventado), recebendo HTTP 404. Nenhuma credencial real, nenhum custo,
nenhum dado enviado - mas o contrato (D4) dizia para nao sair da rede. A prova oficial da coleta
segue sendo o stub local em 127.0.0.1.
