"""Pre-migration for 19.0.1.3.0: remap legacy AI intent values.

Renames the stored ``ai_intent`` selection keys from the real-estate
vocabulary to the product-agnostic one: ``property_sale`` -> ``purchase``
and ``property_rent`` -> ``rent``. No other stored data is touched: the
``ai_extracted`` payloads keep their legacy ``property_category`` key and
the readers treat it as a fallback.
"""


def migrate(cr, version):
    """Remap legacy ``ai_intent`` values on ``mailbox_lead_generation``."""
    cr.execute(
        """
        UPDATE mailbox_lead_generation
        SET ai_intent = 'purchase'
        WHERE ai_intent = 'property_sale'
        """
    )
    cr.execute(
        """
        UPDATE mailbox_lead_generation
        SET ai_intent = 'rent'
        WHERE ai_intent = 'property_rent'
        """
    )
