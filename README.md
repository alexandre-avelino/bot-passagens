# Bot de monitoramento de passagens aereas

Monitora precos de passagens (via Google Voos, sem API paga) e avisa no Telegram
quando encontra as janelas mais baratas dentro das datas que voce configurar.
Roda de graca no GitHub Actions, 2x por dia.

Este README assume que voce nao mexe com codigo. Siga na ordem.

## O que ja esta pronto (Fases 1 e 2)

- Gerador de combinacoes de datas (ida/volta) respeitando a regra do dia
  obrigatorio, com testes automatizados.
- Busca real de precos (Google Voos) via a biblioteca `fast-flights`,
  incluindo horario de ida/chegada e escalas.
- Envio de mensagem para o Telegram com as 3 janelas mais baratas encontradas.
- Workflow do GitHub Actions ja configurado para rodar 2x por dia.
- Historico de precos em SQLite (`historico.db`), commitado de volta no
  repositorio a cada execucao — todo voo encontrado fica registrado, nao so
  o top 3 enviado no Telegram.

Ainda **nao** existem os alertas que usam esse historico (teto de preco,
queda %, novo menor preco) — isso e a Fase 3 (ver final deste arquivo).

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
- `alertas.preco_maximo`: teto de preco (usado nas proximas fases).

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

Se tudo estiver certo, voce recebe uma mensagem no Telegram com as 3 janelas
mais baratas encontradas. **Isso marca a Fase 1 como pronta.**

Depois disso, o mesmo vai acontecer sozinho, automaticamente, pelo GitHub
Actions — sem precisar deixar nenhum computador ligado.

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
  terminal;
- esse historico ainda nao é usado para gerar alertas — isso e a Fase 3.

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

Se mesmo assim voce comecar a ver avisos de erro nas execucoes (aparecem no
final da mensagem do Telegram e nos logs do Actions), tente, em ordem:

- reduzir a lista de `destinos` no `config.yaml`;
- reduzir ainda mais a frequencia (editar os `cron` em
  `.github/workflows/monitor.yml`, por exemplo para 1x/dia);
- aumentar `DELAY_ENTRE_BUSCAS_SEGUNDOS` em `bot_passagens/main.py`.

## Proximas fases (ainda nao implementadas)

- **Fase 3**: alertas completos (teto de preco, queda percentual, novo menor
  preco historico) e resumo diario com contexto ("X% abaixo da media de 30
  dias"), usando o historico da Fase 2.
- **Fase 4** (opcional): comandos interativos no Telegram (`/hoje`,
  `/historico`, `/config`) e dashboard com grafico.

Quando quiser seguir para a Fase 3, e so pedir.
