# Odoo __manifest__.py is a bare dict literal (read via ast.literal_eval);
# the "unused expression" warning is an unavoidable false positive.
# pyright: reportUnusedExpression=false
{
    "name": "Mailbox Lead Generation",
    "version": "19.0.1.2.0",
    "category": "Sales/CRM",
    "summary": "Email triage inbox that turns incoming mail into clean CRM leads",
    "description": """
                Mailbox Lead Generation
                ========================

                Published for Odoo 16.0, 17.0, 18.0 and 19.0 (Community and
                Enterprise).

                A decantation inbox (pre-stage) for incoming email. Every message
                received through an incoming mail server (fetchmail targeting the
                mailbox.lead.generation model) becomes a record that is classified
                by destination address (inquiry or acquisition), optionally triaged
                by an AI provider (any OpenAI-compatible endpoint), matched against
                your property or service catalog, and then converted into a clean
                crm.lead. Spam is rejected before it ever reaches your pipeline.
            """,
    "author": "Victor Bastías Escobar",
    "website": "https://vicbas.com",
    "support": "contacto@vicbas.com",
    "maintainer": "Victor Bastías Escobar",
    "license": "LGPL-3",
    "depends": [
        "base",
        "crm",
    ],
    "data": [
        "security/security_groups.xml",
        "security/ir.model.access.csv",
        "views/mailbox_lead_generation_views.xml",
        "views/mailbox_lead_suggestion_views.xml",
        "data/res_config_settings_views.xml",
        "data/ir_cron.xml",
    ],
    "demo": [],
    "assets": {},
        "installable": True,
        "application": True,
        "auto_install": False,
        "images": [
            "static/description/thumbnail.png",
        ],
    "external_dependencies": {
        "python": [
            "requests",
        ],
        "bin": [],
    },
}
