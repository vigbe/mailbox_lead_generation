# pyright: reportMissingImports=false, reportUnusedImport=false
# (odoo framework imports resolve only inside the Odoo runtime)
from . import (  # noqa: F401
    ai_provider,
    mailbox_lead_generation,
    mailbox_lead_suggestion,
    res_config_settings,
)
