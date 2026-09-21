## Consolidado do PO — fase de escopo e desenho

Todos os pareceres desta fase saíram de execução real no worktree `squad-pecados` (branch `squad-pecados`, caminho `<worktree>`). Run de orquestração: `run_cd1b9874c508`.

### Artefatos produzidos (2.100+ linhas)

| Documento | Autor | Conteúdo |
|---|---|---|
| `docs/01-arquitetura.md` | avareza (arquiteto/backend) | 8 componentes, fluxo ponta a ponta F1–F24, contratos de API e payload normalizado, stack, destino da planilha, riscos |
| `docs/02-dados-e-ia.md` | gula (DBA/IA e dados) | estratégia híbrida de extração, campos e normalização, modelo de dados, idempotência, score de confiança, metas de acurácia, custo por documento |
| `docs/03-qualidade-riscos.md` | ira (QA/segurança) | 30 critérios de aceite testáveis, plano de testes, 15 casos adversariais (inclui injeção em PDF e em mensagem), LGPD, evidências exigidas |
| `docs/04-devops-ops.md` | preguiça (DevOps/SRE) | opções de hospedagem com recomendação, rede e segredos, pipeline, observabilidade, resiliência, backup, runbook |
| `docs/05-ux-revisao-humana.md` | inveja (frontend/UX) | fluxo de revisão humana, 5 telas descritas elemento por elemento, notificações, padrão visual |
| `docs/06-plano-e-requisitos-cliente.md` | luxúria (SM/negócios) | cronograma por etapas com premissas, marcos de aceite, checklist do cliente, dependências externas, riscos de prazo |

As specs de cada frente estão versionadas em `docs/specs/`.

### Prazo proposto (requer aprovação do cliente)

28 dias úteis em 5 etapas sequenciais, contados de D+0: E1 fundação e calibração (3) → E2 motor de extração de PDF (8) → E3 canais WhatsApp e Telegram (6) → E4 escrita na planilha e revisão humana (6) → E5 homologação (5). Com a reserva de risco de 6 dias úteis, o compromisso vira **até 34 dias úteis**. Sustentado por 9 premissas nomeadas (P1–P9) no documento 06.

### O que trava o início (depende do cliente)

Amostras reais (30 PDFs, sendo 3 escaneados, de pelo menos 5 fornecedores; 50 mensagens), planilha alvo real com acesso de escrita, definição e titularidade do número de WhatsApp, aprovação do provedor de IA e do uso de nuvem pelo jurídico/LGPD, volume real (média e pico) e um decisor nomeado.

### Riscos que sustentam o prazo

1. **Extração errada silenciosa de valor** — o pior modo de falha. Mitigação aceita como não negociável: valor só é publicado com âncora determinística, dupla leitura independente ou confirmação humana.
2. **Verificação da conta WhatsApp Business na Meta** — 2 a 15 dias úteis fora do nosso controle; Telegram não depende disso e pode ser entregue antes.
3. **Layout novo de fornecedor** — esperado, não exceção; entra em revisão humana e nunca em escrita automática.
4. **Acesso à planilha corporativa e amostras insuficientes** — os dois bloqueios mais comuns.
5. **LGPD** — decisão do cliente sobre o que pode ser enviado a API de terceiro.

### Ponto de reconciliação técnica em aberto

Os pareceres 01 e 04 divergem no alvo de infraestrutura: o 01 propõe SQLite mais fila em tabela no banco para o MVP (um container, simplicidade); o 04 propõe VPS com Docker Compose rodando Postgres, Redis e MinIO (mais robusto, mais peças). Ambos são defensáveis. **Decisão pendente do PO com aval do cliente**, a ser fechada em E1, quando o volume real for conhecido — é o dado que decide.

### Próximo passo

Aprovação do escopo priorizado e do cronograma pelo decisor do cliente, entrega do checklist da seção 3 do documento 06 e início de E1. Itens de fase 2 (dashboards, conciliação, multiusuário, app próprio) permanecem fora do MVP até nova priorização.
