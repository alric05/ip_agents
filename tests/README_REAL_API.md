# Real API Integration Testing

Two levels of real-API tests live in [test_derwent_migration.py](test_derwent_migration.py):

| Marker | What it tests | Skip condition |
|--------|---------------|----------------|
| `real_api` | Direct Derwent API calls (bypasses server) | `DERWENT_JWT_TOKEN` unset |
| `real_server` | Full stack: curl → server.py → agent → Derwent API | `DERWENT_JWT_TOKEN` unset **or** `localhost:8000/health` unreachable |

The **`real_server`** path is what matches how the frontend and your teammates actually call the agent. Prefer it when validating end-to-end behavior.

---

## Full-stack test (`real_server`)

### 1. Start the server

```bash
# Terminal 1 — requires Azure OpenAI env vars in .env
uvicorn server:api --port 8000 --reload
```

Wait for `Uvicorn running on http://0.0.0.0:8000`. Sanity check:

```bash
curl http://localhost:8000/health
```

### 2. Run the integration test

```bash
# Terminal 2
DERWENT_JWT_TOKEN='<your-jwt>' \
  pytest tests/test_derwent_migration.py -m real_server -v -s
```

The `-s` flag is important — it shows the live SSE event stream (`tool_start`, `tool_end`, `message`, `done`, …) so you can see the agent invoking `search_derwent_citations` with the injected JWT.

### 3. What the test asserts

- HTTP 200 on `/chat/stream`
- At least one `tool_start` event named `search_derwent_citations` or `search_derwent_patents_fld`
- No `tool_end` contains auth-error markers (`"Invalid signature"`, `"Invalid or expired authentication token"`, `"Authentication required"`)
- Stream ends with a `done` event (not `error`)
- On failure, dumps the full collected event log

---

## Direct-API tests (`real_api`)

These hit Clarivate Derwent endpoints directly with a Bearer JWT. Useful for low-level debugging of the client + payload:

```bash
DERWENT_JWT_TOKEN='<your-jwt>' \
  pytest tests/test_derwent_migration.py -m real_api -v
```

These can fail with `401 "Invalid signature"` if the JWT isn't accepted by `api.clarivate.com` directly (common for dev-stable tokens meant to be exchanged server-side). The `real_server` flow bypasses this because the server injects the JWT into the LangGraph config exactly as the frontend does.

---

## Default run (mocked only)

```bash
pytest tests/test_derwent_migration.py -v
```

→ **45 passed**, `real_api` tests (6) and `real_server` test (1) auto-skip with reason.

---

## Troubleshooting

- **`localhost:8000/health unreachable`** — server isn't running. Start it in Terminal 1.
- **`DERWENT_JWT_TOKEN not set`** — prefix your command: `DERWENT_JWT_TOKEN='...' pytest ...`
- **Server fails to start** — check Azure OpenAI env vars in `.env` (`AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT_NAME`, `AZURE_OPENAI_API_VERSION`)
- **Test times out** — agent can take minutes for complex queries. Default timeout is 300s; bump `TestDerwentViaServer.REQUEST_TIMEOUT` if needed.
- **`No Derwent tool was invoked`** — the LLM didn't pick up the tool. Check the SSE log (printed at end of test) to see which tools it did use, and refine the `message` to be more explicit.
