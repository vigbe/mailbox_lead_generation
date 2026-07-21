# Task for gentle-ai-worker

## Context

You are working in the Odoo 19 Community Edition addon `correos_leads` (cwd is the module root). This module is currently a generic scaffold. Redesign it into a **mail-ingestion inbox / decantation pre-stage** for real-estate leads.

This is an Odoo 19 CE module. The project AGENTS.md and CLAUDE.md enforce strict Odoo 19 rules. **Load the odoo-19 skill FIRST** and follow it above any generic suggestion:
- Skill index: `.agents/skills/odoo-19/SKILL.md`
- Read the relevant guides before writing: mixins-guide (mail.thread, message_new), controller-guide, view-guide, security-guide, model-guide, manifest-guide, decorator-guide. They live under `.agents/skills/odoo-19/` (check `references/` and `dev/`).

## Approved architecture (decided with the user — do NOT change the concept)

`correos.leads` is a **decantation inbox** for incoming mail. Flow:
1. A native Odoo incoming mail server (`fetchmail.server`) is configured with its "Model" field = `correos.leads`. Each incoming email creates a `correos.leads` record via `mail.thread`'s `message_new()`.
2. The module classifies the email by **destination address** into `lead_type` = `consulta` (buyer/tenant inquiry) or `captacion` (owner offering a property).
3. A user reviews, and on `action_convert_to_lead()` the module creates a clean `crm.lead` (the real lead). This keeps spam out of the CRM.

So: `correos.leads` = pre-stage decanter; `crm.lead` = clean output lead.

## Hard requirements

### Dependencies (manifest `__manifest__.py`)
- `depends`: `['base', 'crm', 'real_estate_products']`  (add `crm` and `real_estate_products`)
- Keep version `19.0.1.0.0`, application True.

### Model `models/correos_leads.py` — `correos.leads`
Keep `_inherit = ['mail.thread', 'mail.activity.mixin']`, `_order = 'id desc'`.

Fields:
- `name` (Char, required) — descriptive, auto-computed from the email. Remove the current dependency on a non-existent `ir.sequence` 'correos.leads' sequence. Example: subject (or 'Sin asunto') + ' — ' + email_from local part. Must still be overridable.
- `active` (Boolean default True)
- `company_id` (Many2one res.company, required, default env.company)
- `email_from` (Char) — sender, parsed from the incoming message
- `email_to` (Char) — destination address(es) the message was sent to (used for classification)
- `subject` (Char)
- `body_html` (Html) — email body
- `date_received` (Datetime, default=now)
- `message_id` (Char) — RFC Message-ID, for dedup
- `partner_id` (Many2one res.partner) — contact derived from sender (best-effort lookup by email; may be empty)
- `lead_type` Selection `[('consulta','Consulta'), ('captacion','Captación'), ('sin_clasificar','Sin clasificar')]`, default `sin_clasificar`, tracking=True
- `state` Selection `[('nuevo','Nuevo'), ('revisado','Revisado'), ('convertido','Convertido'), ('rechazado_spam','Spam rechazado')]`, default `nuevo`, tracking=True
- `crm_lead_id` (Many2one `crm.lead`, string='Lead creado', readonly, copy=False) — the clean lead created on conversion
- `property_ids` (Many2many `product.real_estate`, string='Propiedades sugeridas') — empty in v1, filled by the matching hook later

Methods:
- `message_new(self, msg_dict, custom_values=None)` — `@api.model` override. Compute `name`, `subject`, `email_from`, `email_to`, `body_html`, `date_received`, `partner_id` from `msg_dict`; pass computed values into `custom_values` before calling super; after creation call `_assign_lead_type()` and write the parsed fields. Follow the Odoo 19 mixins-guide signature exactly. Make it dedup-safe on `message_id` when present (do not create a duplicate if `message_id` already exists).
- `_assign_lead_type(self, email_to)` — parse addresses from `email_to`; check `res.config.settings` config (see below); set `lead_type` to `consulta`/`captacion`/`sin_clasificar`. Make it resilient (never raise on parsing).
- `_compute_name_from_msg(self, msg_dict)` (helper) — build the descriptive name.
- `_analyze_and_match_properties(self)` — **HOOK STUB**. In v1 it MUST be present, documented with a clear docstring explaining it is the extension point for property matching against `product.real_estate`, but it does nothing in v1 (leaves `property_ids` empty). It must be safe to call (no-op).
- `action_review(self)` — `self.ensure_one()`, set `state='revisado'` (only from `nuevo`).
- `action_convert_to_lead(self)` — `self.ensure_one()`; raise UserError if already `convertido`; create a `crm.lead` with: name=subject or name, email_from, partner_id (lookup/create by email when possible), description=body (plain), and a tag/note indicating `lead_type`; set `crm_lead_id` and `state='convertido'`. Keep it defensive.
- `action_reject_spam(self)` — `self.ensure_one()`, set `state='rechazado_spam'`.
- `@api.ondelete(at_uninstall=False)` `_unlink_if_allowed` — forbid deleting `convertido` records (they own a crm.lead link). Allow delete from other states.
- `@api.model_create_multi create(self, vals_list)` — ensure `name` is set when missing (use a fallback, NOT the missing sequence).

### Settings (`res.config.settings`)
Add a settings view and model fields so the user configures the destination mailboxes used for classification:
- `correos_email_consultas` (Char) — comma-separated destination addresses that mean "consulta".
- `correos_email_captacion` (Char) — comma-separated destination addresses that mean "captación".
Expose them in a settings page under a "correos-leads" section. Store via the standard `res.config.settings` pattern (use config parameters `res.config.settings` + `default_`/`config_parameter` as appropriate per the odoo-19 guide). `_assign_lead_type` reads these.

