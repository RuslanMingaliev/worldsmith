---
name: create-agent-task
description: Walk the user through filling the worldsmith agent-task issue form and produce a body suitable for `gh issue create --body-file -`. Trigger on requests like "create an agent task", "file an agent intake issue", "open an agent:task", "/create-agent-task".
---

# create-agent-task

Goal: produce a complete issue body matching `.github/ISSUE_TEMPLATE/agent-task.yml` so the user can file it with `gh issue create --title "[agent] <short>" --body-file -`.

## Flow

1. Ask the user, in this order, one prompt at a time (or all at once if they prefer to paste a draft):
   - **Short title** — used after the `[agent] ` prefix.
   - **Goal** — one paragraph, what should be true after this run.
   - **Scope** — which knowledge files / spec sections / IR keys are in scope.
   - **Affected modules** (optional) — comma-separated module names from `ir/module_plan.yaml`. Leave blank if unsure.
   - **Constraints** — what the agent must NOT touch.
   - **Acceptance criteria** — bulleted, verifiable statements.

2. Render the body using exactly these headings, in this order (matches the Issue Form fields):

   ```
   ### Goal

   <goal>

   ### Scope

   <scope>

   ### Affected modules (optional)

   <modules or "—">

   ### Constraints

   <constraints or "None.">

   ### Acceptance criteria

   <bulleted list>
   ```

3. **Decomposition check** — before showing the rendered body, evaluate against three over-scoping signals (these mirror `tooling/check_issue_scope.py`, the server-side gate in `agent-intake.yml`):

   - **Module count.** `Affected modules` lists more than 2 entries.
   - **Goal track count.** First paragraph of `Goal` contains 3+ distinct verb phrases joined by `and` / `plus` / `also`.
   - **Knowledge mandate without reference.** `Constraints` or `Scope` mentions knowledge-backing AND `ls reference/ 2>/dev/null | wc -l` reports ≤2 entries (just `.gitignore` + `README.md`).

   If any signal trips, surface a one-line summary of each apparent track and offer three options:

   - **A. Split into N issues**, sequentially. Loop Step 1-2 once per track; each gets its own focused `Affected modules` and single-track `Goal`.
   - **B. File as one issue.** Prepend a `### Scope acknowledgment` section noting why the bundle is intentional, for post-mortem traceability.
   - **C. Trim to one track.** Loop back to Step 1 with the user's chosen single track.

   Default: surface — never silently file a flagged draft. After the user picks, continue to Step 4.

   Why this exists: PR #28 took 17 regenerations in part because issue #26 bundled four tracks AND mandated knowledge backing on an empty reference. The server-side linter (`tooling/check_issue_scope.py`) hard-rejects the same patterns, but catching at draft time is cheaper for the user (no failed run to clean up) and friendlier (interactive split vs. blunt rejection).

4. Show the rendered body to the user. Ask: "File this now via `gh issue create`, or print only?"

5. If they confirm filing, run:
   ```bash
   gh issue create --title "[agent] <title>" --body-file - <<'EOF'
   <rendered body>
   EOF
   ```
   Echo back the issue URL.

6. Remind: a maintainer must apply the `agent:run` label to start the workflow. Filing alone only attaches the inert `agent:task` label.

## Notes

- Keep the heading text verbatim — `agent-intake.yml` passes the issue body as `--scope` to Extractor and Architect, and they use the headings as structure.
- If the user omits a required field (Goal, Scope, Acceptance criteria), prompt for it before printing.
- Don't invent acceptance criteria. Push back if the user gives a vague goal — concrete criteria are what makes the run reviewable.
