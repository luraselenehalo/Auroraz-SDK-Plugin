# research-bot

Demonstrates the Stage 7 reasoning API: a plugin invoking AURORAZ's
Fractal 1:3 cognitive engine via `aurora.reasoning.ask()`.

## What it does

Registers two tools:

| Tool | Level | Cost | Use when |
| --- | --- | --- | --- |
| `research_bot_quick_research` | K1 | 1 LLM call | general questions, single-pass answers |
| `research_bot_deep_research`  | K3 | up to 3 LLM calls | complex questions, comparisons, analysis |

The K3 path runs draft → self-verify → optional refine. Lower temperature
on the verifier pass makes it stricter than chat-mode K3. Most queries
finish in two passes (verify says PASS) and one in three needs refinement.

## Permissions

```yaml
permissions:
  - reasoning:k3       # implies k0/k1/k2 via the additive hierarchy
  - notifications:show # for the on_startup greeting
```

If you want the quick tool only, declare `reasoning:k1` instead — calling
`deep_research` will then raise `PermissionDeniedError` server-side.

## Running

Install + enable like any SDK plugin:

```bash
auroraz install ./examples/research-bot
auroraz enable research-bot
```

Then in a chat that triggers the deep_research tool:

```
> compare REST and GraphQL
[research-bot K3 reasoning, ~8s]
REST exposes resources via stable URLs… [draft]
[verify pass] PASS
→ final answer returned
```

## Default rate limits

| Level | Per minute | Per day |
| --- | --- | --- |
| K0 | unlimited | unlimited |
| K1 | 60 | 1,000 |
| K2 | 30 | 500 |
| K3 | 10 | 100 |

Override via env: `AURORAZ_REASONING_RATE_K3_PER_MIN=20`, etc.
