import logging

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class CorreosLeads(models.Model):
    _name = 'correos.leads'
    _description = 'correos-leads'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'
    _check_company_auto = True

    name = fields.Char(
        string='Nombre',
        required=True,
        tracking=True,
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company',
        string='Empresa',
        required=True,
        default=lambda self: self.env.company,
    )
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmado'),
        ('done', 'Realizado'),
    ], default='draft', tracking=True)

    @api.ondelete(at_uninstall=False)
    def _unlink_if_not_draft(self):
        if any(rec.state != 'draft' for rec in self):
            raise UserError(_('Solo se pueden eliminar registros en borrador'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name'):
                vals['name'] = self.env['ir.sequence'].next_by_code('correos.leads') or _('Nuevo')
        return super().create(vals_list)

    def action_confirm(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Solo se pueden confirmar borradores'))
        self.state = 'confirmed'

    def action_done(self):
        self.ensure_one()
        if self.state != 'confirmed':
            raise UserError(_('Solo se puede completar desde confirmado'))
        self.state = 'done'

    def action_draft(self):
        self.ensure_one()
        self.state = 'draft'
