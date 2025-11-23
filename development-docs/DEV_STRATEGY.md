# Development Strategy & Guardrails

_Last updated: 2025-11-23 (post CronJob scaffold, synthesis placeholder, Key Vault CSI integration stub)_

This document defines the **north star**, **invariants**, and **decision criteria** to prevent scope drift and maintain alignment with the dual goals (LLM Engineer + MLOps Engineer).

---
## 1. North Star
Deliver a production-grade, citation-grounded RAG FAQ service over DOSM open data with:
- Reliable `/predict` endpoint (fast, stable, auditable)
- Transparent sourcing (citations; never hallucinate silently)
- Repeatable ingestion + evaluation pipeline
- Secure, cost-conscious Azure deployment (single AKS cluster, namespaces per env)

Everything we build must either:
1. Improve answer quality / reliability
2. Improve operational robustness / security / cost
3. Simplify maintainability (easier future dataset refreshes or model swaps)
If a proposed change does not contribute to at least one, defer or reject.

---
## 2. Invariants (Do Not Break)
- `/predict` response shape (prediction.answer, citations[], confidence, failure_mode, latency_ms, model_version)
- Refusal / clarification logic when confidence below thresholds
- Citations always included when answering (non-refusal)
- Health and metrics endpoints names (`/health`, `/metrics`)
- Structured logging with request_id & model_version
- No plaintext secrets committed; Key Vault / sealed K8s secrets only
- Vector store path configurable via `VECTORSTORE_DIR` (no hard-coded host paths)

---
## 3. Scope Boundaries
Out-of-scope until explicitly approved:
- Multi-dataset blending or semantic stitching
- Advanced LLM prompt engineering requiring external paid providers
- Real-time streaming responses
- Complex feature store integration
- Full user auth / RBAC system (API key only for now)

---
## 4. RAG Enhancement Roadmap (Minimalist)
| Phase | Focus | Deliverables | Exit Criteria |
|-------|-------|--------------|---------------|
| P1 | Basic retrieval | Chunking, embeddings, vector store ingestion script | /predict returns grounded snippet w/ citation |
| P2 | Prompt + synthesis | Add LLM call with answer template, refusal escalation | 80% eval hit-rate baseline |
| P3 | Evaluation harness | queries.jsonl, evaluators CLI, metrics report | Automated hit-rate & latency summary artifact |
| P4 | Refresh automation | CronJob or pipeline to re-ingest monthly dataset | Successful scheduled run & updated model_version |
| P5 | Quality tuning | Chunk size experimentation, confidence calibration | Reduced clarify misfires & improved p95 latency |

Avoid starting next phase before exit criteria satisfied.

---
## 5. Decision Criteria Matrix
| Proposal | Ask | Impact Axis | Mandatory Checks |
|----------|-----|------------|------------------|
| New library | Add vector DB X | Reliability / Quality | Size, maintenance, license, integration complexity |
| Infra change | Extra node pool | Cost / Performance | Utilization metrics show >70% sustained CPU |
| Model upgrade | Larger embedding model | Quality / Cost | Benchmark latency & memory delta; eval hit-rate gain >=5% |
| Secret handling | Introduce CSI driver | Security / Ops | Role assignments proven; fallback documented |

Reject changes lacking measurable impact or clear rollback plan.

---
## 6. Evaluation Cadence
- Run full eval suite (queries.jsonl) before any prod promotion.
- Re-run after: dataset refresh, chunking strategy change, embedding model change, prompt change.
- Track metrics: retrieval hit-rate, hallucination rate, p95 latency, refusal vs low-confidence ratio.
- Append results row to `development-docs/EVALUATION.md` (or separate `EVAL_RESULTS.md`).

---
## 7. Logging & Metrics Minimums
Add or retain metrics for:
- HTTP requests (count, latency histogram)
- RAG decisions (answer, clarify, refuse counts)
- Low-confidence events (counter)
- Ingestion duration (Job logs; consider future metric)
Add DB logging fields: is_refusal, is_low_confidence, confidence, latency_ms.

---
## 8. Security & Compliance Checklist (Per Release)
- [ ] No secrets in values files / git history (scan diff)
- [ ] Key Vault access via managed identity validated
- [ ] Postgres SSL enforced (sslmode=require)
- [ ] API key rotation schedule current (quarterly) / set reminder
- [ ] Image scanned (trivy/sbom planned future) – track action item

---
## 9. Operational Playbook Alignment
Follow `OPERATIONS.md` for:
- Ingress changes (host, TLS toggle) only through Helm values
- Rollbacks: `helm rollback` or deployment undo; never manual pod edits
- Scaling: adjust HPA targets only after observing metrics trend > 1h

