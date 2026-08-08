{
    "name": "Mail Box Lead Generation",
    "version": "19.0.1.0.0",
    "category": "Tools",
    "summary": "Bandeja de decantación de correos inmobiliarios",
    "description": """
            Mail Box Lead Generation
            ========================
            Bandeja de decantación (inbox / pre-stage) para correos inmobiliarios.

            Cada correo entrante (vía fetchmail.server con modelo mailbox.lead.generation)
            crea un registro que se clasifica por dirección de destino en consulta
            o captación, y luego puede convertirse en un crm.lead limpio.
        """,
    "author": "ia-prop.com",
    "website": "https://ia-prop.com",
    "license": "LGPL-3",
    "depends": [
        "base",
        "crm",
        "real_estate_products",
    ],
    "data": [
        "security/security_groups.xml",
        "security/ir.model.access.csv",
        "views/mailbox_lead_generation_views.xml",
        "data/res_config_settings_views.xml",
        "data/ir_cron.xml",
    ],
    "demo": [],
    "assets": {},
    "installable": True,
    "application": True,
    "auto_install": False,
    "external_dependencies": {
        "python": [
            "requests",
        ],
        "bin": [],
    },
}
