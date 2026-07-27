from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # ------------------------------------------------------------------
    # Clasificación de correos (legacy)
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Decantación IA (PR-1) — parámetros vía ir.config_parameter
    # Clave ICP real con prefijo ``correos_leads.`` (coherente con los
    # parámetros de clasificación legacy y con el consumidor del pipeline IA).
    # ------------------------------------------------------------------
    correos_ai_provider = fields.Char(
        string="Proveedor IA",
        config_parameter="correos_leads.ai_provider",
        default="openai",
        help="Identificador del proveedor OpenAI-compatible a usar.",
    )
    correos_ai_api_key = fields.Char(
        string="API key IA",
        config_parameter="correos_leads.ai_api_key",
        help="Clave de API del proveedor. Si está vacía, la IA queda "
        "deshabilitada y los registros pasan a estado «error».",
    )
    correos_ai_model = fields.Char(
        string="Modelo IA",
        config_parameter="correos_leads.ai_model",
        default="gpt-4o-mini",
        help="Nombre del modelo a invocar (ej. gpt-4o-mini).",
    )
    correos_ai_base_url = fields.Char(
        string="Base URL IA",
        config_parameter="correos_leads.ai_base_url",
        help="URL base del endpoint OpenAI-compatible. "
        "Vacío = endpoint por defecto del proveedor.",
    )
    correos_ai_max_tokens = fields.Integer(
        string="Máx. tokens",
        config_parameter="correos_leads.ai_max_tokens",
        default=1000,
        help="Cantidad máxima de tokens de la respuesta IA.",
    )
    correos_ai_timeout = fields.Integer(
        string="Timeout (s)",
        config_parameter="correos_leads.ai_timeout",
        default=30,
        help="Timeout en segundos para cada llamada HTTP a la IA.",
    )
    correos_ai_retries = fields.Integer(
        string="Reintentos",
        config_parameter="correos_leads.ai_retries",
        default=2,
        help="Número de reintentos ante fallos de red/parseo por registro.",
    )
    correos_dynamic_model = fields.Char(
        string="Modelo dinámico",
        config_parameter="correos_leads.dynamic_model",
        default="product.real_estate",
        help="Modelo Odoo contra el que se resuelve el matching de la IA "
        "(default: product.real_estate).",
    )
