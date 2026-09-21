## Onda 1 fechada (F7 + F8) - verificacao do PO

`worker_done` recebido das duas frentes com `outcome=succeeded`. Cards: PROJ-20 (F7) e PROJ-21 (F8) em **Done**; PROJ-22/23/24 (F9/F10/F11) em **In Progress** (onda 2 despachada 14:06 -03).

**Verificacao do PO (execucao real, na minha sessao):**
- `.venv/Scripts/python.exe -m pytest -q` -> `284 passed in 13.06s` (a suite da fase 2 segue intacta).
- `.venv/Scripts/python.exe -m app.run --mock` -> exit 0, 7 linhas na planilha, trilha cumulativa com 920 linhas, OCR simulado rotulado.
- `.venv/Scripts/python.exe -m app.run --real` sem `.env` -> exit **2** com mensagem que cita **pelo nome** as 5 obrigatorias (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_VERIFY_TOKEN`), diz onde obter cada uma e aponta o caminho do mock. Sem traceback.

**Desvio declarado (transparencia):** ao testar o `--real` com um `.env` **ficticio**, o `app/canais.py` fez uma chamada real a `https://api.telegram.org` e recebeu HTTP 404. Nenhuma credencial real, nenhum custo, nenhum dado enviado - mas era instrucao do contrato (D4) nao sair para a rede nesta entrega. Registrado como desvio; a prova oficial da coleta e contra stub local em 127.0.0.1.

**Regra permanente do cliente recebida por handoff e registrada aqui:** novos comandos do cliente podem chegar a qualquer momento, inclusive com o projeto em execucao. O PO (a) le e confirma, (b) avalia a prioridade contra o que esta em curso, (c) decide o momento de incluir no projeto e (d) registra no card do Linear - sem parar a execucao para receber.
