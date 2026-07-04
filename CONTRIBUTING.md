# Contributing

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your own API keys/tokens
```

See `README.md` for the full setup and layout, and `AGENTS.md` for
conventions on adding skills and the pm2 service topology.

## Making changes

- Follow the existing import/layout conventions in `AGENTS.md` (skill
  folders, absolute `src.*` imports, `SkillTool` subclasses, etc).
- If you change a non-test source file, add or update a test alongside it.
- Keep skills self-contained: implementation + `tools.py` + a `<skill>.md`
  description live together under `skills/<skill_name>/`.

## Running checks locally

```bash
python -m pytest tests/
ruff check --select E9,F .
cd order_explorer_site/frontend && npm run lint   # if you touched the frontend
```

A git pre-commit hook (`.githooks/pre-commit`) runs these same checks
automatically once enabled:

```bash
git config core.hooksPath .githooks
```

If the hook rejects a commit, fix the issue and re-commit rather than
bypassing it with `--no-verify`.

## Submitting a change

1. Fork the repo and create a branch off `main`.
2. Make your change with tests passing locally.
3. Open a pull request describing what changed and why.

## Reporting bugs / requesting features

Open a GitHub issue with steps to reproduce (for bugs) or the motivating
use case (for features). For security issues, see `SECURITY.md` instead of
filing a public issue.
