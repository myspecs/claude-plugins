---
name: start-session
description: Start a new MySpec spec session in the MySpec webapp on the user's behalf — MySpec's own AI then generates or edits the spec bundle with the user — with an opening prompt composed from this repository and conversation, and hand the user the session link. Use when the user says "have MySpec write the spec", "start a MySpec session", "generate a spec on MySpec for this", "open a MySpec chat for this change", "spec this feature in MySpec", "let MySpec edit the requirements", or wants a greenfield, brownfield, enterprise, Spec Kit, or OpenSpec bundle produced by MySpec rather than written locally. Requires the myspec MCP server (see the setup skill).
user-invocable: false
---

# Start a MySpec spec session

Tools are called as `mcp__plugin_myspec-mcp_myspec__<tool>` (signatures in the `implement` skill's `references/mcp-tools.md` § Spec sessions). `start_spec_session` creates ONE real chat session in the MySpec webapp, runs its first turn, and returns a link where the user continues; MySpec's AI does the interview and writes the bundle. It bills model tokens to the signed-in account. When the user wants Claude to write the documents in this conversation instead, use the `spec-authoring` skill.

## 1. Decide the session

1. Project: the `<!-- myspec-mcp:start -->` block in `CLAUDE.md`, else `list_projects` (ask when several match; offer `create_project` when none).
2. Mode and workflow, from the user's intent and the repository:

| Intent | `mode` | `workflow_id` |
|---|---|---|
| New product or service | `generate` | `myspec-greenfield-v1` (default); `enterprise-greenfield-v1` adds a quality plan and verification per task; `speckit-greenfield-v1` writes Spec Kit documents |
| Change to an existing codebase | `generate` | `myspec-brownfield-v1` (proposal and requirements delta), or `openspec-brownfield-v1` for OpenSpec tooling |
| Change documents of an existing bundle | `edit` | `myspec-edit-v1` (default), `myspec-edit-brownfield-v1` for a brownfield bundle |

   Ask with `AskUserQuestion` when the choice is not obvious, recommending one. A workflow that contradicts `mode` is rejected.
3. Inputs to cite: for `edit`, the `spec_file_ids` of the documents to change (`list_spec_file`); attachments the session should read (`list_attachments`, `attachment_ids`); at most 25 each. Language (`en` default, `zh`, `ja`, `vi`) only when the user wants another; it cannot change later.
4. Brownfield: the session must read the local code. Start the reverse bridge first (the `reverse-bridge` skill), confirm its `connected` line, and keep it running after this call: the session reads the code while the user works in the webapp.

## 2. Compose the opening prompt

Write it as the user would, in their voice, with what MySpec cannot see and the user would otherwise retype:

- the goal and the users it serves, in the user's words;
- for brownfield: the repository and the area it changes (modules, entry points, files you read), current behaviour, constraints (stack, conventions, what must not change);
- decisions already made and open questions, labelled as such;
- for edit: what to change in which document and why.

Keep facts you verified separate from guesses; never invent requirements. Show the prompt, the workflow and the cited files to the user and get a yes before the call: it starts a billed session.

## 3. Start it, once

1. `start_spec_session` with `project_id`, `mode`, `prompt`, and the optional fields chosen above, plus a short `session_title`.
2. On a timeout or transport error, do not call again: `list_spec_sessions` (newest first) to find the session it may already have created, and use that one.
3. Relay to the user: the `session_url`, a one-line summary of `assistant_text`, and what the session waits for (`pending_action`: answer a form, decide on a file, give review feedback, choose an option; `turn_still_running` means the first turn is still working). `first_turn_error` or `warnings` (for example no bridge connected) do not mean the session is missing: relay the link with them.
4. Stop there. Do not answer the session's questions or drive its workflow through other tools; the user continues in the webapp.

## 4. Afterwards

When the user says the session is done, `get_spec_session` shows its status (`completed`), and `list_spec_file` shows the bundle it wrote. Implementation goes through the `implement` skill; a review through the `analyze` skill. Stop the reverse bridge when no session needs it.
