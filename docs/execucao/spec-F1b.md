# TASK F1b - Correcao: a trilha de auditoria nao pode ser apagada a cada rodada

## Target
`app/pipeline.py` (seu arquivo). Nao toque em arquivos de outro dono.

## Achado do PO (verificacao de aceite pos-onda 1)
A verificacao do PO rodou o comando unico 3 vezes e a idempotencia esta correta
(7 linhas na planilha em todas as rodadas, 20 artefatos deduplicados na 2a e na 3a).
Porem `app/pipeline.py` linhas ~155-157 fazem:

```python
# trilha de auditoria e um append por rodada: comeca limpa para nao misturar rodadas
if caminhos["auditoria"].exists():
    caminhos["auditoria"].unlink()
```

Isso **destroi a trilha de auditoria**. Depois da 2a rodada, `data/out/auditoria.jsonl`
continha apenas 20 linhas de `deduplicado` - o registro de "o que entrou e quando" da
primeira rodada (os 7 `inserido`) foi perdido. `persistencia.registrar_auditoria()` ja
faz append corretamente; o unlink e que rompe o requisito.

O criterio de aceite do cliente e literal: "mantem trilha de auditoria (arquivo de log/
registro do que entrou e quando)". Uma trilha que se apaga nao e trilha.

## Change
1. Torne `data/out/auditoria.jsonl` **cumulativa** (append entre rodadas). Remova o
   `unlink()`. O arquivo nunca e truncado pelo pipeline.
2. Preserve a intencao original de separar rodadas gravando **tambem** um arquivo por
   rodada: `data/out/auditoria_rodada_<AAAAMMDD-HHMMSS>.jsonl`, com as linhas daquela
   rodada. Assim as duas leituras existem e a culpa de misturar desaparece.
3. Cada linha da auditoria passa a registrar explicitamente a rodada
   (ex.: campo `rodada_id` = timestamp de inicio da rodada). Assim uma leitura cumulativa
   continua sendo analisavel por rodada.
4. Ajuste o resumo impresso para informar quantas linhas foram gravadas na rodada e onde
   (cumulativa e por rodada).
5. Verifique se algum outro arquivo de saida sofre do mesmo problema (`.csv`, `resumo.json`,
   `fila_excecoes.json`, `painel.html`, `pipeline.db`). Para cada um, decida e **documente
   no proprio codigo** qual e o comportamento correto: a fonte de verdade e o SQLite, entao
   a planilha e a fila serem regeradas a partir do banco e aceitavel; o que nao e aceitavel
   e perder registro de auditoria.

## Constraints
- Nao edite `app/contratos.py` (CONGELADO) nem arquivos de outro dono.
- **Nao rode nenhum comando `git`** - o PO versiona.
- Mantenha as 20 colunas da planilha e a idempotencia intactas: a correcao nao pode
  introduzir linha duplicada.
- Nada de rede, nada de servico pago.

## Ownership
Somente `app/pipeline.py` (e, se estritamente necessario, `app/run.py` - tambem seu).

## Observable acceptance
- Rode o comando unico **tres vezes** a partir de `data/out/` limpo e cole no `worker_done`:
  (a) a contagem de linhas da planilha depois de cada rodada (tem de ser 7, 7, 7);
  (b) a contagem de linhas de `data/out/auditoria.jsonl` depois de cada rodada
      (tem de ACUMULAR: 20, 40, 60);
  (c) a lista dos arquivos `auditoria_rodada_*.jsonl` gerados.
- Se algo nao fechar, relate a falha honestamente em vez de ajustar o numero na mao.
