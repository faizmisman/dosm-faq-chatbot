# Agent Context (Copilot / ChatGPT)

**You are assisting on the DOSM Insights Platform. Preserve contracts and keep changes minimal & safe.**

## Invariants

- Do **not** change `/predict` response shape without updating tests & docs.  
- RAG must **always** cite sources and refuse/clarify when ungrounded.  
- Use structured logging utilities; no raw prints.  

## Safe tasks to propose

- Add unit tests for refusal/clarify paths.  
- Factor small helpers (prompt templates, vector utils).  
- Add Prometheus counters for refusal/low confidence.  

## Avoid without human approval

- New frameworks, major topology changes, paid providers.  
- Breaking API or CI/CD triggers.  
- Storing secrets outside Key Vault/MSI.  
