# Matching Design — Polymorphic Product Matching

> Status: APPROVED (product decisions confirmed). Phased implementation.
> Module: `mailbox_lead_generation` (Odoo 19 Community).
> Supersedes the in-flight SDD artifact design (single `dynamic_model` + `property_ids` coupling).

## Goal

When a mailbox lead receives an email, compare it against the **available
products** — native products from other modules (`product.template`) **or**
`product.real_estate` — so that:

- If the DB has `real_estate_products` installed, real-estate retrieval works.
- If the owner later adds service products (legal advice, advisory,
  ad-highlighting, etc.), they are matchable too.
- The module installs and runs **with or without** `real_estate_products`.

## Product decisions (confirmed)

1. **Semantics: Hybrid.** The AI first classifies the **intent**
   (`propiedad_compra`, `propiedad_arriendo`, `servicio_legal`,
   `servicio_asesoria`, `destacar_anuncio`, `otro`). Retrieval (attach specific
   records) runs **only for real-estate intents**. Services are identified by
   intent (optionally attach the matching `product.template`).
2. **Storage: Polymorphic suggestions.** A new child model
   `mailbox.lead.suggestion` holds matches via `res_model` + `res_id`
   (Reference-style), with `match_type`, `score`, `reason`, `state`.
3. **Dependency: Optional auto-detected.** `real_estate_products` removed from
   `depends`; real estate is offered as a matching source only when installed.

## Architecture

### Matching flow (hybrid)

```
Email → cron / action_retry_ai
   → AI classification: category + intent + extracted_data
   → route by intent:
       propiedad_*  AND product.real_estate installed
            → RETRIEVAL: filter candidates (operation, comuna, bedrooms, budget)
              → top-N → mailbox.lead.suggestion (score + reason)
       servicio_* / destacar_*
            → optional match against product.template (service catalog)
              → suggestion(s) or intent tag only
       otro / no source
            → no retrieval (intent still stored for human review)
```

### New model `mailbox.lead.suggestion`

```
lead_id      Many2one  → mailbox.lead.generation  (required, ondelete=cascade)
res_model    Char        (product.real_estate | product.template | ...)
res_id       Integer
record_ref   Reference   (computed display from res_model + res_id)
match_type   Selection   (propiedad | servicio | otro)
score        Float       0.0–1.0
reason       Text        (why it matched)
state        Selection   (suggested | accepted | rejected)  ← human review flow
```

- Own ACL (`ir.model.access.csv`) + minimal list/form view.
- Embedded (One2many from the lead) in the lead form.

### Source registry (extensibility, v2 = method-based)

The lead model exposes `_get_matching_sources()` returning the active sources:

- `real_estate` source — **only if `product.real_estate` in `self.env`**
  (lives in `real_estate_bridge.py`, conditionally loaded).
- `services` source — always available (matches against `product.template`),
  lives in the base model.

Each source implements a uniform `_match(self, lead, intent, extracted) ->
list[suggestion_values]`. v2 ships the two built-ins; a formal AbstractModel
registry can be extracted later without breaking the contract.

### `property_ids` — computed mirror (backward compat)

- The stored `Many2many("product.real_estate")` is **removed** from the base
  model (it required the comodel at registry build → incompatible with the
  optional dependency).
- `property_ids` is **re-added as a computed M2M mirror** of suggestions where
  `res_model = product.real_estate`, declared inside `real_estate_bridge.py`,
  which is loaded **only when `real_estate_products` is importable**.
- Net effect: existing views keep working when real estate is installed; the
  base module has zero hard reference to `product.real_estate`.

### Optional-dependency loading

`models/__init__.py`:

```python
from . import ai_provider
from . import mailbox_lead_generation
from . import mailbox_lead_suggestion
from . import res_config_settings
try:
    import odoo.addons.real_estate_products  # noqa: F401
    from . import real_estate_bridge
except ImportError:
    pass
```

Assumption (documented): in this workspace `real_estate_products` is always
installed on any DB that runs the real-estate stack, so the rare
"present-but-not-installed" edge does not occur in practice.

## Phases

### Phase B — Plumbing (NO AI, NO real retrieval)

Pure structural work, fully testable without the AI provider or network.

Scope IN:

- New `mailbox.lead.suggestion` model + ACL + minimal view + embed in lead form.
- `mailbox.lead.generation`: add `suggestion_ids` (One2many); add
  `_get_matching_sources()` scaffold; add `_run_matching()` no-op scaffold
  (returns empty, wired so Phase C fills it); clean `_selection_dynamic_models`
  fallback so it never hard-references a missing comodel.
- Remove stored `property_ids` M2M from the base model.
- `models/real_estate_bridge.py`: conditional computed `property_ids` mirror +
  real-estate source scaffold (empty `_match` for now).
- `__manifest__.py`: drop `real_estate_products` from `depends`; add the new
  security + view data files.
- TDD tests: suggestion CRUD, computed `property_ids` mirror, optional-dep
  behavior (guards), source registry returns expected sources.

Scope OUT (Phase C): AI `intent` in the contract, real retrieval engine, wiring
of `_analyze_and_match_properties`, `score`/`reason` population.

### Phase C — Intent + Retrieval (preview)

- Extend AI contract: add `intent` (+ optional `service_type`) to the system
  prompt and `_ai_validate_contract`.
- Real-estate retrieval: domain-filter candidates by operation / comuna /
  bedrooms / budget extracted by the AI; rank; top-N → suggestions.
- Wire `_analyze_and_match_properties` → call `_run_matching()` → fill
  suggestions.
- Tests with mocked IA + stubbed `product.real_estate` records.

### Future

- Service-catalog matching against `product.template`.
- Formal AbstractModel source registry for third-party sources.

## Non-goals

- No removal of existing committed v1 behavior (ingestion, classification,
  conversion, cron stub).
- No AI network calls in Phase B.
- No destructive migration (no data exists in `property_ids` today).
