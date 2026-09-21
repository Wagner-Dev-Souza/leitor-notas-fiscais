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
- Commits **com push para o GitHub** no remoto `origin`: `Wagner-Dev-Souza/agentes-nf-pedidos` (**privado**). Nunca faça push de segredo.

## Modelo de branches (remoto `origin`)
- `squad-pecados` — **é aqui que o time trabalha e commita** (é a branch do worktree do Orca).
- `homolog` — **homologação**: onde o trabalho converge antes de ir para produção.
- `main` — **produção**: só recebe o que já passou por `homolog`.
- Ordinal de promoção: `squad-pecados` → `homolog` → `main`. **Nada de commitar direto em `main`.**

## Requisito de entrega: configuração simples e operação em produção

O produto tem de ser **simples de rodar** por quem não conhece o projeto:

1. **Arquivo de configuração no formato `.env`** onde se coloca o **número/token REAL** de WhatsApp e de Telegram para o agente rodar de verdade. Versionar apenas um **`.env.example`** com as chaves vazias/placeholder e comentário explicando cada uma. O `.env` real **nunca** entra no git (é segredo).
2. **Nenhum segredo no código** e nenhum segredo em arquivo versionado. Sem a chave configurada, a aplicação deve **avisar com mensagem clara** qual variável falta — e não quebrar de forma obscura.
3. **README documentando a implementação em produção**: como instalar dependências, como configurar (quais chaves/número, onde colocar), como rodar o produto em produção, como acompanhar (logs, onde a planilha de saída é gravada), como agendar a execução e o que fazer quando uma extração falha.
4. O **modo mock continua sendo o padrão** para teste e demonstração; o modo real é ativado pela configuração do `.env`.

## Antes de dizer "pronto"
- Rode o pipeline de ponta a ponta com os mocks e **mostre a saída real** (a planilha gerada e os testes passando). Resultado sem execução real não conta.
- Um comando único deve reproduzir tudo (documentado no README).
- Não apague nem sobrescreva o trabalho dos outros agentes em `docs/`.
