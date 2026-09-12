# Spec Driven Development principles this plugin follows

Distilled from the MySpec platform's own reviewer rubrics and from current SDD practice (GitHub Spec Kit, OpenSpec, Kiro, Anthropic's Claude Code guidance).

1. Spec is the source of truth. When code and spec conflict, the spec is authoritative. When the spec itself is wrong, change it with the user before changing code; never adapt it to match code silently. An outdated spec is still better than no spec, so keep it current rather than abandoning it.
2. Fixed reading order. Governing principles (constitution) first, then requirements, then solution, then tasks. Load only the sections a task needs when the bundle is large; long context buries the rules.
3. Clarify before coding. Bounded, multiple-choice questions; answers written into the spec, not left in chat.
4. One task per iteration, sized for one session. Parallel work only for tasks with met dependencies and disjoint files.
5. Acceptance criteria are tests. Each EARS+ criterion becomes at least one test named for traceability. A green run is the stop condition.
6. Traceability end to end: requirement id, then task `_Requirements:_` line, then test name. Verification reports coverage, not vibes.
7. Record progress where collaborators see it: the checkbox in `tasks.md` on the platform, written with optimistic concurrency so nobody's work is overwritten.
8. Verification is a separate, read-only pass with severities. Remediation only after the user approves, and gap-filling is append-only.
9. Spec updates are part of the definition of done. Drift is fixed in the document, then in the code.
10. Human review gates: approve the spec before implementing, review each milestone before the next, and review spec changes alongside code changes.
11. Minimal but complete specs: reviewable in one sitting, explicit out-of-scope, no metadata footers, no padding.
12. Session handoff: checkboxes plus a short progress note plus git history let the next session resume without re-deriving state.
