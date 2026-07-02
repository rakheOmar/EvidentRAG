Status: ready-for-agent

## What to build

The evaluation system with a Golden Dataset editor and RAGAS benchmark dashboard. Users can define (Query, expected Answer) pairs, run RAGAS evaluation (answer relevancy, faithfulness, context precision, context recall), and view scores in a dashboard with per-Query breakdowns. The Golden Dataset is editable through the UI, and eval runs are persisted so scores can be compared over time.

## Acceptance criteria

- [ ] `GET /api/v1/evaluation-dataset` returns `200 OK` and lists all evaluation dataset entries
- [ ] `POST /api/v1/evaluation-dataset` creates a new evaluation dataset entry `(query_text, expected_answer)` and returns `201 Created`; validation failures return `422`
- [ ] `GET /api/v1/evaluation-dataset/{entry_id}` returns `200 OK` with one evaluation dataset entry; missing entries return `404`
- [ ] `PATCH /api/v1/evaluation-dataset/{entry_id}` updates one evaluation dataset entry and returns `200 OK`; missing entries return `404` and validation failures return `422`
- [ ] `DELETE /api/v1/evaluation-dataset/{entry_id}` removes an entry and returns `204 No Content`; missing entries return `404`
- [ ] `POST /api/v1/evaluations` triggers a RAGAS evaluation run against all evaluation dataset entries and returns `201 Created` with an `evaluation_id`; invalid requests return `422`
- [ ] Evaluation runs the full query pipeline for each Golden Dataset Query and computes: answer relevancy, faithfulness, context precision, context recall
- [ ] `GET /api/v1/evaluations` returns `200 OK` with all evaluation runs and aggregate scores + per-Query breakdown
- [ ] `GET /api/v1/evaluations/{evaluation_id}` returns `200 OK` with one evaluation run and detailed results; missing evaluations return `404`
- [ ] React UI: Golden Dataset management page (table with add/edit/delete, inline editing)
- [ ] React UI: Evaluation dashboard page (run button, aggregate scores as cards, per-Query score table, historical run comparison chart)
- [ ] RAGAS scores are computed server-side using the `ragas` Python library
- [ ] Eval runs are stored in PostgreSQL `eval_runs` table (id, scores JSON, created_at)

## Blocked by

- #04-simple-route-query-pipeline
