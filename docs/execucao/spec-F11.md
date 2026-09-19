# Spec F11 - README de producao, AGENTS.md e relatorio de fechamento (dono: luxuria)

Contrato: `docs/execucao/00b-contrato-fechamento.md` (secoes 1, 2, 3, 5, 6). Leia inteiro.
Esta frente comeca DEPOIS de F7/F8/F9 estarem no worktree (voce documenta codigo que existe,
nao codigo imaginado). Se algo do contrato nao existir no worktree, escreva assim mesmo o que
existe e denuncie a falta no relato.

## Entregar

1. `README.md` - **nova secao de implementacao em producao** (numerada, no estilo do README que
   ja existe; renumere as seguintes se precisar). Tem de responder, sem enrolacao:

   a. **Instalar dependencias**: Python do projeto (`.venv/Scripts/python.exe`, 3.12.14),
      comando exato de instalacao a partir de `requirements.txt`, e o comando para rodar os testes.
   b. **Configurar** - variavel por variavel, na ordem do catalogo: o que e, se e obrigatoria
      (e em que modo), **onde obter o valor** e exemplo de linha. Deixar explicitissimo onde
      entram o **token/número real de WhatsApp e de Telegram** e como ativar o modo real
      (`MODO_EXECUCAO=real`), incluindo o aviso de que o `.env` real **nunca** vai para o git.
      Referencie `.env.example` como a lista oficial e mantenha a tabela coerente com ele.
   c. **Rodar o produto**: comando unico no modo mock (o padrao) e no modo real; o que aparece
      na tela; o que fazer quando ele reclama de variavel faltante; `--check-config`.
   d. **Onde saem a planilha e a trilha de auditoria**: caminho de `controle_financeiro.xlsx`,
      `controle_financeiro.csv`, `auditoria.jsonl`, `auditoria_rodada_*.jsonl`,
      `fila_excecoes.json`, `painel.html`, `resumo.json`, `pipeline.db` e o papel de cada um
      (trilha que nunca se apaga x visao regeneravel - reaproveite a secao que ja existe).
   e. **Acompanhar logs**: `<LOG_DIR>/pipeline-<AAAAMMDD>.log`, o que olhar, níveis de log.
   f. **Agendar a execucao periodica**: pelo menos Windows (Agendador de Tarefas, incluindo o
      "Iniciar em" correto para a tarefa achar o `.venv`) e uma alternativa Linux/macOS
      (`cron`). Com o comando real que vai no agendador, e o aviso de que a rodada e idempotente
      (rodar de novo nao duplica linha) - ou seja, agendar e seguro.
   g. **Quando uma extracao falha**: o documento vai para a fila de excecoes, o que a pessoa vê
      no `painel.html`/`fila_excecoes.json`, como revisar e o que significa cada motivo
      (`cnpj_dv_invalido`, `divergencia_soma_itens`, `texto_instrucao_suspeita`, ...). Deixe
      claro o caminho: falhou -> fila -> revisao humana -> planilha.
   h. **Modo real dos canais**: como o Telegram e coletado (`getUpdates`) e como o WhatsApp
      entra (receptor de webhook local, `tools/receber_webhook_whatsapp.py`, porta, token de
      verificacao), e o que o operador precisa fazer no painel da Meta.

2. **Honestidade obrigatoria no README** (requisito 5 do cliente). Manter e atualizar a secao
   de limitacoes declarando sem rodeio:
   * OCR **simulado** (sidecar `.ocr.txt`; sem Tesseract nesta maquina) - nao e OCR real;
   * canais: os dados de WhatsApp/Telegram usados na demonstracao sao **arquivos de mock com o
     envelope real das APIs**;
   * a coleta real foi implementada e testada contra **stub local**, mas a chamada credenciada
     a `api.telegram.org`/`graph.facebook.com` **nao foi executada** (sem token/número real
     autorizado) - o que foi provado e a montagem da requisicao, a gravacao do envelope e o
     ciclo completo ate a planilha;
   * nao ha nada de servico pago, chave nova ou numero real nesta entrega.

3. `AGENTS.md` - corrigir a linha desatualizada que diz que nao existe remoto / que nao se faz
   push. Agora existe `origin` (privado, `https://github.com/Wagner-Dev-Souza/agentes-nf-pedidos`),
   a branch de trabalho e `squad-pecados`, `homolog` e homologacao e `main` e producao (sem
   commit direto), **so o PO roda git**, e continua valendo: segredo nunca entra no git.
   Nao reescreva o resto do arquivo.

4. `relatorios/RELATORIO-FECHAMENTO.md` - relatorio curto desta fase para o cliente: o que foi
   pedido, o que foi entregue, evidencias reais (comandos e saida), o que ficou de fora e por
   que, e o que o cliente precisa fazer para rodar de verdade (colocar o token/número real no
   `.env`). Sem promessa que nao se cumpriu.

## Fora do seu escopo

* Nao editar `app/`, `tools/`, `tests/`, `.env.example`, `.gitignore` nem as docs das fases
  anteriores. Divergencia entre README e codigo = chame no relato, nao conserte o codigo.
* Nao rodar git.
* Nao inventar saida de comando: se voce nao rodou, escreva o comando e diga que a saida esta
  no relato de quem rodou (F7/F8/F9/F10), ou rode voce mesma e cole.

## Evidencia (obrigatoria)

`docs/execucao/_ids/relato-F11.md` com: os comandos que voce rodou para conferir cada caminho
citado no README (ex.: `ls data/out`, `python -m app.run --mock`, `python -m app.run --check-config`
com `.env` temporario), a saida real colada, e a lista de linhas do README que voce criou.
