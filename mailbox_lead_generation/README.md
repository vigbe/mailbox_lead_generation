# Mailbox Lead Generation

An email triage inbox that turns incoming mail into clean CRM leads. Every
message received through an incoming mail server (fetchmail) becomes a record
in a dedicated decantation inbox, gets classified (destination address +
optional AI), can be matched against your product catalog (`product.template`,
any product type), and is converted into a clean `crm.lead` in one click. Spam
never pollutes your pipeline.

> Available on the Odoo Apps Store for Odoo 16.0, 17.0, 18.0 and 19.0 — by
> [Victor Bastías Escobar](https://vicbas.com).

- **Inbox model:** `mailbox.lead.generation` (target it from fetchmail)
- **Classification:** destination address rules (inquiry / acquisition) plus
  optional AI category and intent
- **AI (optional):** any OpenAI-compatible endpoint — configurable base URL,
  model, API key, timeout and retries, with a scheduled batch-triage cron
- **Matching:** suggests products from your product catalog (`product.template`,
  any product type) for each email, with optional deep real-estate matching
  (`real_estate_products`) when that module is installed
- **Workflow:** new → reviewed → converted to `crm.lead` (or rejected as spam,
  or sent to pending), with full traceability back to the source email

> Odoo 16–19 Community & Enterprise · Python 3.10+ · depends on `base` +
> `crm` (+ pip `requests`)

## Install

```bash
# with the addons path configured
odoo -i mailbox_lead_generation -d <your_db>
# or update later
odoo -u mailbox_lead_generation -d <your_db>
```

Then configure under **Settings → Mailbox Lead Generation**: the destination
addresses for inquiry/acquisition classification, and (optionally) the AI
provider credentials.

## Usage

1. Configure an incoming mail server (fetchmail) targeting the model
   `mailbox.lead.generation`.
2. Incoming emails land in the triage inbox with their classification.
3. Review each record; convert real inquiries into CRM leads or reject spam.
4. Optionally enable AI triage for automatic category/intent detection and
   matching suggestions.

## Notes

- The user interface is currently available in Spanish; an English UI is on
  the roadmap.
- Product matching works with any `product.template` catalog; the deep
  real-estate matching activates only when `real_estate_products` is installed.

## License

- `LGPL-3`

## Author

- Victor Bastías Escobar
- Website: <https://vicbas.com>
- Support: <contacto@vicbas.com>
