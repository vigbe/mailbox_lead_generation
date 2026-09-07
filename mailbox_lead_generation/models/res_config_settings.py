# pyright: reportMissingImports=false
# (odoo framework imports resolve only inside the Odoo runtime)
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # ------------------------------------------------------------------
    # Clasificación de correos (legacy)
    # ------------------------------------------------------------------
    mailbox_email_consultas = fields.Char(
        string="Emails de Consulta",
        config_parameter="mailbox_lead_generation.email_consultas",
        help="Direcciones de destino (separadas por comas) que se clasifican "
        'como "consulta" (inquilino/comprador interesado).',
    )
    mailbox_email_captacion = fields.Char(
        string="Emails de Captación",
        config_parameter="mailbox_lead_generation.email_captacion",
        help="Direcciones de destino (separadas por comas) que se clasifican "
        'como "captación" (propietario ofreciendo una propiedad).',
    )

    # ------------------------------------------------------------------
    # Decantación IA (PR-1) — parámetros vía ir.config_parameter
    # Clave ICP real con prefijo ``mailbox_lead_generation.`` (coherente con los
    # parámetros de clasificación legacy y con el consumidor del pipeline IA).
    # ------------------------------------------------------------------
    mailbox_ai_provider = fields.Char(
        string="Proveedor IA",
        config_parameter="mailbox_lead_generation.ai_provider",
        default="openai",
        help="Identificador del proveedor OpenAI-compatible a usar.",
    )
    mailbox_ai_api_key = fields.Char(
        string="API key IA",
        config_parameter="mailbox_lead_generation.ai_api_key",
        help="Clave de API del proveedor. Si está vacía, la IA queda "
        "deshabilitada y los registros pasan a estado «error».",
    )
    mailbox_ai_model = fields.Char(
        string="Modelo IA",
        config_parameter="mailbox_lead_generation.ai_model",
        default="gpt-4o-mini",
        help="Nombre del modelo a invocar (ej. gpt-4o-mini).",
    )
    mailbox_ai_base_url = fields.Char(
        string="Base URL IA",
        config_parameter="mailbox_lead_generation.ai_base_url",
        help="URL base del endpoint OpenAI-compatible. "
        "Vacío = endpoint por defecto del proveedor.",
    )
    mailbox_ai_max_tokens = fields.Integer(
        string="Máx. tokens",
        config_parameter="mailbox_lead_generation.ai_max_tokens",
        default=1000,
        help="Cantidad máxima de tokens de la respuesta IA.",
    )
    mailbox_ai_timeout = fields.Integer(
        string="Timeout (s)",
        config_parameter="mailbox_lead_generation.ai_timeout",
        default=30,
        help="Timeout en segundos para cada llamada HTTP a la IA.",
    )
    mailbox_ai_retries = fields.Integer(
        string="Reintentos",
        config_parameter="mailbox_lead_generation.ai_retries",
        default=2,
        help="Número de reintentos ante fallos de red/parseo por registro.",
    )
    mailbox_dynamic_model = fields.Char(
        string="Modelo dinámico",
        config_parameter="mailbox_lead_generation.dynamic_model",
        default="product.real_estate",
        help="Modelo Odoo contra el que se resuelve el matching de la IA "
        "(default: product.real_estate).",
    )