### Views `views/correos_leads_views.xml`
- **list**: NOT editable (this is an inbox managed via buttons). Columns: name, email_from, subject, lead_type (badge: success=consulta, info=captacion, muted=sin_clasificar), state (badge), crm_lead_id, date_received. Use `<list>` (Odoo 19). Decorations via `decoration-*`.
- **form**: header buttons — "Revisar" (invisible unless state==nuevo), "Convertir en Lead" (invisible unless state in nuevo,revisado and not convertido), "Rechazar spam" (invisible unless state!=rechazado_spam). Statusbar `state`. Sheet groups: Origen (email_from, email_to, date_received, subject, message_id, partner_id), Contenido (body_html), Clasificación (lead_type editable, property_ids), Salida (crm_lead_id). Chatter (`oe_chatter` with message_follower_ids, activity_ids, message_ids).
- **search**: filters by lead_type and state; group by lead_type and state; search on name, subject, email_from.
- Keep the action + menu items, update help text.
- Add the settings view record.

### Security
- `security/ir.model.access.csv`: update so `group_correos_leads_user` = read,write,create (NO unlink); `group_correos_leads_manager` = full including unlink. Keep existing group names.
- Also add ACL for `res.config.settings` only if the odoo-19 guide requires it (usually not needed for settings; verify in the security guide).

### Tests `tests/test_correos_leads.py` (REPLACE the scaffold test_module.py)
Write behavior tests (Odoo `TransactionCase` or `SavepointCase`):
1. `test_message_new_creates_record` — call `message_new` with a fake `msg_dict` (email_from, to, subject, body, message_id); assert a `correos.leads` record is created with the parsed fields and `state='nuevo'`.
2. `test_assign_lead_type_by_destination` — configure `correos_email_consultas` to a test address, send a msg with that `to`; assert `lead_type='consulta'`. Same for captacion. And an unknown destination => `sin_clasificar`.
3. `test_message_new_dedup_by_message_id` — calling `message_new` twice with the same `message_id` does not create a duplicate.
4. `test_convert_to_lead_creates_crm_lead` — from a created record, call `action_convert_to_lead`; assert `crm_lead_id` is set, `state='convertido'`, and the `crm.lead` exists with the email.
5. `test_convert_twice_raises` — converting an already-converted record raises UserError.
6. `test_reject_spam` — `action_reject_spam` sets `state='rechazado_spam'`.
7. `test_unlink_blocked_when_converted` — deleting a `convertido` record raises; deleting a `nuevo` record works.

Update `tests/__init__.py` to import the new test module. Delete the old scaffold assertions.

## Odoo 19 rules (MANDATORY — verified against the skill)
- Use `<list>`, never `<tree>`.
- Direct attributes `invisible="..."`, `readonly="..."`, `required="..."` — NO `attrs`.
- `@api.ondelete(at_uninstall=False)` for delete validation.
- `@api.model_create_multi` for `create`.
- `from odoo.fields import Command` if you do relational ops.
- `self.ensure_one()` in action methods.
- `@api.model` on `message_new`.
- Follow the exact Odoo 19 `message_new` signature from the mixins-guide.

## Notes
- There may be NO running Odoo instance to execute tests here. Write correct, idiomatic tests anyway; do not invent test results. Verify your code with the available diagnostics (lsp/lens) and the odoo-19 skill. If you CAN run a real Odoo test command, do; otherwise report that tests are written but not executed and why.
- Keep changes single-threaded (you are the only writer).
- Do NOT commit, push, or create PRs.

## Memory
If you make important discoveries, decisions, or hit non-obvious Odoo 19 quirks (e.g., the exact `message_new` signature, fetchmail model-selection behavior, settings storage pattern), save them to Engram via the available memory save tool with project: 'correos_leads' before returning.

## Deliverable
Return a concise review-ready summary: files changed (with paths), the final model field list, the methods, how classification config works, and the test list. Flag anything you could not verify or any risk for the reviewer.

## Acceptance Contract
Acceptance level: reviewed
Completion is not accepted from prose alone. End with a structured acceptance report.

Criteria:
- criterion-1: Implement the requested change without widening scope
- criterion-2: Return evidence sufficient for an independent acceptance review

Required evidence: changed-files, tests-added, commands-run, validation-output, residual-risks, no-staged-files

Review gate: required by reviewer.

Finish with a fenced JSON block tagged `acceptance-report` in this shape:
Use empty arrays when no items apply; array fields contain strings unless object entries are shown.
```acceptance-report
{
  "criteriaSatisfied": [
    {
      "id": "criterion-1",
      "status": "satisfied",
      "evidence": "specific proof"
    }
  ],
  "changedFiles": [
    "src/file.ts"
  ],
  "testsAddedOrUpdated": [
    "test/file.test.ts"
  ],
  "commandsRun": [
    {
      "command": "command",
      "result": "passed",
      "summary": "short result"
    }
  ],
  "validationOutput": [
    "validation output or concise summary"
  ],
  "residualRisks": [
    "none"
  ],
  "noStagedFiles": true,
  "diffSummary": "short description of the diff",
  "reviewFindings": [
    "blocker: file.ts:12 - issue found, or no blockers"
  ],
  "manualNotes": "anything else the parent should know"
}
```