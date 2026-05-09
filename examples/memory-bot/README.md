# memory-bot

A plugin that stores and recalls facts via AURORAZ's long-term memory.

Two tools:
- `memory_bot_remember(text)` — stores a fact
- `memory_bot_recall(query, k=3)` — semantic search

## Permissions

- `memory:read` — for `recall`
- `memory:write` — for `remember`

## Try it

After installing into AURORAZ:

> "Remember that my favorite pizza topping is mushrooms."
> "What did I tell you I liked on pizza?"

The plugin tags every memory with its plugin id automatically — you only
see your own plugin's stored memories, never other plugins'.
