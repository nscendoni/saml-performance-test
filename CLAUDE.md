# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

After `pip install -e .`, the `saml-perf` CLI is available as a console script (entry point: `cli:main`).

## Common Commands

```bash
# Generate test signing keys
saml-perf generate-keys -o ./keys -n test-idp --cn "My Test IdP"

# Run a performance test
saml-perf test \
    --sp-url https://sp.example.com/saml/acs \
    --issuer https://idp.example.com \
    --private-key ./keys/test-idp.key \
    --certificate ./keys/test-idp.crt \
    --users 100 --concurrency 10 \
    --groups admins --groups users \
    --verbose

# Generate a single assertion for debugging
saml-perf generate \
    --issuer https://idp.example.com \
    --sp-url https://sp.example.com/saml/acs \
    --private-key ./keys/test-idp.key \
    --certificate ./keys/test-idp.crt \
    --user-id john.doe --email john.doe@example.com \
    --groups admins

# View a saved results file
saml-perf report results.json
```

Use `--debug` on the `test` command to capture full response bodies and headers per request.

## Architecture

The tool simulates an Identity Provider (IdP) sending signed SAML 2.0 POST binding assertions to a Service Provider (SP).

**Module responsibilities:**

- **`saml_builder.py`** (`SAMLAssertionBuilder`) — Builds SAML 2.0 XML using `lxml`, signs with RSA-SHA256 via `signxml`. The `build_signed_response()` method returns a base64-encoded response ready for HTTP POST. Loads PEM key/cert from disk at construction time.

- **`user_generator.py`** — Two generators: `UserGenerator` (random names/emails) and `SequentialUserGenerator` (deterministic index-based IDs). `TestUser` is the shared dataclass used by both.

- **`performance_tester.py`** (`SAMLPerformanceTester`) — Async runner using `aiohttp`. Concurrency is controlled by `asyncio.Semaphore`. Each request sends a GET to SP root first (to establish session/cookies), then POSTs the `SAMLResponse`. HTTP 2xx–3xx are treated as success. `TestResults.calculate_statistics()` computes p95/p99 from sorted response times.

- **`cli.py`** — Click CLI wiring the four commands (`test`, `generate`, `generate-keys`, `report`). The `test` command calls `run_performance_test()` from `performance_tester.py`, which orchestrates builder + generator + tester.

**Data flow for `saml-perf test`:**
1. `SAMLAssertionBuilder` loads key/cert
2. `UserGenerator` generates N synthetic `TestUser` objects
3. `SAMLPerformanceTester.run_test()` fans out async tasks, one per user
4. Each task calls `build_signed_response()` → base64-encodes → HTTP POSTs to SP ACS URL
5. `TestResults.calculate_statistics()` aggregates timing stats

## AEMaaCS Testing

To test against AEM as a Cloud Service:
1. Generate keys, import the `.crt` to AEM, note the `certalias___xxx` value
2. Configure the SAML handler OSGi config with `idpCertAlias`, `serviceProviderEntityId`, and `groupMembershipAttribute`
3. Run: `saml-perf test --issuer saml-idp --sp-url http://localhost:4503/<path>/saml_login --private-key ./keys/test-idp.key --certificate ./keys/test-idp.crt --groups admins -n 10`
