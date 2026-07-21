import logging
from datetime import timezone
from email.utils import parsedate_to_datetime

from odoo import _, api, fields, models, tools
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class CorreosLeads(models.Model):
    _name = "correos.leads"
    _description = "Bandeja de decantacion de correos inmobiliarios"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    # ------------------------------------------------------------------
    # Fields
    # ------------------------------------------------------------------
    name = fields.Char(
        string="Asunto / Referencia",
        required=True,
        tracking=True,
        help="Descripcion corta auto-generada desde el correo (asunto + remitente).",
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        string="Empresa",
        required=True,
        default=lambda self: self.env.company,
    )
    email_from = fields.Char(string="Remitente", help="Direccion de origen del correo.")
    email_to = fields.Char(
        string="Destino",
        help="Direccion(es) de destino usada(s) para clasificar el correo.",
    )
    subject = fields.Char(string="Asunto")
    body_html = fields.Html(string="Cuerpo del correo", sanitize=False)
    date_received = fields.Datetime(string="Recibido", default=fields.Datetime.now)
    message_id = fields.Char(
        string="Message-ID",
        help="Identificador RFC822 del mensaje, usado para deduplicacion.",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Contacto",
        help="Contacto encontrado por direccion de correo (best-effort).",
    )

    lead_type = fields.Selection(
        [
            ("consulta", "Consulta"),
            ("captacion", "Captacion"),
            ("sin_clasificar", "Sin clasificar"),
        ],
        string="Tipo",
        default="sin_clasificar",
        tracking=True,
    )
    state = fields.Selection(
        [
            ("nuevo", "Nuevo"),
            ("revisado", "Revisado"),
            ("convertido", "Convertido"),
            ("rechazado_spam", "Spam rechazado"),
        ],
        string="Estado",
        default="nuevo",
        tracking=True,
    )

    crm_lead_id = fields.Many2one(
        "crm.lead",
        string="Lead creado",
        readonly=True,
        copy=False,
    )
    property_ids = fields.Many2many(
        "product.real_estate",
        "correos_leads_property_rel",
        "correos_leads_id",
        "property_id",
        string="Propiedades sugeridas",
    )

    # ------------------------------------------------------------------
    # mail.thread ingestion
    # ------------------------------------------------------------------
    @api.model
    def message_new(self, msg_dict, custom_values=None):
        """Create a correos.leads record from an incoming email.

        Called by fetchmail when the incoming mail server targets this model.
        Implements dedup-by-Message-ID, field extraction and lead-type
        classification based on the destination address.
        """
        # Dedup: do not create a duplicate if the message_id already exists.
        msg_id = msg_dict.get("message_id") or ""
        if msg_id:
            existing = self.search([("message_id", "=", msg_id)], limit=1)
            if existing:
                _logger.info("correos.leads: duplicate message_id %s ignored.", msg_id)
                return existing

        custom_values = dict(custom_values or {})
        email_from = msg_dict.get("email_from") or ""
        email_to = msg_dict.get("to") or ", ".join(msg_dict.get("recipients") or [])

        custom_values.setdefault("name", self._compute_name_from_msg(msg_dict))
        custom_values.setdefault("subject", msg_dict.get("subject") or "")
        custom_values.setdefault("email_from", email_from)
        custom_values.setdefault("email_to", email_to)
        custom_values.setdefault("body_html", msg_dict.get("body") or "")
        custom_values.setdefault("message_id", msg_id)
        date_received = self._parse_msg_date(msg_dict.get("date"))
        if date_received:
            custom_values.setdefault("date_received", date_received)
        partner = self._find_partner_from_email(email_from)
        if partner:
            custom_values.setdefault("partner_id", partner.id)

        record = super().message_new(msg_dict, custom_values)

        # Classify by destination address (resilient, never raises).
        lead_type = self._assign_lead_type(email_to)
        if lead_type:
            record.write({"lead_type": lead_type})
        return record

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _compute_name_from_msg(self, msg_dict):
        """Build a descriptive name from the email subject and sender."""
        subject = (msg_dict.get("subject") or "").strip() or _("Sin asunto")
        email_from = msg_dict.get("email_from") or msg_dict.get("from") or ""
        addresses = tools.email_split(email_from)
        email = addresses[0] if addresses else email_from.strip()
        local_part = email.split("@")[0] if email else _("desconocido")
        return _("%(subject)s — %(sender)s") % {
            "subject": subject,
            "sender": local_part,
        }

    def _parse_msg_date(self, date_str):
        """Parse an RFC822 date string into an Odoo Datetime string (UTC, naive).

        Returns False if the date cannot be parsed.
        """
        if not date_str:
            return False
        try:
            dt = parsedate_to_datetime(date_str)
        except (TypeError, ValueError, OverflowError):
            return False
        if not dt:
            return False
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return fields.Datetime.to_string(dt)

    def _find_partner_from_email(self, email_from):
        """Best-effort lookup of an existing partner by email address."""
        if not email_from:
            return self.env["res.partner"]
        normalized = tools.email_normalize(email_from)
        if not normalized:
            return self.env["res.partner"]
        return self.env["res.partner"].search(
            [("email_normalized", "=", normalized)], limit=1
        )

    @api.model
    def _assign_lead_type(self, email_to):
        """Classify the destination address(es) into a lead_type.

        Reads the configured mailbox lists from Settings and matches the
        destination addresses. Always returns a valid lead_type and never
        raises, so a parsing problem cannot break mail ingestion.
        """
        try:
            if not email_to:
                return "sin_clasificar"
            addresses = [a.lower() for a in tools.email_split(email_to)]
            if not addresses:
                return "sin_clasificar"
            ICP = self.env["ir.config_parameter"].sudo()
            consultas = [
                a.lower()
                for a in tools.email_split(
                    ICP.get_param("correos_leads.email_consultas") or ""
                )
            ]
            captacion = [
                a.lower()
                for a in tools.email_split(
                    ICP.get_param("correos_leads.email_captacion") or ""
                )
            ]
            for addr in addresses:
                if addr in consultas:
                    return "consulta"
                if addr in captacion:
                    return "captacion"
            return "sin_clasificar"
        except Exception:  # noqa: BLE001 - ingestion must stay resilient
            _logger.exception("correos.leads: failed to assign lead_type")
            return "sin_clasificar"

    def _analyze_and_match_properties(self):
        """Extension point for matching the email against product.real_estate.

        In v1 this is an intentional no-op: it leaves ``property_ids`` empty.
        Subsequent versions should override this method to suggest properties
        based on the email content (subject/body/destination).
        """
        self.ensure_one()
        return True

    def _get_or_create_partner(self):
        """Return an existing partner for this record's email, or create one."""
        self.ensure_one()
        partner = self.partner_id
        if partner:
            return partner
        partner = self._find_partner_from_email(self.email_from)
        if partner:
            return partner
        if self.email_from:
            normalized = tools.email_normalize(self.email_from)
            local = normalized.split("@")[0] if normalized else self.email_from.strip()
            partner = self.env["res.partner"].create(
                {
                    "name": local or self.email_from,
                    "email": self.email_from,
                }
            )
        return partner

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_review(self):
        """Mark the email as reviewed (only from 'nuevo')."""
        self.ensure_one()
        if self.state == "nuevo":
            self.state = "revisado"
        return True

    def action_convert_to_lead(self):
        """Create a clean crm.lead from this email and mark it converted."""
        self.ensure_one()
        if self.state == "convertido":
            raise UserError(_("Este correo ya fue convertido a un lead."))
        partner = self._get_or_create_partner()
        lead_type_label = dict(self._fields["lead_type"].selection).get(
            self.lead_type, self.lead_type
        )
        description_parts = []
        if self.lead_type != "sin_clasificar":
            description_parts.append(_("Tipo de correo: %s") % lead_type_label)
        if self.body_html:
            description_parts.append(self.body_html)
        lead = self.env["crm.lead"].create(
            {
                "name": self.subject or self.name,
                "partner_id": partner.id if partner else False,
                "email_from": self.email_from or "",
                "description": "\n".join(description_parts)
                if description_parts
                else False,
            }
        )
        self.write(
            {
                "crm_lead_id": lead.id,
                "state": "convertido",
            }
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": "crm.lead",
            "res_id": lead.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_reject_spam(self):
        """Mark the email as rejected spam."""
        self.ensure_one()
        self.state = "rechazado_spam"
        return True

    def action_open_crm_lead(self):
        """Open the related crm.lead created from this email."""
        self.ensure_one()
        if not self.crm_lead_id:
            return True
        return {
            "type": "ir.actions.act_window",
            "res_model": "crm.lead",
            "res_id": self.crm_lead_id.id,
            "view_mode": "form",
            "target": "current",
        }

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @api.ondelete(at_uninstall=False)
    def _unlink_if_allowed(self):
        if any(rec.state == "convertido" for rec in self):
            raise UserError(_("No se puede eliminar un correo ya convertido a lead."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name"):
                vals["name"] = _("Correo sin asunto")
        return super().create(vals_list)
