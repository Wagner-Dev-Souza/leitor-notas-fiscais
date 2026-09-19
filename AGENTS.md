# Regras do projeto (leia antes de commitar)

Projeto: agentes de IA para leitura de notas fiscais/pedidos (PDF + WhatsApp/Telegram) com gravação em planilha de controle financeiro.

## Origem
Cliente (Wagner, via Loghanth) **não envia material**. Nada de depender de arquivo, conta, número de WhatsApp ou chave do cliente: **gere os dados você mesmo** (mock, fake, sintético) dentro do repositório, e pode consultar referências de formato na internet.

## O que NUNCA entra no git
- `.venv/`, `__pycache__/`, `*.pyc` — ambiente local, não é código
- `.env` e qualquer arquivo com chave/token/senha
- Dados gerados em tempo de execução que possam ser recriados por script (mantenha o **script gerador**, não a saída)

## O que entra
- Código-fonte, scripts geradores de mock, testes, README e docs.
- Commits **locais**, com mensagem clara dizendo o que mudou. **Sem push** — não existe remoto configurado para este projeto.

## Antes de dizer "pronto"
- Rode o pipeline de ponta a ponta com os mocks e **mostre a saída real** (a planilha gerada e os testes passando). Resultado sem execução real não conta.
- Um comando único deve reproduzir tudo (documentado no README).
- Não apague nem sobrescreva o trabalho dos outros agentes em `docs/`.
