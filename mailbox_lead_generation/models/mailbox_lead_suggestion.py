# pyright: reportMissingImports=false
# (odoo framework imports resolve only inside the Odoo runtime)
from odoo import _, api, fields, models


class MailboxLeadSuggestion(models.Model):
    """Polymorphic suggested match for a mailbox lead.

    Each row points at any target record via ``res_model`` + ``res_id`` (a
    Reference-style link resolved into the computed ``record_ref``), classified
    by ``match_type`` and carrying a human-reviewable ``score``/``reason``/
    ``state``. The model is intentionally comodel-free: the only hard relation
    is ``lead_id`` → ``mailbox.lead.generation``.
    """

    _name = "mailbox.lead.suggestion"
    _description = "Mailbox Lead Suggested Match"
    _order = "score desc"

    lead_id = fields.Many2one(
        "mailbox.lead.generation",
        string="Correo / Lead",
        required=True,
        ondelete="cascade",
        index=True,
    )
    res_model = fields.Char(
        string="Modelo referenciado",
        required=True,
        help="Modelo Odoo del registro sugerido, p.ej. 'product.real_estate', "
        "'product.template'.",
    )
    res_id = fields.Integer(string="ID registro", required=True)
    match_type = fields.Selection(
        [("propiedad", "Propiedad"), ("servicio", "Servicio"), ("otro", "Otro")],
        string="Tipo de coincidencia",
        required=True,
        default="otro",
    )
    score = fields.Float(
        string="Puntaje",
        digits=(3, 2),
        default=0.0,
        help="Confianza de la coincidencia (0.00–1.00).",
    )
    reason = fields.Text(string="Motivo")
    state = fields.Selection(
        [
            ("suggested", "Sugerido"),
            ("accepted", "Aceptado"),
            ("rejected", "Rechazado"),
        ],
        string="Estado",
        default="suggested",
        tracking=True,
    )
    record_ref = fields.Reference(
        selection="_selection_available_target_models",
        string="Registro",
        compute="_compute_record_ref",
        store=False,
    )

    # ------------------------------------------------------------------
    # Dynamic Reference target whitelist
    # ------------------------------------------------------------------
    @api.model
    def _selection_available_target_models(self):
        """Whitelist of models selectable for the ``record_ref`` Reference.

        Built at runtime so the field never breaks when ``real_estate_products``
        is not installed: ``product.template`` is offered when present and
        ``product.real_estate`` only when available. De-duplicated; never
        hard-fails if a model is missing.
        """
        choices = []
        candidates = ["product.template"]
        if "product.real_estate" in self.env:
            candidates.append("product.real_estate")
        for model in candidates:
            if model in self.env and model not in {key for key, _ in choices}:
                desc = self.env[model]._description or model
                choices.append((model, desc))
        return choices or [("", "—")]

    @api.depends("res_model", "res_id")
    def _compute_record_ref(self):
        """Resolve ``record_ref`` (Reference) from ``res_model`` + ``res_id``.

        Everything is guarded: an unknown model or falsy id yields ``False``.
        """
        for rec in self:
            value = False
            if rec.res_model and rec.res_model in self.env and rec.res_id:
                value = f"{rec.res_model},{rec.res_id}"
            rec.record_ref = value

    def _compute_display_name(self):
        """Human-readable name for list/search; falls back to model/id."""
        for rec in self:
            name = ""
            try:
                if rec.record_ref:
                    name = rec.record_ref.display_name or ""
            except Exception:  # noqa: BLE001 - display_name must never raise
                name = ""
            if not name:
                name = _("Sugerencia %s/%s") % (rec.res_model or "?", rec.res_id or 0)
            rec.display_name = name

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @api.ondelete(at_uninstall=False)
    def _unlink_if_allowed(self):
        """Phase B: deletions are always allowed.

        Review-flow guards (e.g. blocking delete of an accepted suggestion)
        arrive in Phase C.
        """
        return True
