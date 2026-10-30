# AGENTS.md

- Workflow: coder -> independent validator -> Codex Sol final gate -> PR + CodeRabbit. Keep PRs in draft until the final gate approves.
- Update README.md in every PR.
- Polars only; no pandas.
- Every new row carries a `data_source` column (codes in `config/data_sources.py`).
- Point-in-time rule: no join without `as_of_ts`; labels are joined only inside training/evaluation code.
- LLM features must pass `cutoff_guard`; historical LLM results are labelled exploratory.
- Never commit licensed data, credentials, notebook outputs, or data files outside `tests/fixtures`.
- Test command: `pytest -m "not spark and not databricks and not live"`.
- Never place orders, deploy, or mutate the shared Databricks workspace without explicit owner approval. Paper trading only.
