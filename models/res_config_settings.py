from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    correos_email_consultas = fields.Char(
        string="Emails de Consulta",
        config_parameter="correos_leads.email_consultas",
        help="Direcciones de destino (separadas por comas) que se clasifican "
        'como "consulta" (inquilino/comprador interesado).',
    )
    correos_email_captacion = fields.Char(
        string="Emails de Captación",
        config_parameter="correos_leads.email_captacion",
        help="Direcciones de destino (separadas por comas) que se clasifican "
        'como "captación" (propietario ofreciendo una propiedad).',
    )
