# TASK F6b - Fechamento: atualizar README e relatorios com o estado final (tudo verde)

## Target
`README.md`, `relatorios/RELATORIO-ENTREGA.md`, `relatorios/CRONOGRAMA.md`. Seus arquivos.

## Por que esta tarefa existe
Voce escreveu a documentacao quando a frente de testes (F5) ainda **nao** tinha entregado, e
registrou isso com honestidade - correto na hora. O quadro mudou e a documentacao esta
desatualizada em pontos que o cliente vai ler:

1. **A suite de testes EXISTE e esta VERDE.** O PO rodou agora, do zero:
   `.venv/Scripts/python.exe -m pytest -q` -> `284 passed in 12.58s`.
   Seus documentos ainda dizem "tests/ nao existe" e "item 5 da definicao de pronto nao
   atendido". Isso deixou de ser verdade.
2. **Tres defeitos foram encontrados pelo QA e corrigidos pelos donos**, e o PO verificou as
   tres correcoes:
   - D1: `manifest.json` da copia B4 tinha chave de acesso inventada -> corrigido (preguica);
   - D2: OCR simulado degradava `F` no lugar de `E`, fora do conjunto congelado -> o gerador
     foi restringido ao conjunto documentado `0/O, 1/l/I, 5/S, 2/Z` (preguica);
   - D3: motivo `divergencia_soma_itens` quando a soma nao podia ser calculada -> agora
     `total_sem_detalhamento` (gula);
   - extra: `tem_camada_texto` voltava `True` no caminho de OCR -> corrigido para `False`
     (avareza).
3. **A trilha de auditoria mudou de comportamento:** e cumulativa entre rodadas e cada linha
   tem `rodada_id`; existe tambem `auditoria_rodada_<AAAAMMDD-HHMMSS>.jsonl`. O contrato foi
   emendado (secao 4.1). Verifique se o README descreve o comportamento antigo e atualize.

## Change
1. Rode voce mesmo, agora, e use **a sua saida real** (nao copie a minha):
   - `.venv/Scripts/python.exe -m pytest -q`
   - `.venv/Scripts/python.exe -m run`? nao - use `.venv/Scripts/python.exe -m app.run --mock`
   - `.venv/Scripts/python.exe tools/verificar.py`
2. Atualize `README.md`: os numeros da rodada, o comportamento cumulativo da auditoria e o
   arquivo `auditoria_rodada_*.jsonl`; a secao de testes passa a refletir a suite real
   (quantos testes, o que cobrem). Mantenha as limitacoes honestas (OCR simulado rotulado).
3. Atualize `relatorios/RELATORIO-ENTREGA.md`:
   - os 9 itens da definicao de pronto: diga item por item o que esta atendido, com a
     evidencia, e o que nao esta;
   - registre os 4 defeitos encontrados pelo QA e como foram fechados - isso e prova de
     processo, nao vergonha;
   - mantenha a distincao entre o que foi **executado de verdade** e o que e proposta.
4. Feche `relatorios/CRONOGRAMA.md` (secao B) com o **tempo total da fase de execucao**,
   agora que as ondas fecharam. Bases disponiveis:
   - inicio: `docs/execucao/_ids/sprint_inicio.txt` = `2026-09-19 12:40:46 -0300`;
   - fim: o ultimo `worker_done` em `docs/execucao/_ids/monitor.log` (carimbos em UTC -
     converta para -03) e/ou o mtime do ultimo artefato;
   - despachos: `docs/execucao/_ids/dispatch_*.json`.
   Declare a base da medicao e os limites (tempo de parede com trabalho paralelo, nao soma
   de esforco). Separe **onda 1**, **onda 2/3 (correcoes)** e o **total**. Se algum numero
   nao for medivel, diga que nao e em vez de estimar sem base.
5. Nao invente nada: todo numero no documento tem de sair de arquivo, carimbo de tempo ou
   saida de comando que voce rodou.

## Constraints
- Nao edite arquivos de outro dono (`app/**`, `tools/**`, `tests/**`, `data/**`).
- **Nao rode nenhum comando `git`** - o PO versiona.
- Nada de preco, proposta comercial ou prazo nao aprovado.
- Nao apague nem reescreva os docs de planejamento (`docs/01..06`).

## Ownership
`README.md`, `relatorios/**`.

## Observable acceptance
- Cole no `worker_done` a saida real de `.venv/Scripts/python.exe -m pytest -q` e de
  `.venv/Scripts/python.exe tools/verificar.py` que voce rodou.
- Informe os numeros finais do Tempo B (onda 1, correcoes, total) e a base exata de cada um.
- Declare explicitamente, item por item, quais dos 9 criterios da definicao de pronto estao
  atendidos.
