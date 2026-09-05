# pyright: reportMissingImports=false
# (odoo framework imports resolve only inside the Odoo runtime)
import json
import logging

import requests

from odoo import models
from odoo.tools import html2plaintext

_logger = logging.getLogger(__name__)

# Default OpenAI-compatible endpoint used when no ``ai_base_url`` is configured.
_DEFAULT_AI_BASE_URL = "https://api.openai.com/v1"

# Canonical category domain shared with the concrete model
# (``mailbox.lead.generation``). Keeping a local copy avoids a hard import
# dependency from the abstract mixin back into the concrete model.
_AI_CATEGORY_DOMAIN = ("lead", "captacion", "servicio", "otro")

# Canonical intent domain shared with the concrete model's ``ai_intent`` field.
# The values are intentionally English-stable literals so the domain-agnostic
# system prompt never emits a Spanish vertical term (e.g. "arriendo").
_AI_INTENT_DOMAIN = (
    "property_sale",
    "property_rent",
    "service",
    "promotion",
    "other",
)


class MailboxLeadGenerationAIProvider(models.AbstractModel):
    """Abstract OpenAI-compatible AI provider mixin.

    Encapsulates the transport layer (HTTP chat-completion client) and the
    strict response-contract normalizer, so the concrete
    ``mailbox.lead.generation`` model stays focused on its domain logic.

    The mixin is consumed through classical inheritance::

        _inherit = ["mail.thread", "mail.activity.mixin",
                    "mailbox.lead.generation.ai.provider"]
    """

    _name = "mailbox.lead.generation.ai.provider"
    _description = "Mailbox Lead Generation AI Provider (abstract mixin)"

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    def _ai_get_config(self):
        """Read the 7 AI config parameters from ``ir.config_parameter``.

        Integer-valued parameters (``max_tokens``, ``timeout``, ``retries``)
        are coerced to ``int`` with safe defaults. Returns a plain dict.
        """
        ICP = self.env["ir.config_parameter"].sudo()

        def _get(key, default=""):
            return ICP.get_param(key) or default

        def _get_int(key, default):
            raw = _get(key)
            try:
                return int(raw) if raw not in (None, "") else default
            except (TypeError, ValueError):
                _logger.warning(
                    "mailbox.lead.generation: invalid int for %s=%r; "
                    "falling back to default %d.",
                    key,
                    raw,
                    default,
                )
                return default

        return {
            "provider": _get("mailbox_lead_generation.ai_provider", "openai"),
            "api_key": _get("mailbox_lead_generation.ai_api_key"),
            "model": _get("mailbox_lead_generation.ai_model", "gpt-4o-mini"),
            "base_url": _get("mailbox_lead_generation.ai_base_url")
            or _DEFAULT_AI_BASE_URL,
            "max_tokens": _get_int("mailbox_lead_generation.ai_max_tokens", 1000),
            "timeout": _get_int("mailbox_lead_generation.ai_timeout", 30),
            "retries": _get_int("mailbox_lead_generation.ai_retries", 2),
        }

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------
    def _ia_chat(self, messages):
        """Call an OpenAI-compatible ``chat/completions`` endpoint.

        - Retries up to ``retries + 1`` times on any failure (exception,
          non-2xx HTTP status, or non-JSON body).
        - Returns the parsed JSON payload found under
          ``choices[0].message.content`` as a dict.
        - Raises ``ValueError`` immediately when the API key is empty.
        - Propagates the last exception after all retries are exhausted.
        """
        config = self._ai_get_config()
        api_key = config["api_key"]
        if not api_key:
            raise ValueError(
                "AI API key is not configured (mailbox_lead_generation.ai_api_key)."
            )

        base_url = (config["base_url"] or _DEFAULT_AI_BASE_URL).rstrip("/")
        url = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": config["model"],
            "messages": messages,
            "response_format": {"type": "json_object"},
            "temperature": 0.0,
            "max_tokens": config["max_tokens"],
        }
        timeout = config["timeout"]
        attempts = max(1, config["retries"] + 1)

        last_exc = RuntimeError("AI chat did not execute any attempt.")
        for attempt in range(attempts):
            try:
                response = requests.post(
                    url, headers=headers, json=payload, timeout=timeout
                )
                if response.status_code < 200 or response.status_code >= 300:
                    raise ValueError(
                        f"AI endpoint returned HTTP {response.status_code}."
                    )
                body = response.json()
                content = body["choices"][0]["message"]["content"]
                return json.loads(content)
            except Exception as exc:  # noqa: BLE001 - retry any transport/parse failure
                last_exc = exc
                _logger.warning(
                    "mailbox.lead.generation: AI chat attempt %d/%d failed: %s",
                    attempt + 1,
                    attempts,
                    exc,
                )
        # All retries exhausted: propagate the last observed failure.
        raise last_exc

    # ------------------------------------------------------------------
    # Prompt building (domain-agnostic)
    # ------------------------------------------------------------------
    def _ai_build_system_prompt(self):
        """Build a domain-agnostic system prompt for incoming-email triage.

        Reads the routing mailboxes and the configured dynamic-model label
        from ``ir.config_parameter`` so the prompt adapts to the install
        without ever hardcoding a vertical vocabulary (no property type or
        operation term is emitted). The model is instructed to return the
        strict JSON contract consumed by ``_ai_validate_contract``.

        ``self`` is a single ``mailbox.lead.generation`` record.
        """
        self.ensure_one()
        ICP = self.env["ir.config_parameter"].sudo()
        email_consultas = ICP.get_param("mailbox_lead_generation.email_consultas") or ""
        email_captacion = ICP.get_param("mailbox_lead_generation.email_captacion") or ""
        dynamic_model = (
            ICP.get_param("mailbox_lead_generation.dynamic_model")
            or "product.real_estate"
        )
        catalog_label = ""
        if dynamic_model in self.env:
            catalog_label = self.env[dynamic_model]._description or dynamic_model

        # Generic catalog clause; only the model's own label is interpolated
        # (concatenation, never ``%`` formatting, so a label containing '%'
        # cannot break the template below).
        catalog_clause = ""
        if catalog_label:
            catalog_clause = (
                " The available item catalog is named '"
                + catalog_label
                + "'; when the client is looking for an item, describe it "
                "generically."
            )

        return (
            "You are an assistant that triages incoming business emails and "
            "returns STRICT JSON only (no markdown, no commentary).\n"
            "\n"
            "Routing context:\n"
            f"- Emails addressed to {email_consultas} express inbound client "
            "interest (a prospective client asking about an item or service).\n"
            f"- Emails addressed to {email_captacion} come from an owner offering "
            f"an item for the catalog.{catalog_clause}\n"
            "\n"
            "Analyze the email and return a JSON object with EXACTLY these "
            "keys:\n"
            '- "category": one of "lead", "captacion", "servicio", '
            '"otro".\n'
            '- "intent": one of "property_sale", "property_rent", '
            '"service", "promotion", "other".\n'
            '- "confidence": a number between 0 and 1.\n'
            '- "extracted_data": an object with any of: contact_name, '
            "contact_phone, contact_email, operation, location, budget, "
            "property_category, notes, clean_summary.\n"
            "\n"
            "Rules:\n"
            '- "category" "lead" = inbound client interest; "captacion" = '
            'an owner offering an item; "servicio" = a request for a service; '
            '"otro" = none of the above.\n'
            '- "intent" "property_sale" = the client wants to buy an item; '
            '"property_rent" = the client wants to rent an item; "service" = '
            'the client wants a service; "promotion" = the client wants to '
            'highlight an existing listing; "other" = undetermined.\n'
            '- Always include "clean_summary": a short neutral summary of '
            "the request.\n"
        )

    def _ai_build_user_message(self):
        """Build a clean plain-text user message from the record's email.

        The HTML body is converted to plain text with ``html2plaintext`` so
        inner text is preserved while markup is stripped. ``self`` is a
        single ``mailbox.lead.generation`` record.
        """
        self.ensure_one()
        body_text = html2plaintext(self.body_html or "")
        return (
            f"From: {self.email_from or ''}\n"
            f"To: {self.email_to or ''}\n"
            f"Subject: {self.subject or ''}\n"
            f"Body: {body_text}"
        )

        # ------------------------------------------------------------------
        # Contract normalization

    # ------------------------------------------------------------------
    def _ai_validate_contract(self, data):
        """Normalize a raw AI JSON payload into model field values.

        Returns a dict of vals suitable for ``write``/``create`` on the
        concrete model. Raises ``ValueError`` when ``data`` is not a dict.
        """
        if not isinstance(data, dict):
            raise ValueError("AI response must be a JSON object (dict).")

        extracted = data.get("extracted_data")
        if not isinstance(extracted, dict):
            extracted = {}

        def _text(value):
            return str(value).strip() if value not in (None, "") else ""

        category = _text(data.get("category"))
        if category not in _AI_CATEGORY_DOMAIN:
            category = "otro"

        intent = _text(data.get("intent"))
        if intent not in _AI_INTENT_DOMAIN:
            intent = "other"

        confidence = data.get("confidence")
        try:
            confidence = float(confidence) if confidence is not None else 0.0
        except (TypeError, ValueError):
            confidence = 0.0
        confidence = min(1.0, max(0.0, confidence))

        return {
            "ai_category": category,
            "ai_intent": intent,
            "ai_confidence": confidence,
            "ai_summary": _text(extracted.get("clean_summary")),
            "ai_extracted": extracted,
            "phone": _text(extracted.get("phone")),
            "operation": _text(extracted.get("operation")),
            "ai_raw_response": json.dumps(data, ensure_ascii=False, default=str),
        }
