Status: ready-for-agent

## What to build

The evaluation system with a Golden Dataset editor and RAGAS benchmark dashboard. Users can define (Query, expected Answer) pairs, run RAGAS evaluation (answer relevancy, faithfulness, context precision, context recall), and view scores in a dashboard with per-Query breakdowns. The Golden Dataset is editable through the UI, and eval runs are persisted so scores can be compared over time.

## Acceptance criteria

- [ ] `GET /api/eval/golden-dataset` lists all Golden Dataset entries
- [ ] `POST /api/eval/golden-dataset` creates a new (Query, expected Answer) pair
- [ ] `DELETE /api/eval/golden-dataset/{id}` removes an entry
- [ ] `POST /api/eval/run` triggers a RAGAS evaluation against all Golden Dataset entries
- [ ] Evaluation runs the full query pipeline for each Golden Dataset Query and computes: answer relevancy, faithfulness, context precision, context recall
- [ ] `GET /api/eval/results` returns all eval runs with aggregate scores + per-Query breakdown
- [ ] React UI: Golden Dataset management page (table with add/edit/delete, inline editing)
- [ ] React UI: Evaluation dashboard page (run button, aggregate scores as cards, per-Query score table, historical run comparison chart)
- [ ] RAGAS scores are computed server-side using the `ragas` Python library
- [ ] Eval runs are stored in PostgreSQL `eval_runs` table (id, scores JSON, created_at)

## Blocked by

- #04-simple-route-query-pipeline
