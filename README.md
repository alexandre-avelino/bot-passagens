# Bot de monitoramento de passagens aereas

Monitora precos de passagens (via Google Voos, sem API paga) e manda duas
mensagens no Telegram a cada execucao (2x por dia, de graca via GitHub
Actions): um **detalhe** das janelas mais baratas encontradas (com selo 🚨
nas que baterem alguma regra configurada -- teto, queda %, novo menor
preco) e um **resumo** com o melhor preco ja registrado em todo o
historico.

Este README assume que voce nao mexe com codigo. Siga na ordem.

## O que ja esta pronto (Fases 1, 2, 3 e parte da 4)

- Gerador de combinacoes de datas (ida/volta) respeitando a regra do dia
  obrigatorio, com testes automatizados.
- Busca real de precos (Google Voos) via a biblioteca `fast-flights`,
  incluindo horario de ida/chegada e escalas.
- Workflow do GitHub Actions ja configurado para rodar 2x por dia (mais um
  cron externo de fallback, ver secao "Passo 7").
- Historico de precos em SQLite (`historico.db`), commitado de volta no
  repositorio a cada execucao — todo voo encontrado fica registrado, nao so
  o que aparece nas mensagens.
- Alertas completos usando esse historico (teto de preco, queda percentual,
  novo menor preco), sinalizados dentro da mensagem de detalhe. Ver a secao
  "Detalhe, alertas e resumo" abaixo.
- Dashboard publico com grafico do menor preco por dia e por destino:
  **<https://alexandre-avelino.github.io/bot-passagens/>** (ver secao
  "Dashboard" abaixo).

Ainda **nao** existem comandos interativos no Telegram (`/hoje`,
`/historico`, `/config`) — essa parte da Fase 4 exige um servidor sempre
ligado (ver conversa sobre hospedagem) e ainda nao foi implementada.

## Passo 1 — Criar o bot no Telegram

1. Abra o Telegram e procure por **@BotFather**.
2. Envie `/newbot` e siga as instrucoes (escolha um nome e um username
   terminado em `bot`).
3. O BotFather vai te dar um **token**, algo como
   `123456789:AAExemploDeTokenNaoUseEste`. Guarde esse valor — e o seu
   `TELEGRAM_BOT_TOKEN`.
4. Envie **qualquer mensagem** para o seu bot novo (ex: "oi"). Isso e
   necessario para o passo seguinte funcionar.

## Passo 2 — Descobrir o seu chat_id

1. No navegador, acesse (trocando `SEU_TOKEN` pelo token do passo 1):
   `https://api.telegram.org/botSEU_TOKEN/getUpdates`
2. Procure por `"chat":{"id":` no resultado. O numero logo depois e o seu
   `TELEGRAM_CHAT_ID` (pode ser negativo, tudo bem).
   - Se aparecer vazio, volte no Telegram, mande outra mensagem pro bot, e
     atualize a pagina.

## Passo 3 — Criar o repositorio no GitHub

1. Crie um repositorio no GitHub — **privado ou publico**, a sua escolha.
   Os secrets do Passo 4 nunca ficam expostos de qualquer forma, seja qual
   for a visibilidade. Se quiser publicar um dashboard (ver secao
   "Dashboard" abaixo) via GitHub Pages, o repositorio **precisa ser
   publico** no plano gratuito do GitHub (Pages privado exige plano pago).
   Nesse caso, suas datas de viagem e o historico de precos ficam visiveis
   a qualquer um — nao ha dado sensivel nisso (so aeroportos, datas e
   precos), mas vale saber antes de decidir.
2. No terminal, dentro desta pasta (`bot-passagens`), rode:

   ```bash
   git init
   git add .
   git commit -m "Bot de monitoramento de passagens - Fase 1"
   git branch -M main
   git remote add origin https://github.com/SEU_USUARIO/SEU_REPOSITORIO.git
   git push -u origin main
   ```

## Passo 4 — Cadastrar os secrets no GitHub

1. No repositorio, va em **Settings -> Secrets and variables -> Actions**.
2. Clique em **New repository secret** e crie:
   - `TELEGRAM_BOT_TOKEN` = o token do Passo 1
   - `TELEGRAM_CHAT_ID` = o numero do Passo 2
3. Nunca cole esses valores dentro do `config.yaml` ou de qualquer arquivo do
   repositorio — eles ficam só nos secrets.

## Passo 5 — Ajustar a viagem em `config.yaml`

