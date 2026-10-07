# payments-mcp-server

![CI](https://github.com/geethika-chigurupati/payments-mcp-server/actions/workflows/ci.yml/badge.svg)

A small [MCP](https://modelcontextprotocol.io) server, built with [FastMCP](https://github.com/PrefectHQ/fastmcp),
that lets AI agents create, look up, and refund payments against a **mock in-memory ledger**.
No real money moves and no real payment provider is called. It is a learning and portfolio project
about designing safe tools for agents.

## Tools

| Tool | Scope needed | What it does |
|---|---|---|
| `create_payment` | `payments:write` | Creates a payment. Needs a unique `idempotency_key`. |
| `get_payment` | `payments:read` | Returns a payment and its refund status. |
| `refund_payment` | `payments:write` | Refunds part or all of the remaining balance. |

## Design decisions

- **Idempotency:** retrying `create_payment` with the same key and same details returns the original
  payment (`created: false`) instead of creating a duplicate. Reusing a key with *different* details
  is rejected. Agents retry often, so this matters.
- **Money as decimal strings:** amounts are `Decimal` values parsed from strings like `"19.99"`,
  never floats. At most 2 decimal places, positive, and capped.
- **Refund rules:** partial refunds are allowed, total refunds can never exceed the original amount,
  and a fully refunded payment cannot be refunded again.
- **JWT scope-based auth (HTTP mode):** bearer tokens are verified with HS256. The algorithm is pinned
  on the server (the token header cannot choose it), and `exp`, `sub`, and `iss` are required.
  Read and write operations need different scopes.
- **Fail closed:** auth is required unless `REQUIRE_AUTH=false` is set explicitly, and the server
  refuses to start in HTTP mode without a secret of at least 32 characters.
- **Testable core:** the ledger and auth logic have no MCP imports, so they are unit tested directly.

## Quickstart

Requires Python 3.11+.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

### Run over HTTP with auth

```bash
export PAYMENTS_JWT_SECRET="replace-with-a-random-string-of-32-or-more-characters"
python -m payments_mcp.server --http --port 8000          # serves http://127.0.0.1:8000/mcp

# in another terminal (same secret exported), create a development token:
python -m payments_mcp.token --scopes payments:read,payments:write
```

Send the token as `Authorization: Bearer <token>` from your MCP client.

### Run over stdio for local development (no auth)

```bash
REQUIRE_AUTH=false python -m payments_mcp.server
```

Auth is checked on HTTP requests, so use `--http` whenever you want it enforced.

## Example client call

```python
import asyncio
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

transport = StreamableHttpTransport(
    "http://127.0.0.1:8000/mcp", headers={"Authorization": "Bearer <token>"}
)

async def main():
    async with Client(transport) as client:
        result = await client.call_tool(
            "create_payment",
            {"amount": "12.50", "currency": "USD", "idempotency_key": "order-1001"},
        )
        print(result.data)

asyncio.run(main())
```

## Testing

- Unit tests cover the ledger (idempotency, validation, refund rules), the auth module
  (expired, wrong-secret, wrong-issuer, unsigned, and missing-scope tokens), and the MCP tools
  through an in-memory FastMCP client. They run in CI on every push.
- Auth over a live HTTP connection was also checked manually: no token is rejected, a read-only
  token cannot write, and a read/write token succeeds. There is no automated test for the live
  HTTP path yet.
- Tested with Python 3.12 and 3.14 and FastMCP 4.0.x.

## Limitations

- The ledger is in memory and single-process. Data is lost when the server stops.
- Tokens are issued by a local development script. There is no OAuth2 flow or key rotation.
- No rate limiting, audit log, or real payment provider.

## Roadmap

- [ ] Persist payments in PostgreSQL
- [ ] Webhook delivery with retries for payment events
- [ ] Rate limiting and an audit log
- [ ] Automated integration test over HTTP
- [ ] Docker image and `docker compose` setup

## License

MIT
