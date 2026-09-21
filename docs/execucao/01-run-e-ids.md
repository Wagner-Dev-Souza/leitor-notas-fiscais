# Rastreabilidade da fase de execucao

Registro do que foi despachado, para quem, e quando. Gerado a partir dos recibos
gravados pelo proprio Orca em `docs/execucao/_ids/`.

## Run de orquestracao

- **run_id:** `run_50dff8b29067`
- **criado em:** 2026-09-19T15:40:19Z (UTC)
- **coordenador (PO):** `term_1d23b48f-7417-485e-ad32-dd2c9e385b7d` (painel `soberba`)
- **worktree:** `<worktree>`

O PO coordenou de fora de um painel Orca, entao toda mutacao de orquestracao usou
`--from <handle>` explicito, e o Run ficou endereçado ao painel `soberba`.

## Tarefas e despachos

| Frente | Dono | Card | task_id | dispatch_id | Onda |
|---|---|---|---|---|---|
| F1 | avareza | PROJ-13 | `task_73228873f5e4` | `ctx_de0ddd571739` | onda 1 |
| F2 | gula | PROJ-14 | `task_92daee272b4e` | `ctx_29cdd9601d08` | onda 1 |
| F3 | preguica | PROJ-15 | `task_572a9ab00fa6` | `ctx_5e34253d9283` | onda 1 |
| F4 | inveja | PROJ-16 | `task_2900551aaf36` | `ctx_ca2ab3b03df8` | onda 1 |
| F1b | avareza | PROJ-13 | `task_f6c2b01fc43a` | `ctx_93f0fcecb179` | onda 2 |
| F5 | ira | PROJ-17 | `task_7ac042f4fcd3` | `ctx_8d1e65d0a8e4` | onda 2 |
| F6 | luxuria | PROJ-18 | `task_0152251aad9c` | `ctx_f6e562a972b3` | onda 2 |
| F3b | preguica | PROJ-15 | `task_159e8449d4c8` | `ctx_079d592b7f80` | onda 3 |
| F2b | gula | PROJ-14 | `task_efbd56dad274` | `ctx_4503cc73b5b0` | onda 3 |
| F1c | avareza | PROJ-13 | `task_69c6320470bf` | `ctx_a45c213aa0b9` | onda 3 |
| F6b | luxuria | PROJ-18 | `task_354a0540417a` | `ctx_3a57eac25430` | onda 4 |

## Ondas

| Onda | Frentes | Estrategia |
|---|---|---|
| 1 | F1, F2, F3, F4 | quatro frentes em paralelo, arquivos disjuntos por contrato |
| 2 | F1b, F5, F6 | correcao de defeito + testes + documentacao, em paralelo |
| 3 | F3b, F2b, F1c | os tres defeitos do QA, cada um devolvido ao seu dono |
| 4 | F6b | fechamento dos documentos com o estado final |

Dependencias: F5 e F6 so podiam comecar depois do codigo da onda 1 existir; F3b/F2b/F1c
dependiam do relatorio do QA (F5). Por isso as ondas, e nao um unico disparo de dez frentes.

## Artefatos de evidencia nesta pasta

| Arquivo | Conteudo |
|---|---|
| `run.json` | recibo de criacao do Run |
| `task_*.json` / `task_*.id` | recibos e ids das tarefas |
| `dispatch_*.json` | recibos dos despachos (`injected: true`) |
| `monitor.log` | instante de cada `worker_done` (carimbos em UTC) |
| `relatos_worker_done.md` | relato completo de cada frente, como ela mesma reportou |
| `sprint_inicio.txt` | instante do inicio da sprint de execucao em IA |
| `evidencia_pipeline.txt` | saida real do comando unico na rodada final |

Esta pasta e **material de trabalho do PO** (scratch operacional) e nao faz parte do
produto; fica no repositorio porque e a prova de quem despachou o que.