Abra `config.yaml` e ajuste:

- `origem` / `destinos`: codigos de aeroporto (IATA), ex: `CGB`, `GRU`, `CGH`.
- `periodo`: janela de datas que o bot vai varrer.
- `dias_obrigatorios` + `margem_adjacente`: dia(s) que precisam ser passados
  inteiros no destino (nunca dia de embarque/desembarque). `margem_adjacente`
  e quantos dias de folga sao exigidos antes E depois de cada um desses dias.
- `duracao.minima` / `duracao.maxima`: duracao da estadia, em dias.
- `alertas.preco_maximo`: dispara alerta quando algum voo custar isso ou menos.
- `alertas.queda_percentual`: dispara alerta quando o preco cair esse % ou
  mais desde a ultima vez que aquela janela foi checada.
- `alertas.novo_menor_preco`: se `true`, dispara alerta quando uma janela
  bate o menor preco ja visto para ela (a primeira vez que uma janela e
  vista nao conta como recorde, so estabelece o ponto de partida).

Nao precisa mexer em nenhum arquivo `.py` para monitorar uma viagem nova.

## Passo 6 — Testar localmente (uma vez)

No terminal, dentro da pasta `bot-passagens`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export TELEGRAM_BOT_TOKEN="cole_o_token_aqui"
export TELEGRAM_CHAT_ID="cole_o_chat_id_aqui"

python -m bot_passagens.main
```

Se tudo estiver certo, voce recebe **duas mensagens** no Telegram: o
detalhe das janelas mais baratas e o resumo. **Isso marca a Fase 1 como
pronta.**

Depois disso, o mesmo vai acontecer sozinho, automaticamente, pelo cron
externo (Passo 7) — sem precisar deixar nenhum computador ligado, 2x por
dia, sempre as duas mensagens juntas.

## Passo 7 — Cron externo (obrigatorio: e o unico agendador usado)

O agendador nativo do GitHub Actions (`schedule` no workflow) se mostrou
pouco confiavel: primeiro nao disparava nunca, depois passou a disparar
mas com ~2h de atraso -- e como o cron externo (abaixo) tambem estava
ativo, isso causava **execucoes e mensagens duplicadas** (uma no horario
certo, outra ~2h depois). Por isso o workflow **nao tem mais `schedule:`
nenhum** -- o unico jeito do bot rodar automaticamente e via este cron
externo gratuito, que chama a API do GitHub nos horarios certos.

1. Crie um **token do GitHub** com permissao minima (so pra disparar esse
   workflow, nada mais):
   - Va em <https://github.com/settings/personal-access-tokens/new>.
   - **Resource owner**: sua conta.
   - **Repository access**: "Only select repositories" -> escolha
     `bot-passagens`.
   - **Permissions -> Repository permissions -> Actions**: mude para
     "Read and write".
   - Deixe as outras permissoes como estao (sem acesso).
   - Defina uma expiracao (ex: 1 ano) e clique em **Generate token**.
   - Copie o token gerado (comeca com `github_pat_...`) — so aparece uma vez.
2. Crie uma conta gratuita em <https://cron-job.org> (ou outro servico
   equivalente de sua preferencia).
3. Crie **um unico cronjob** cobrindo os dois horarios (a tela de agendamento
   tem uma opcao **"Custom"** com selecao multipla):
   - **URL**: `https://api.github.com/repos/alexandre-avelino/bot-passagens/actions/workflows/monitor.yml/dispatches`
   - **Metodo**: `POST`
   - **Headers**:
     - `Authorization: Bearer SEU_TOKEN_AQUI`
     - `Accept: application/vnd.github+json`
     - `Content-Type: application/json`
   - **Body** (JSON): `{"ref":"main"}`
   - **Schedule -> Custom**:
     - **Timezone do job**: `America/Cuiaba` (se o cron-job.org perguntar)
     - **Hours**: selecione `8` e `20` (clique em um, segure Cmd e clique no
       outro para selecionar os dois sem desmarcar)
     - **Minutes**: selecione so `5`
     - Days of month / Days of week / Months: deixe todos selecionados
       (padrao = todo dia, todo mes)
4. Use o botao de "test run" do cron-job.org pra confirmar que disparou uma
   execucao no GitHub (confira na aba **Actions** do repositorio).

