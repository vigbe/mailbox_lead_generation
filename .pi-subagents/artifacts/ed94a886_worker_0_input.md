# Task for worker

## Role
You are the single implementation writer for the Odoo 19 CE addon `correos_leads` (cwd is the module root). Verify FIRST that you have write/edit/bash tools; if they are missing, stop immediately and report `status: blocked` with the exact missing tools.

## Load the odoo-19 skill FIRST
- Index: `.agents/skills/odoo-19/SKILL.md`
- Read the relevant guides under `.agents/skills/odoo-19/` (`references/` and `dev/`): mixins-guide (mail.thread, `message_new`), controller-guide, view-guide, security-guide, model-guide, manifest-guide, decorator-guide. Follow them above any generic suggestion.

## Context
This module is currently a generic scaffold. Redesign it into a **mail-ingestion inbox / decantation pre-stage** for real-estate leads. The user already approved this architecture (do NOT change the concept).

### Approved architecture
`correos.leads` = decantation inbox for incoming mail. Flow:
1. A native Odoo incoming mail server (`fetchmail.server`) is configured with its "Model" field = `correos.leads`. Each incoming email creates a `correos.leads` record via `mail.thread`'s `message_new()`.
2. The module classifies the email by **destination address** into `lead_type` = `consulta` (buyer/tenant inquiry) or `captacion` (owner offering a property).
3. On `action_convert_to_lead()` the module creates a clean `crm.lead`. This keeps spam out of the CRM.

### Confirmed facts from the workspace (already verified — trust these)
- The property model is `product.real_estate` (lives in the `real_estate_products` addon at `../real_estate_products/models/product_real_estate.py`; it inherits `mail.thread` and `mail.activity.mixin`).
- `real_estate_products/__manifest__.py` depends on `['base','product','stock','web','mail','crm','project','calendar']` — so `crm` is available.
- There is a `crm_lead_extend` model in `real_estate_products` that extends `crm.lead` (do not break it).

## Hard requirements

### Manifest `__manifest__.py`
- `depends`: `['base', 'crm', 'real_estate_products']`
- Keep `version: '19.0.1.0.0'`, `application: True`, `installable: True`.
- Add the new data files (settings view, etc.) to `data`.

### Model `models/correos_leads.py` — `correos.leads`
Keep `_inherit = ['mail.thread', 'mail.activity.mixin']`, `_order = 'id desc'`.

Fields:
- `name` (Char, required) — descriptive, auto-computed from the email. **Remove** the current dependency on a non-existent `ir.sequence` 'correos.leads'. Build name from subject (or 'Sin asunto') + ' — ' + sender local part. Still overridable.
- `active` (Boolean default True)
- `company_id` (Many2one res.company, required, default env.company)
- `email_from` (Char) — sender
- `email_to` (Char) — destination address(es) used for classification
- `subject` (Char)
- `body_html` (Html) — email body
- `date_received` (Datetime, default=fields.Datetime.now)
- `message_id` (Char) — RFC Message-ID for dedup
- `partner_id` (Many2one res.partner) — best-effort lookup by email
- `lead_type` Selection `[('consulta','Consulta'), ('captacion','Captación'), ('sin_clasificar','Sin clasificar')]`, default `sin_clasificar`, tracking=True
- `state` Selection `[('nuevo','Nuevo'), ('revisado','Revisado'), ('convertido','Convertido'), ('rechazado_spam','Spam rechazado')]`, default `nuevo`, tracking=True
- `crm_lead_id` (Many2one `crm.lead`, string='Lead creado', readonly, copy=False)
- `property_ids` (Many2many `product.real_estate`, string='Propiedades sugeridas') — empty in v1

Methods:
- `message_new(self, msg_dict, custom_values=None)` — `@api.model` override following the exact Odoo 19 signature from the mixins-guide. Compute `name`, `subject`, `email_from`, `email_to`, `body_html`, `date_received`, `partner_id`, `message_id` from `msg_dict`; pass them via `custom_values` to super; after creation call `_assign_lead_type()` and write remaining fields. Dedup-safe on `message_id` when present (do not create a duplicate if that message_id already exists).
- `_assign_lead_type(self, email_to)` — parse addresses; read settings config (see below); set `lead_type`. Never raise on parsing (resilient).
- `_compute_name_from_msg(self, msg_dict)` (helper) — build the descriptive name.
- `_analyze_and_match_properties(self)` — **HOOK STUB**. Present with a clear docstring stating it is the extension point for matching against `product.real_estate`, but in v1 it is a safe no-op (leaves `property_ids` empty).
- `action_review(self)` — `self.ensure_one()`, set `state='revisado'` (only from `nuevo`).
- `action_convert_to_lead(self)` — `self.ensure_one()`; raise UserError if already `convertido`; create a `crm.lead` with name=subject/name, email_from, partner_id (lookup/create by email when possible), description=body, a tag/note for `lead_type`; set `crm_lead_id` and `state='convertido'`. Defensive.
- `action_reject_spam(self)` — `self.ensure_one()`, set `state='rechazado_spam'`.
- `@api.ondelete(at_uninstall=False)` `_unlink_if_allowed` — forbid deleting `convertido` records; allow others.
- `@api.model_create_multi create(self, vals_list)` — ensure `name` is set when missing (fallback, not the missing sequence).

