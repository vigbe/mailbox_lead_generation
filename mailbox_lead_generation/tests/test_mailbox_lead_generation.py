# pyright: reportMissingImports=false
# (odoo framework imports resolve only inside the Odoo runtime)
import json
from unittest import mock

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

# Fully-qualified target for patching ``requests.post`` inside the AI provider
# module (kept as a constant so test lines stay short).
_AI_PROVIDER_REQUESTS_POST = (
    "odoo.addons.mailbox_lead_generation.models.ai_provider.requests.post"
)


@tagged("post_install", "-at_install")
class TestMailboxLeadGeneration(TransactionCase):
    _uid_seq = 0

    def setUp(self):
        super().setUp()
        self.MailboxLeadGeneration = self.env["mailbox.lead.generation"]
        self.ICP = self.env["ir.config_parameter"].sudo()

    def _next_uid(self):
        type(self)._uid_seq += 1
        return type(self)._uid_seq

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _build_msg_dict(self, **overrides):
        """Build a minimal msg_dict as produced by mail's message_process."""
        msg = {
            "message_id": f"<test-{self._next_uid()}@example.com>",
            "subject": "Departamento en Las Condes",
            "from": "Juan Perez <juan@example.com>",
            "email_from": "juan@example.com",
            "to": "consultas@tudominio.com",
            "recipients": ["consultas@tudominio.com"],
            "date": False,
            "body": "<p>Hola, quiero informacion.</p>",
        }
        msg.update(overrides)
        return msg

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------
    def test_message_new_creates_record(self):
        msg = self._build_msg_dict()
        record = self.MailboxLeadGeneration.message_new(msg)
        self.assertTrue(record.id)
        self.assertEqual(record.state, "nuevo")
        self.assertEqual(record.subject, "Departamento en Las Condes")
        self.assertEqual(record.email_from, "juan@example.com")
        self.assertEqual(record.email_to, "consultas@tudominio.com")
        self.assertEqual(record.body_html, "<p>Hola, quiero informacion.</p>")
        self.assertIn("Departamento en Las Condes", record.name)  # subject in name
        self.assertIn("juan", record.name.lower())  # sender local part in name

    def test_assign_lead_type_by_destination(self):
        self.ICP.set_param(
            "mailbox_lead_generation.email_consultas", "consultas@tudominio.com"
        )
        self.ICP.set_param(
            "mailbox_lead_generation.email_captacion", "captacion@tudominio.com"
        )
        self.assertEqual(
            self.MailboxLeadGeneration._assign_lead_type("consultas@tudominio.com"),
            "consulta",
        )
        self.assertEqual(
            self.MailboxLeadGeneration._assign_lead_type("captacion@tudominio.com"),
            "captacion",
        )
        self.assertEqual(
            self.MailboxLeadGeneration._assign_lead_type("desconocido@otro.com"),
            "sin_clasificar",
        )
        # End-to-end via message_new
        record = self.MailboxLeadGeneration.message_new(
            self._build_msg_dict(message_id="<cons@example.com>")
        )
        self.assertEqual(record.lead_type, "consulta")

    def test_message_new_dedup_by_message_id(self):
        msg = self._build_msg_dict(message_id="<dedup@example.com>")
        first = self.MailboxLeadGeneration.message_new(msg)
        second = self.MailboxLeadGeneration.message_new(msg)
        self.assertEqual(first, second)
        self.assertEqual(
            self.MailboxLeadGeneration.search_count(
                [("message_id", "=", "<dedup@example.com>")]
            ),
            1,
        )

    def test_convert_to_lead_creates_crm_lead(self):
        record = self.MailboxLeadGeneration.message_new(
            self._build_msg_dict(message_id="<convert@example.com>")
        )
        record.action_convert_to_lead()
        self.assertEqual(record.state, "convertido")
        self.assertTrue(record.crm_lead_id.id)
        lead = record.crm_lead_id
        self.assertEqual(lead.email_from, "juan@example.com")
        self.assertTrue(lead.partner_id.id)

    def test_convert_twice_raises(self):
        record = self.MailboxLeadGeneration.message_new(
            self._build_msg_dict(message_id="<twice@example.com>")
        )
        record.action_convert_to_lead()
        with self.assertRaises(UserError):
            record.action_convert_to_lead()

    def test_reject_spam(self):
        record = self.MailboxLeadGeneration.message_new(
            self._build_msg_dict(message_id="<spam@example.com>")
        )
        record.action_reject_spam()
        self.assertEqual(record.state, "rechazado_spam")

    def test_unlink_blocked_when_converted(self):
        converted = self.MailboxLeadGeneration.message_new(
            self._build_msg_dict(message_id="<del1@example.com>")
        )
        converted.action_convert_to_lead()
        with self.assertRaises(UserError):
            converted.unlink()
        # Deleting a non-converted record works.
        nuevo = self.MailboxLeadGeneration.message_new(
            self._build_msg_dict(message_id="<del2@example.com>")
        )
        nuevo.unlink()
        self.assertFalse(nuevo.exists())

    # ------------------------------------------------------------------
    # PR-1 — AI schema & config (TASK-PR1-002 / 003 / 005 / 006)
    # ------------------------------------------------------------------
    def _create_record(self, **vals):
        """Create a minimal mailbox.lead.generation record for AI-schema tests."""
        base = {
            "name": "Correo de prueba IA",
            "email_from": "test@example.com",
        }
        base.update(vals)
        return self.MailboxLeadGeneration.create(base)

    # --- TASK-PR1-002: _compute_category (IA wins, lead_type fallback) ---
    def test_compute_category_ai_wins_over_lead_type(self):
        record = self._create_record(
            ai_category="captacion", lead_type="sin_clasificar"
        )
        self.assertEqual(record.category, "captacion")

    def test_compute_category_fallback_consulta(self):
        record = self._create_record(lead_type="consulta")
        self.assertFalse(record.ai_category)
        self.assertEqual(record.category, "lead")

    def test_compute_category_fallback_captacion(self):
        record = self._create_record(lead_type="captacion")
        self.assertEqual(record.category, "captacion")

    def test_compute_category_unknown_lead_type(self):
        record = self._create_record(lead_type="sin_clasificar")
        self.assertEqual(record.category, "otro")

    # --- TASK-PR1-003: _selection_dynamic_models ---
    def test_selection_dynamic_models_non_empty(self):
        choices = self.MailboxLeadGeneration._selection_dynamic_models()
        self.assertIsInstance(choices, list)
        self.assertGreaterEqual(len(choices), 1)

    def test_selection_dynamic_models_includes_catalogs(self):
        # product.template is the product-agnostic default catalog;
        # product.real_estate is offered only when real_estate_products is
        # installed (registry check, no hard dependency).
        choices = self.MailboxLeadGeneration._selection_dynamic_models()
        keys = [key for key, _ in choices]
        if "product.template" in self.env:
            self.assertIn("product.template", keys)
        if "product.real_estate" in self.env:
            self.assertIn("product.real_estate", keys)

    def test_selection_dynamic_models_configured_model(self):
        if "product.real_estate" not in self.env:
            self.skipTest("product.real_estate not installed in this DB")
        self.ICP.set_param(
            "mailbox_lead_generation.dynamic_model", "product.real_estate"
        )
        choices = self.MailboxLeadGeneration._selection_dynamic_models()
        self.assertIn("product.real_estate", [key for key, _ in choices])

    def test_selection_dynamic_models_unknown_model(self):
        # Unknown dynamic_model must not crash; always >=1 fallback option
        self.ICP.set_param(
            "mailbox_lead_generation.dynamic_model", "inmuebles.no.existe"
        )
        choices = self.MailboxLeadGeneration._selection_dynamic_models()
        self.assertGreaterEqual(len(choices), 1)
        keys = [key for key, _ in choices]
        if "product.template" in self.env:
            self.assertIn("product.template", keys)
        if "product.real_estate" in self.env:
            self.assertIn("product.real_estate", keys)

    # --- TASK-PR1-005: actions lifecycle ---
    def test_action_send_to_pending_from_nuevo(self):
        record = self._create_record(state="nuevo")
        record.action_send_to_pending()
        self.assertEqual(record.state, "pending")

    def test_action_send_to_pending_from_error(self):
        record = self._create_record(state="error")
        record.action_send_to_pending()
        self.assertEqual(record.state, "pending")

    def test_action_send_to_pending_from_procesando(self):
        # R1 mitigation: a record stuck in 'procesando' can be re-queued
        record = self._create_record(state="procesando")
        record.action_send_to_pending()
        self.assertEqual(record.state, "pending")

    def test_action_send_to_pending_ignores_convertido(self):
        record = self._create_record(state="convertido")
        record.action_send_to_pending()
        self.assertEqual(record.state, "convertido")

    def test_action_retry_ai_from_error(self):
        record = self._create_record(state="error")
        record.action_retry_ai()
        self.assertEqual(record.state, "pending")

    def test_action_retry_ai_ignores_pending(self):
        record = self._create_record(state="pending")
        record.action_retry_ai()
        self.assertEqual(record.state, "pending")

    # --- TASK-PR1-006: _cron_process_ai_batch (safe stub) ---
    def test_cron_process_ai_batch_empty(self):
        # No pending records -> must not raise
        records = self.MailboxLeadGeneration._cron_process_ai_batch(limit=50)
        self.assertFalse(records)

    # ------------------------------------------------------------------
    # PR-2 Phase A — TASK-PR2-001: AI provider mixin
    # (mailbox.lead.generation.ai.provider) — mocked HTTP, no network.
    # ------------------------------------------------------------------
    def _set_ai_config(self, **overrides):
        """Populate the 7 ICP AI config parameters for provider tests."""
        defaults = {
            "provider": "openai",
            "api_key": "test-key",
            "model": "gpt-4o-mini",
            "base_url": "https://api.openai.com/v1",
            "max_tokens": 1000,
            "timeout": 30,
            "retries": 2,
        }
        defaults.update(overrides)
        self.ICP.set_param("mailbox_lead_generation.ai_provider", defaults["provider"])
        self.ICP.set_param("mailbox_lead_generation.ai_api_key", defaults["api_key"])
        self.ICP.set_param("mailbox_lead_generation.ai_model", defaults["model"])
        self.ICP.set_param("mailbox_lead_generation.ai_base_url", defaults["base_url"])
        self.ICP.set_param(
            "mailbox_lead_generation.ai_max_tokens", str(defaults["max_tokens"])
        )
        self.ICP.set_param(
            "mailbox_lead_generation.ai_timeout", str(defaults["timeout"])
        )
        self.ICP.set_param(
            "mailbox_lead_generation.ai_retries", str(defaults["retries"])
        )

    def _ai_contract_payload(self, **overrides):
        """A valid raw AI JSON payload matching the strict contract."""
        data = {
            "category": "lead",
            "confidence": 0.9,
            "extracted_data": {
                "name": "Juan Perez",
                "phone": "+56912345678",
                "email": "juan@example.com",
                "operation": "compra",
                "model_reference_id": "Producto solicitado",
                "clean_summary": "Cliente busca un producto en zona centrica.",
            },
        }
        data.update(overrides)
        return data

    def _ai_choices_response(self, content_obj, status_code=200):
        """Build a fake OpenAI-style response object for mocked requests.post."""
        response = mock.Mock()
        response.status_code = status_code
        response.json.return_value = {
            "choices": [{"message": {"content": json.dumps(content_obj)}}]
        }
        return response

    # --- _ia_chat (mock requests.post, no network) ---
    def test_ia_chat_parses_json_ok(self):
        self._set_ai_config()
        provider = self.env["mailbox.lead.generation.ai.provider"]
        payload = self._ai_contract_payload()
        with mock.patch(_AI_PROVIDER_REQUESTS_POST) as mock_post:
            mock_post.return_value = self._ai_choices_response(payload)
            result = provider._ia_chat([{"role": "user", "content": "hi"}])
        self.assertEqual(result, payload)
        self.assertEqual(mock_post.call_count, 1)

    def test_ia_chat_retries_then_succeeds(self):
        # retries=1 -> attempts = retries + 1 = 2
        self._set_ai_config(retries=1)
        provider = self.env["mailbox.lead.generation.ai.provider"]
        payload = self._ai_contract_payload()
        failed = self._ai_choices_response({}, status_code=500)
        success = self._ai_choices_response(payload)
        with mock.patch(_AI_PROVIDER_REQUESTS_POST) as mock_post:
            mock_post.side_effect = [failed, success]
            result = provider._ia_chat([{"role": "user", "content": "hi"}])
        self.assertEqual(mock_post.call_count, 2)
        self.assertEqual(result, payload)

    def test_ia_chat_raises_when_api_key_empty(self):
        self._set_ai_config(api_key="")
        provider = self.env["mailbox.lead.generation.ai.provider"]
        with mock.patch(_AI_PROVIDER_REQUESTS_POST) as mock_post:
            with self.assertRaises(ValueError):
                provider._ia_chat([{"role": "user", "content": "hi"}])
            self.assertFalse(mock_post.called)

    # --- _ai_validate_contract ---
    def test_ai_validate_contract_valid(self):
        provider = self.env["mailbox.lead.generation.ai.provider"]
        vals = provider._ai_validate_contract(self._ai_contract_payload())
        self.assertEqual(vals["ai_category"], "lead")
        self.assertEqual(vals["ai_confidence"], 0.9)
        self.assertEqual(vals["phone"], "+56912345678")
        self.assertEqual(vals["operation"], "compra")
        self.assertEqual(
            vals["ai_summary"], "Cliente busca un producto en zona centrica."
        )
        self.assertIn("ai_raw_response", vals)

    def test_ai_validate_contract_category_out_of_domain(self):
        provider = self.env["mailbox.lead.generation.ai.provider"]
        vals = provider._ai_validate_contract(self._ai_contract_payload(category="foo"))
        self.assertEqual(vals["ai_category"], "otro")

    def test_ai_validate_contract_non_dict_raises(self):
        provider = self.env["mailbox.lead.generation.ai.provider"]
        with self.assertRaises(ValueError):
            provider._ai_validate_contract("not a dict")
        with self.assertRaises(ValueError):
            provider._ai_validate_contract(None)

    def test_ai_validate_contract_confidence_clamped(self):
        provider = self.env["mailbox.lead.generation.ai.provider"]
        vals = provider._ai_validate_contract(self._ai_contract_payload(confidence=1.5))
        self.assertEqual(vals["ai_confidence"], 1.0)

    # ------------------------------------------------------------------
    # PR-2 Phase A — TASK-PR2-002: mixin wired into the concrete model
    # ------------------------------------------------------------------
    def test_ia_chat_available_on_lead_model(self):
        """After upgrade the concrete model exposes the mixin transport API."""
        model = self.env["mailbox.lead.generation"]
        self.assertTrue(callable(getattr(model, "_ia_chat", None)))
        self.assertTrue(callable(getattr(model, "_ai_validate_contract", None)))
        self.assertTrue(callable(getattr(model, "_ai_get_config", None)))

    # ------------------------------------------------------------------
    # PR-2 Phase A — TASK-PR2-003: domain-agnostic prompts
    # ------------------------------------------------------------------
    def test_ai_build_system_prompt_contains_routing(self):
        self.ICP.set_param(
            "mailbox_lead_generation.email_consultas", "consultas@tudominio.com"
        )
        self.ICP.set_param(
            "mailbox_lead_generation.email_captacion", "captacion@tudominio.com"
        )
        self.ICP.set_param(
            "mailbox_lead_generation.dynamic_model", "product.real_estate"
        )
        record = self._create_record()
        prompt = record._ai_build_system_prompt()
        self.assertIn("consultas@tudominio.com", prompt)
        self.assertIn("captacion@tudominio.com", prompt)

    def test_ai_build_system_prompt_contains_dynamic_model_label(self):
        if "product.real_estate" not in self.env:
            self.skipTest("product.real_estate not installed in this DB")
        self.ICP.set_param(
            "mailbox_lead_generation.dynamic_model", "product.real_estate"
        )
        record = self._create_record()
        prompt = record._ai_build_system_prompt()
        label = self.env["product.real_estate"]._description
        self.assertIn(label, prompt)

    def test_ai_build_system_prompt_is_domain_agnostic(self):
        self.ICP.set_param(
            "mailbox_lead_generation.dynamic_model", "product.real_estate"
        )
        record = self._create_record()
        prompt = record._ai_build_system_prompt().lower()
        # Must not hardcode any specific vertical vocabulary.
        self.assertNotIn("departamento", prompt)
        self.assertNotIn("arriendo", prompt)
        # Must not leak the legacy real-estate contract keys.
        self.assertNotIn("property_sale", prompt)
        self.assertNotIn("property_rent", prompt)
        self.assertNotIn("property_category", prompt)
        # Emits the neutral intent domain and extraction key instead.
        self.assertIn('"purchase"', prompt)
        self.assertIn('"rent"', prompt)
        self.assertIn("item_category", prompt)

    def test_ai_build_user_message_contains_email_fields(self):
        record = self._create_record(
            email_from="juan@example.com",
            email_to="consultas@tudominio.com",
            subject="Hola",
            body_html="<p>Mensaje <strong>importante</strong></p>",
        )
        msg = record._ai_build_user_message()
        self.assertIn("juan@example.com", msg)
        self.assertIn("consultas@tudominio.com", msg)
        self.assertIn("Hola", msg)
        # html2plaintext must strip tags but keep inner text.
        self.assertIn("importante", msg)
        self.assertNotIn("<strong>", msg)

    # ------------------------------------------------------------------
    # PR-2 Phase C1 — intent in the contract + wired pipeline + cron.
    # ------------------------------------------------------------------
    def test_ai_validate_contract_extracts_intent(self):
        provider = self.env["mailbox.lead.generation.ai.provider"]
        vals = provider._ai_validate_contract(
            self._ai_contract_payload(intent="purchase")
        )
        self.assertEqual(vals["ai_intent"], "purchase")
        # Unknown intent falls back to "other".
        vals = provider._ai_validate_contract(
            self._ai_contract_payload(intent="nonsense")
        )
        self.assertEqual(vals["ai_intent"], "other")
        # Missing intent also falls back to "other".
        vals = provider._ai_validate_contract(self._ai_contract_payload())
        self.assertEqual(vals["ai_intent"], "other")
        # ai_extracted holds the raw extracted_data dict as-is.
        self.assertIsInstance(vals["ai_extracted"], dict)

    def test_analyze_and_match_properties_writes_intent_and_state(self):
        self._set_ai_config()
        record = self._create_record(state="procesando")
        payload = self._ai_contract_payload(intent="purchase", category="lead")
        with mock.patch(_AI_PROVIDER_REQUESTS_POST) as mock_post:
            mock_post.return_value = self._ai_choices_response(payload)
            record._analyze_and_match_properties()
        self.assertEqual(record.ai_intent, "purchase")
        self.assertEqual(record.ai_category, "lead")
        self.assertEqual(record.ai_confidence, 0.9)
        self.assertEqual(record.state, "procesado")

    def test_cron_process_ai_batch_processes_pending(self):
        self._set_ai_config()
        rec1 = self._create_record(state="pending")
        rec2 = self._create_record(state="pending")
        payload = self._ai_contract_payload(intent="service", category="servicio")
        with mock.patch(_AI_PROVIDER_REQUESTS_POST) as mock_post:
            mock_post.return_value = self._ai_choices_response(payload)
            result = self.MailboxLeadGeneration._cron_process_ai_batch(limit=50)
        self.assertEqual(rec1.state, "procesado")
        self.assertEqual(rec2.state, "procesado")
        self.assertEqual(len(result), 2)

    def test_cron_process_ai_batch_error_does_not_abort(self):
        # retries=0 -> exactly one requests.post call per record.
        self._set_ai_config(retries=0)
        # Created first (lower id) -> processed LAST by the id-desc order.
        rec_ok = self._create_record(state="pending")
        # Created second (higher id) -> processed FIRST and fails.
        rec_fail = self._create_record(state="pending")
        payload = self._ai_contract_payload(intent="service", category="servicio")
        with mock.patch(_AI_PROVIDER_REQUESTS_POST) as mock_post:
            mock_post.side_effect = [
                RuntimeError("AI endpoint down"),  # rec_fail (id desc first)
                self._ai_choices_response(payload),  # rec_ok
            ]
            # Must NOT raise even though one record fails.
            result = self.MailboxLeadGeneration._cron_process_ai_batch(limit=50)
        self.assertEqual(rec_fail.state, "error")
        self.assertEqual(rec_ok.state, "procesado")
        self.assertEqual(len(result), 1)

    def test_run_matching_routes_purchase_intent(self):
        if "product.real_estate" not in self.env:
            self.skipTest("product.real_estate not installed in this DB")
        owner = self.env["res.partner"].create({"name": "Dueño matching"})
        prop = self.env["product.real_estate"].create(
            {
                "name": "Inmueble prueba matching",
                "propietario_id": owner.id,
                "operacion": "venta",
                "tipo_propiedad": "departamento",
            }
        )
        lead = self._create_record(ai_intent="purchase", ai_extracted={})
        fake_match = [
            {
                "res_model": "product.real_estate",
                "res_id": prop.id,
                "match_type": "propiedad",
                "score": 0.88,
                "reason": "Coincidencia por ubicación y presupuesto.",
            }
        ]
        with mock.patch.object(
            type(lead), "_match_real_estate", return_value=fake_match
        ) as mk:
            result = lead._run_matching()
        mk.assert_called_once_with("purchase", {})
        self.assertEqual(result._name, "mailbox.lead.suggestion")
        self.assertEqual(len(result), 1)
        suggestion = result
        self.assertEqual(suggestion.res_model, "product.real_estate")
        self.assertEqual(suggestion.res_id, prop.id)
        self.assertEqual(suggestion.match_type, "propiedad")
        self.assertAlmostEqual(suggestion.score, 0.88, places=2)