---
## 10. Naming Consistency
Standardize primary release name: `faq-chatbot-dosm-insights`.
Image repos: `dosm-faq-chatbot`. Model versions follow: `dosm-rag-vX.Y`.
Dataset card MUST reflect active dataset powering embeddings.

---
## 11. Git Discipline
- Feature branches: `feat/<short-key>`; hotfix: `fix/<issue>`
- PR must state: PURPOSE, INVARIANTS IMPACT (none / list), RISK & ROLLBACK.
- Merge requires green CI (tests + lint) & updated docs if contracts touched.

---
## 12. Backlog Triage Rules
Priority order: (1) Security/availability > (2) Data quality > (3) Evaluation > (4) Performance > (5) Nice-to-have UX.
Defer items that increase complexity without near-term measurable benefit.

---
## 13. Rollback & Experiment Isolation
All experimental flags behind env vars or Helm values (e.g. `RAG_PROMPT_MODE=beta`).
Rollback procedure documented before enabling new path.

---
## 14. Monthly Refresh Process (Target)
1. CronJob runs ingestion script with current dataset snapshot.
2. Generates new vector store in PVC → atomic swap symlink or versioned directory.
3. Bumps `MODEL_VERSION` to next minor.
4. Triggers evaluation Job; results appended to report.
5. Manual prod promotion after review.

---
## 15. Performance Budget
- p95 `/predict` < 1500 ms (P2 target) excluding cold-start.
- Vector search < 250 ms p95.
- Embedding build (ingestion) < 5 min for current dataset scale.
Exceeding budget triggers investigation before adding features.

---
## 16. Prompt & Answer Policy (Future P2)
- Always ground answers only in retrieved context; no speculative extrapolation.
- If context insufficient: return clarify (ask for year/indicator) or refuse.
- Format answer: concise sentence(s) + optional structured bullet if multi-row.

---
## 17. Extension Guidelines
When adding:
- New dataset: replicate ingestion module; must not break existing dataset service.
- Additional endpoints: require justification (perf, ops, tooling); version docs.
- External services: minimal dependency footprint, evaluate vendor lock-in.

---
## 18. Open Action Items (Track Separately)
Completed (moved from action list):
- Evaluation harness (queries.jsonl + CLI)
- Refusal & low-confidence metrics
- Key Vault CSI driver scaffold (disabled by default)
- CronJob ingestion + schedule scaffold
- Initial template-based synthesis (Phase P2 placeholder)
- Confidence normalization & env threshold (`CONF_THRESHOLD`)

Remaining / Upcoming:
- True LLM provider integration (external or local) with guarded prompt
- Dataset expansion & improved chunking for higher hit-rate
- TLS ingress enablement & removal of temporary image pull secret
- Workload Identity for Key Vault (replace sync secret approach)
- Automated eval on ingestion completion
- Chunk size experimentation (Phase P5)

---
## 19. Acceptance Gate for Prod Promotion
Must have:
- Latest eval metrics row
- No failing tests
- Security checklist complete
- Ingestion artifacts versioned & consistent with dataset card
- Rollback plan documented in PR

---
## 20. Anti-Patterns To Avoid
- Embedding rebuilds inside request path
- Storing large artifacts in container image beyond necessity
- Silent API contract changes
- Hard-coding environment-specific values in code

---
## 21. How To Propose A Change
Open issue with template:
```
Title: <Change Summary>
Goal: <Which north-star axis it improves>
Impact: <Quality / Reliability / Cost / Security>
Invariants: <List unaffected or justify changes>
Risks: <Operational / Security / Performance>
Rollback: <Command or steps>
Metrics: <What to measure pre/post>
ETA: <Estimate>
```
Merge only after maintainer review.

---
## 22. Living Document
Review weekly; update `Last updated` and summarize changes in commit message. Larger strategic shifts require stakeholder approval and doc diff highlighting changed sections.

---
## 23. Quick Cheatsheet
- Validate invariants: `pytest -q` + contract tests.
- Re-ingest dataset: Helm Job or Cron → confirm new `MODEL_VERSION`.
- Promote release: ensure eval metrics improved or equal.

---
## 24. Exit Criteria For Initial MVP
- RAG retrieval working & citations returned.
- Evaluation harness present with baseline metrics.
- Deployment reproducible via Helm & CI.
- Security checklist passes.
- Documentation (ARCHITECTURE, DEV_STRATEGY) consistent and up to date.

---
_Adhere to these guardrails to maintain trajectory and avoid unnecessary pivots._
