# API and client error contract

All versioned API failures use this envelope:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed",
    "details": {"fields": []},
    "request_id": "..."
  }
}
```

## Endpoint audit

| Endpoint | Success | Defined failures |
| --- | --- | --- |
| `GET /health` | `200` | `500` only for unexpected middleware failures |
| `GET /api/v1/model-context` | `200` | `503` when model context is unavailable |
| `POST /api/v1/threads` | `201` | `422` invalid body, `503` queue unavailable |
| `GET /api/v1/threads` | `200` | `422` invalid pagination |
| `GET /api/v1/threads/{thread_id}` | `200` | `404` unknown thread |
| `POST /api/v1/threads/{thread_id}/messages` | `201` | `404` unknown thread, `422` invalid body, `503` queue unavailable |
| `GET /api/v1/threads/{thread_id}/messages/{message_id}/events` | `200` SSE | `404` unknown thread/message |
| `PUT /api/v1/sentence-traces/{trace_id}/rating` | `200` | `404` unknown trace, `422` invalid rating, `503` embedding service unavailable |
| `POST /api/v1/documents` | `201` | `400` invalid PDF/size, `404` unknown Source, `409` deleted Source, `415` media type, `422` multipart validation |
| `GET /api/v1/documents` | `200` | `422` invalid pagination |
| `GET /api/v1/documents/{document_id}` | `200` | `404` unknown Document Version |
| `GET /api/v1/documents/{document_id}/events` | `200` SSE | `404` unknown Document Version |
| `POST /api/v1/documents/{document_id}/retries` | `200` | `404` unknown version, `409` version is not failed |
| `DELETE /api/v1/documents/{document_id}` | `204` | `404` unknown version |

Resource paths use plural nouns. Actions are represented as subresources (`rating`, `retries`), and IDs are opaque path parameters rather than titles or filenames.

## Client presentation policy

- `inline`: `400` and `422`; the caller keeps the form/message active and renders the returned `error.message` or `error.details.fields` beside the relevant field.
- `toast`: recoverable `404` and `409`; the user can continue working elsewhere.
- `dialog`: authentication/authorization failures, network failures, and `5xx`/`503`; the failure blocks the current operation and includes `request_id` when available.
