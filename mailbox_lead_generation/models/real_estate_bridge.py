# pyright: reportMissingImports=false
# (odoo framework imports resolve only inside the Odoo runtime)
from odoo import api, models


class MailboxLeadGenerationRealEstateBridge(models.Model):
    """Conditional real-estate extension of ``mailbox.lead.generation``.

    Loaded only when ``real_estate_products`` is importable (see
    ``models/__init__.py``). This keeps the base module comodel-free. The
    real-estate retrieval source (``_match_real_estate``) lives here so matching
    logic never leaks into the base model.

    NOTE: a relational ``property_ids`` mirror of the suggestions was removed on
    purpose. A ``Many2many`` to an optional (non-dependency) comodel cannot be
    resolved during incremental registry setup (``-u``): Odoo asserts the comodel
    is in the pool while only the updated module's models are set up, so
    ``product.real_estate`` is unknown and the registry fails to load. The
    polymorphic ``mailbox.lead.suggestion`` rows
    (``res_model == 'product.real_estate'``) are the single source of truth; use
    them directly (e.g. via ``lead.suggestion_ids``).
    """

    _inherit = "mailbox.lead.generation"

    # Max candidates returned by the real-estate retrieval source.
    _RE_TOP_N = 5

    # ------------------------------------------------------------------
    # Real-estate retrieval source (Phase C)
    # ------------------------------------------------------------------
    @api.model
    def _re_map_tipo_propiedad(self, raw):
        """Map a free-text property category to a ``product.real_estate`` tipo.

        Returns the canonical selection key (e.g. ``departamento``) or ``False``
        when no confident mapping exists. Callers skip the tipo filter when
        ``False`` is returned, so a loose mapping never over-constrains.
        """
        if not raw:
            return False
        text = str(raw).strip().lower()
        synonyms = {
            "departamento": ("departamento", "depto", "apartment", "flat"),
            "casa": ("casa", "house", "chalet", "vivienda"),
            "oficina": ("oficina", "office"),
            "local_comercial": ("local", "comercial", "shop", "tienda"),
            "terreno": ("terreno", "sitio", "parcela", "lote", "land"),
            "campo": ("campo", "fundo", "predio", "rural"),
            "bodega": ("bodega", "warehouse", "galpon"),
            "parking": ("parking", "estacionamiento", "cochera"),
            "desarrollo": ("desarrollo", "proyecto", "development"),
        }
        for key, aliases in synonyms.items():
            if any(alias in text for alias in aliases):
                return key
        return False

    @api.model
    def _re_extract_bedrooms(self, extracted):
        """Best-effort bedroom count from the AI payload (several key aliases)."""
        for key in ("bedrooms", "rooms", "habitaciones", "dormitorios", "dorm"):
            value = (extracted or {}).get(key)
            if value in (None, ""):
                continue
            try:
                count = int(float(value))
                return count if count > 0 else None
            except (TypeError, ValueError):
                continue
        return None

    @api.model
    def _re_extract_budget(self, extracted):
        """Best-effort numeric budget from the AI payload."""
        value = (extracted or {}).get("budget")
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _match_real_estate(self, intent, extracted):
        """Retrieve and rank ``product.real_estate`` candidates for this lead.

        Maps the AI intent to a listing operation (sale/rent), filters live
        candidates by the strong signals (operation, comuna, tipo) and ranks
        them by the weaker ones (bedrooms, budget). Returns a list of
        suggestion value dicts for ``_run_matching`` to materialize.

        Robust to a missing comodel or unknown price fields: it degrades to
        ``[]`` / skips the relevant signal instead of raising.
        """
        self.ensure_one()
        re_model = self.env.get("product.real_estate")
        if re_model is None:
            return []

        extracted = extracted or {}
        # Buyer intent maps to the listing side: wants to buy -> sale listings.
        operacion = "venta" if intent == "property_sale" else "arriendo"
        domain = [
            ("active", "=", True),
            ("state", "in", ["available", "reserved"]),
            ("operacion", "=", operacion),
        ]

        location = str(extracted.get("location") or "").strip()
        if location:
            domain.append(("comuna", "ilike", location))

        tipo = self._re_map_tipo_propiedad(extracted.get("property_category"))
        if tipo:
            domain.append(("tipo_propiedad", "=", tipo))

        candidates = re_model.search(domain)
        if not candidates:
            return []

        wanted_rooms = self._re_extract_bedrooms(extracted)
        budget = self._re_extract_budget(extracted)
        price_field = (
            "valor_propiedad_clp"
            if operacion == "venta"
            else "precio_arriendo_clp_proyectado"
        )
        has_price_field = price_field in re_model._fields

        scored = []
        for prop in candidates:
            score = 0.5  # base: passed the hard filters
            reasons = [operacion]

            if wanted_rooms:
                rooms = prop.habitaciones or 0
                if wanted_rooms - 1 <= rooms <= wanted_rooms + 1:
                    score += 0.2
                    reasons.append(f"{rooms} dorm.")
            if budget and budget > 0 and has_price_field:
                price = getattr(prop, price_field, 0.0) or 0.0
                if 0 < price <= budget:
                    score += 0.2
                    reasons.append("dentro de presupuesto")
            if location and prop.comuna and location.lower() in prop.comuna.lower():
                score += 0.1
                reasons.append(prop.comuna)

            scored.append(
                {
                    "res_model": "product.real_estate",
                    "res_id": prop.id,
                    "match_type": "propiedad",
                    "score": min(1.0, round(score, 2)),
                    "reason": " · ".join(reasons),
                }
            )

        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[: self._RE_TOP_N]