### Settings (`models/res_config_settings.py` + a settings view)
Add classification config so the user maps destination mailboxes:
- `correos_email_consultas` (Char) — comma-separated destination addresses meaning "consulta".
- `correos_email_captacion` (Char) — comma-separated destination addresses meaning "captación".
Use the standard `res.config.settings` pattern (read/write via config parameters; follow the odoo-19 guide for the exact storage pattern). Expose them under a "correos-leads" section in Settings. `_assign_lead_type` reads these. Add the settings view XML to `data` and a menu hook if needed.

### Views `views/correos_leads_views.xml`
- **list** (NOT editable — inbox managed via buttons): name, email_from, subject, lead_type (badge: success=consulta, info=captacion, muted=sin_clasificar), state (badge), crm_lead_id, date_received. Use `<list>` (Odoo 19), `decoration-*`.
- **form**: header buttons — "Revisar" (invisible unless state==nuevo), "Convertir en Lead" (invisible unless state in nuevo,revisado and state!=convertido), "Rechazar spam" (invisible unless state!=rechazado_spam). Statusbar `state`. Sheet groups: Origen (email_from, email_to, date_received, subject, message_id, partner_id), Contenido (body_html), Clasificación (lead_type editable, property_ids), Salida (crm_lead_id). Chatter (`oe_chatter`).
- **search**: filters by lead_type and state; group by lead_type and state; search on name, subject, email_from.
- Keep the action + menu items, update help text.

### Security `security/ir.model.access.csv`
- `group_correos_leads_user` = read,write,create (NO unlink)
- `group_correos_leads_manager` = full incl. unlink
- Keep the existing group names from `security/security_groups.xml` (do not change groups, only ACL).

### Tests `tests/test_correos_leads.py` (REPLACE scaffold `test_module.py`)
Odoo `TransactionCase`. Cover:
1. `test_message_new_creates_record` — msg_dict → record created with parsed fields, `state='nuevo'`.
2. `test_assign_lead_type_by_destination` — configured consultas address in `to` → `lead_type='consulta'`; same for captacion; unknown → `sin_clasificar`.
3. `test_message_new_dedup_by_message_id` — same message_id twice → no duplicate.
4. `test_convert_to_lead_creates_crm_lead` — `action_convert_to_lead` → `crm_lead_id` set, `state='convertido'`, crm.lead exists with email.
5. `test_convert_twice_raises` — converting already-converted → UserError.
6. `test_reject_spam` — `action_reject_spam` → `state='rechazado_spam'`.
7. `test_unlink_blocked_when_converted` — delete convertido raises; delete nuevo works.
Update `tests/__init__.py` to import the new test module; remove the old scaffold tests.

## Odoo 19 rules (MANDATORY)
- `<list>` never `<tree>`. Direct `invisible/readonly/required` — NO `attrs`. `@api.ondelete(at_uninstall=False)`. `@api.model_create_multi` for create. `self.ensure_one()` in actions. `@api.model` on `message_new`. `from odoo.fields import Command` if relational ops. `store=True` only if needed (not required here).

## Execution notes
- There may be NO running Odoo to execute tests here. Write correct idiomatic tests anyway; do NOT invent test results. If you CAN run a real Odoo test command, do; otherwise report tests written-but-not-executed and why.
- Verify your code with available diagnostics (lsp/lens). 
- You are the ONLY writer (single-threaded). Do NOT commit, push, or create PRs.

## Memory
If you hit non-obvious Odoo 19 quirks (exact `message_new` signature, fetchmail model-selection behavior, settings storage pattern), save them via the available memory save tool with project: 'correos_leads' before returning.

## Return
Return a concise review-ready summary: files changed (paths), final field list, methods, how classification config works, test list, and any unverifiable risk. Follow the schema: status, summary, files_changed, validation, risks, review_focus.

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