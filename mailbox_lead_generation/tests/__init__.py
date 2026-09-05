# pyright: reportUnusedImport=false
# (Odoo: the import itself registers the module)
from . import (  # noqa: F401
    test_mailbox_lead_generation,
    test_mailbox_lead_suggestion,
    test_real_estate_matching,
    test_services_matching,
)
