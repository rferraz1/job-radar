# Deploy

## Mac (agora) — launchd

1. `cd ~/git/job-radar && python -m venv .venv && .venv/bin/pip install -r requirements.txt`
2. `.venv/bin/python -m playwright install chromium`
3. `cp .env.example .env` e preencher (`GEMINI_API_KEY`, `TELEGRAM_*`, `CV_PATH`).
   `CV_PATH` **precisa ser caminho absoluto** (roda via launchd/systemd, sem working
   dir garantido) — CV vazio/inacessível desliga a análise LLM do ciclo.
4. `cp deploy/com.rodolfo.jobradar.plist ~/Library/LaunchAgents/`
   — ajustar `WorkingDirectory` e o path do python se o checkout não for `~/git/job-radar`.
5. `launchctl load ~/Library/LaunchAgents/com.rodolfo.jobradar.plist`
6. Testar 1 ciclo na mão: `.venv/bin/python main.py --perfil brasil --once`
7. Logs: `/tmp/jobradar.out.log` e `/tmp/jobradar.err.log`.

Desligar: `launchctl unload ~/Library/LaunchAgents/com.rodolfo.jobradar.plist`

**Não reinicie o processo no meio de um ciclo** (mesma disciplina do workout-generator):
o ciclo é curto (~2–5 min), espere terminar. Matar no meio pode deixar o SQLite
num estado meia-boca (raro, mas evitável).

## VM (depois) — systemd

1. `git clone` em `/opt/job-radar`, `python -m venv .venv`, `pip install -r requirements.txt`, `playwright install chromium`.
2. Criar `/opt/job-radar/.env` com o mesmo conteúdo do Mac.
3. `cp deploy/jobradar.service /etc/systemd/system/`
4. Criar `/etc/systemd/system/jobradar.timer` (a cada 3h, 07–22) OU um cron equivalente.
5. `systemctl daemon-reload && systemctl enable --now jobradar.timer`
6. Migrar o histórico: `scp` do `data/jobs.db` do Mac pra VM ANTES do primeiro run
   (senão o `BancoVazioSuspeito` aborta, ou notifica tudo de novo).

## SQLite -> Postgres (só se precisar)

`database/database.py` é o único arquivo que toca o banco. Trocar as funções
`_conectar`/`iniciar_db`/`salvar_vaga`/etc. pra um driver Postgres, mantendo as
mesmas assinaturas. Nenhum outro módulo muda.
