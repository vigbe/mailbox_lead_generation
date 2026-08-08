from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


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
        self.ICP.set_param("mailbox_lead_generation.email_consultas", "consultas@tudominio.com")
        self.ICP.set_param("mailbox_lead_generation.email_captacion", "captacion@tudominio.com")
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

    def test_selection_dynamic_models_includes_real_estate(self):
        # real_estate_products is a module dependency -> always installed
        choices = self.MailboxLeadGeneration._selection_dynamic_models()
        keys = [key for key, _ in choices]
        self.assertIn("product.real_estate", keys)

    def test_selection_dynamic_models_configured_model(self):
        self.ICP.set_param("mailbox_lead_generation.dynamic_model", "product.real_estate")
        choices = self.MailboxLeadGeneration._selection_dynamic_models()
        self.assertIn("product.real_estate", [key for key, _ in choices])

    def test_selection_dynamic_models_unknown_model(self):
        # Unknown dynamic_model must not crash; always >=1 fallback option
        self.ICP.set_param("mailbox_lead_generation.dynamic_model", "inmuebles.no.existe")
        choices = self.MailboxLeadGeneration._selection_dynamic_models()
        self.assertGreaterEqual(len(choices), 1)
        self.assertIn("product.real_estate", [key for key, _ in choices])

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

    def test_cron_process_ai_batch_no_side_effects(self):
        rec1 = self._create_record(state="pending")
        rec2 = self._create_record(state="pending")
        records = self.MailboxLeadGeneration._cron_process_ai_batch(limit=50)
        self.assertEqual(len(records), 2)
        # Stub must NOT change state (no IA call, no claim)
        self.assertEqual(rec1.state, "pending")
        self.assertEqual(rec2.state, "pending")
