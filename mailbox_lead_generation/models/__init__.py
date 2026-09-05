# pyright: reportMissingImports=false
# (odoo framework imports resolve only inside the Odoo runtime)
from . import ai_provider
from . import mailbox_lead_generation
from . import mailbox_lead_suggestion
from . import res_config_settings

try:
    import odoo.addons.real_estate_products  # noqa: F401
    from . import real_estate_bridge
except ImportError:
    pass
