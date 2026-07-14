# Bot de monitoramento de passagens aereas

Monitora precos de passagens (via Google Voos, sem API paga) e avisa no
Telegram quando o preco de alguma janela bate uma regra configurada (teto,
queda %, novo menor preco), alem de um resumo diario com o melhor achado do
dia. Roda de graca no GitHub Actions, 2x por dia.

Este README assume que voce nao mexe com codigo. Siga na ordem.

## O que ja esta pronto (Fases 1, 2 e 3)

- Gerador de combinacoes de datas (ida/volta) respeitando a regra do dia
  obrigatorio, com testes automatizados.
- Busca real de precos (Google Voos) via a biblioteca `fast-flights`,
  incluindo horario de ida/chegada e escalas.
- Workflow do GitHub Actions ja configurado para rodar 2x por dia.
- Historico de precos em SQLite (`historico.db`), commitado de volta no
  repositorio a cada execucao — todo voo encontrado fica registrado, nao so
  o que aparece nas mensagens.
- Alertas completos usando esse historico (teto de preco, queda percentual,
  novo menor preco) e resumo diario com o melhor preco ja visto. Ver a secao
  "Alertas e resumo diario" abaixo — o comportamento de quando o bot manda
  mensagem mudou nesta fase.

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

1. Crie um repositorio **privado** no GitHub (recomendado, ja que o codigo
   fica publico se o repo for publico — os precos e as datas nao sao segredo,
   mas os secrets do passo 4 nunca ficam expostos de qualquer forma).
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
export RESUMO_DIARIO=true   # forca o resumo diario neste teste manual

python -m bot_passagens.main
```

Se tudo estiver certo, voce recebe uma mensagem no Telegram com as janelas
mais baratas encontradas (o resumo diario, por causa do `RESUMO_DIARIO=true`
acima). **Isso marca a Fase 1 como pronta.**

Depois disso, o mesmo vai acontecer sozinho, automaticamente, pelo GitHub
Actions — sem precisar deixar nenhum computador ligado. Sem o
`RESUMO_DIARIO=true`, uma execucao sem nenhum alerta disparado nao manda
nada no Telegram (ver secao abaixo).

## Passo 7 — Cron externo (recomendado, corrige falhas do agendador do GitHub)

O agendador nativo do GitHub Actions (`schedule` no workflow) e conhecido por
falhar em disparar workflows automaticamente de vez em quando -- e mais
comum em repositorios novos ou pouco movimentados, e nao tem garantia
oficial de horario. Isso ja aconteceu com o nosso (a execucao das 8h nao
disparou sozinha em pelo menos uma ocasiao). Para nao depender so disso, dá
pra usar um servico externo gratuito que chama a API do GitHub nos horarios
certos, forcando o disparo por fora.

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
3. Crie **dois** cronjobs, um para cada horario:
   - **URL**: `https://api.github.com/repos/alexandre-avelino/bot-passagens/actions/workflows/monitor.yml/dispatches`
   - **Metodo**: `POST`
   - **Headers**:
     - `Authorization: Bearer SEU_TOKEN_AQUI`
     - `Accept: application/vnd.github+json`
     - `Content-Type: application/json`
   - **Body** (JSON): `{"ref":"main"}`
   - **Horario do 1º cronjob**: 12:05 UTC (8h05 em Cuiaba)
   - **Horario do 2º cronjob**: 00:05 UTC (20h05 em Cuiaba)
4. Use o botao de "test run" do cron-job.org pra confirmar que disparou uma
   execucao no GitHub (confira na aba **Actions** do repositorio).

O agendamento nativo do GitHub (`schedule` no `monitor.yml`) continua ativo
tambem -- nao tem problema os dois convivendo; se o do GitHub disparar por
conta propria em algum dia, so significa uma execucao a mais (nao quebra
nada). Se no futuro isso gerar mensagens duplicadas com frequencia, dá pra
remover o bloco `schedule:` do workflow e deixar so o cron externo no
comando.

## Historico de precos

A cada execucao, todos os voos encontrados (nao so os 3 enviados no Telegram)
sao gravados em `historico.db` (SQLite), que fica versionado dentro do
proprio repositorio — o workflow do Actions commita esse arquivo de volta
automaticamente depois de cada busca. Isso significa que:

- o repositorio vai acumular commits automaticos com a mensagem "Atualiza
  historico de precos" (2x por dia); isso e esperado, nao precisa fazer nada;
- se quiser consultar o historico manualmente, da pra abrir `historico.db`
  com qualquer visualizador de SQLite (ex: extensao "SQLite Viewer" no
  VS Code) ou rodar `sqlite3 historico.db "select * from buscas"` no
  terminal.

## Alertas e resumo diario

A cada execucao o bot avalia, para cada janela de datas, se alguma regra do
`config.yaml` bateu (comparando com o que ja estava no historico *antes*
desta execucao):

- preco menor ou igual a `alertas.preco_maximo`;
- queda de `alertas.queda_percentual`% ou mais desde a ultima vez que essa
  janela especifica foi checada;
- novo menor preco ja visto para essa janela especifica (se
  `alertas.novo_menor_preco: true`).

Se pelo menos uma bateu, chega um **alerta imediato** no Telegram — com rota,
datas, preco, o motivo do alerta e a comparacao com a media dos precos dessa
janela nos ultimos 30 dias.

Alem disso, a execucao das ~8h (horario de Cuiaba) sempre manda um
**resumo diario** com as 3 janelas mais baratas do dia e o menor preco ja
registrado em todo o historico, independente de ter batido alguma regra.

**Importante**: se nao bateu nenhuma regra E a execucao nao e a das 8h
(ou seja, a execucao das ~20h na maioria dos dias), **o bot nao manda nada
no Telegram**. Isso e o comportamento esperado, nao um bug — significa que
os precos nao mudaram o suficiente para valer um aviso. Se quiser conferir
que o bot rodou mesmo assim, os logs de cada execucao ficam em
**Actions** no GitHub.

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

- **Fase 4** (opcional): comandos interativos no Telegram (`/hoje`,
  `/historico`, `/config`) e dashboard com grafico.

Quando quiser seguir para a Fase 4, e so pedir.
