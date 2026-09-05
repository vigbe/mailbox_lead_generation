# pyright: reportMissingImports=false
# (odoo framework imports resolve only inside the Odoo runtime)
import logging

from odoo import http

_logger = logging.getLogger(__name__)


class MailboxLeadGenerationController(http.Controller):
    pass