Sem esse cron externo configurado e ativo, o bot **nao roda sozinho** --
so dispara quando voce (ou eu) rodar manualmente pela aba Actions. Por
isso esse passo deixou de ser "recomendado" e virou obrigatorio pra
automacao funcionar.

## Historico de precos

A cada execucao, todos os voos encontrados (nao so os 3 enviados no Telegram)
sao gravados em `historico.db` (SQLite), que fica versionado dentro do
proprio repositorio — o workflow do Actions commita esse arquivo de volta
automaticamente depois de cada busca. Isso significa que:

- o repositorio vai acumular commits automaticos com a mensagem "Atualiza
  historico de precos e dashboard" (2x por dia); isso e esperado, nao
  precisa fazer nada;
- se quiser consultar o historico manualmente, da pra abrir `historico.db`
  com qualquer visualizador de SQLite (ex: extensao "SQLite Viewer" no
  VS Code) ou rodar `sqlite3 historico.db "select * from buscas"` no
  terminal.

## Dashboard

A cada execucao, o bot gera `docs/index.html` com um grafico do menor preco
encontrado por dia, uma linha por destino. Publicado de graca via GitHub
Pages (exige repositorio publico, ver Passo 3):

**<https://alexandre-avelino.github.io/bot-passagens/>**

O grafico comeca com poucos pontos (um por dia desde que o bot rodou pela
primeira vez) e vai ganhando historico com o tempo. Se voce trocar de
usuario/repositorio, o link muda para
`https://SEU_USUARIO.github.io/SEU_REPOSITORIO/` — nao precisa configurar
nada alem do que ja esta no workflow, GitHub Pages atualiza sozinho a cada
push no `docs/index.html`.

## Detalhe, alertas e resumo

Toda execucao (2x por dia) manda **sempre duas mensagens** no Telegram,
nunca so uma e nunca nenhuma:

**1. Detalhe** — as 3 janelas mais baratas encontradas nessa execucao, cada
uma com preco, horario, link e a comparacao com a media geral dos ultimos
30 dias (todas as rotas monitoradas juntas). Alem disso, o bot avalia se
cada janela bate alguma regra do `config.yaml` (comparando com o que ja
estava no historico *antes* desta execucao):

- preco menor ou igual a `alertas.preco_maximo`;
- queda de `alertas.queda_percentual`% ou mais desde a ultima vez que essa
  janela especifica foi checada;
- novo menor preco ja visto para essa janela especifica (se
  `alertas.novo_menor_preco: true`).

Se alguma regra bateu, aquela janela ganha um selo 🚨 na mensagem de
detalhe, com o motivo especifico logo abaixo.

**2. Resumo** — as mesmas 3 janelas mais baratas, so que num formato mais
enxuto, mais o menor preco ja registrado em todo o historico e quantas
janelas foram verificadas nessa execucao.

## Rodar os testes automatizados

```bash
source .venv/bin/activate
python -m pytest
```

## Aviso importante sobre volume de buscas

Com a configuracao padrao (2 destinos, periodo de ~2 semanas, duracao 4-7
dias), o bot faz cerca de 50 buscas por execucao. O workflow roda 2x por dia
(08h e 20h, horario de Cuiaba) em vez de 5x, o que da ~100 buscas/dia no
total -- reduzido de proposito para diminuir o risco de rate limit do Google
Voos (nao existe um limite oficial publicado, entao isso e uma estimativa
conservadora, nao uma garantia). Tambem ha uma pausa de ~2,5s entre cada
busca dentro de uma mesma execucao.

Se buscas comecarem a falhar, o bot manda um aviso no Telegram (no maximo 1x
por dia, mesmo que falhe em varias execucoes seguidas) e sempre registra o
detalhe nos logs do Actions. Se isso comecar a acontecer, tente, em ordem:

- reduzir a lista de `destinos` no `config.yaml`;
- reduzir ainda mais a frequencia (editar os `cron` em
  `.github/workflows/monitor.yml`, por exemplo para 1x/dia);
- aumentar `DELAY_ENTRE_BUSCAS_SEGUNDOS` em `bot_passagens/main.py`.

## Proximas fases (ainda nao implementadas)

- **Fase 4, parte 2** (opcional): comandos interativos no Telegram (`/hoje`,
  `/historico`, `/config`). Exige decidir uma hospedagem sempre ligada
  primeiro (o dashboard e o resto do bot continuam gratis; isso especifico
  nao da pra fazer so com GitHub Actions).

Quando quiser conversar sobre isso, e so pedir.
