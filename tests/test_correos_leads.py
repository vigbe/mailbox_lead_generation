from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCorreosLeads(TransactionCase):
    _uid_seq = 0

    def setUp(self):
        super().setUp()
        self.CorreosLeads = self.env["correos.leads"]
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
        record = self.CorreosLeads.message_new(msg)
        self.assertTrue(record.id)
        self.assertEqual(record.state, "nuevo")
        self.assertEqual(record.subject, "Departamento en Las Condes")
        self.assertEqual(record.email_from, "juan@example.com")
        self.assertEqual(record.email_to, "consultas@tudominio.com")
        self.assertEqual(record.body_html, "<p>Hola, quiero informacion.</p>")
        self.assertIn("Departamento en Las Condes", record.name)  # subject in name
        self.assertIn("juan", record.name.lower())  # sender local part in name

    def test_assign_lead_type_by_destination(self):
        self.ICP.set_param("correos_leads.email_consultas", "consultas@tudominio.com")
        self.ICP.set_param("correos_leads.email_captacion", "captacion@tudominio.com")
        self.assertEqual(
            self.CorreosLeads._assign_lead_type("consultas@tudominio.com"),
            "consulta",
        )
        self.assertEqual(
            self.CorreosLeads._assign_lead_type("captacion@tudominio.com"),
            "captacion",
        )
        self.assertEqual(
            self.CorreosLeads._assign_lead_type("desconocido@otro.com"),
            "sin_clasificar",
        )
        # End-to-end via message_new
        record = self.CorreosLeads.message_new(
            self._build_msg_dict(message_id="<cons@example.com>")
        )
        self.assertEqual(record.lead_type, "consulta")

    def test_message_new_dedup_by_message_id(self):
        msg = self._build_msg_dict(message_id="<dedup@example.com>")
        first = self.CorreosLeads.message_new(msg)
        second = self.CorreosLeads.message_new(msg)
        self.assertEqual(first, second)
        self.assertEqual(
            self.CorreosLeads.search_count(
                [("message_id", "=", "<dedup@example.com>")]
            ),
            1,
        )

    def test_convert_to_lead_creates_crm_lead(self):
        record = self.CorreosLeads.message_new(
            self._build_msg_dict(message_id="<convert@example.com>")
        )
        record.action_convert_to_lead()
        self.assertEqual(record.state, "convertido")
        self.assertTrue(record.crm_lead_id.id)
        lead = record.crm_lead_id
        self.assertEqual(lead.email_from, "juan@example.com")
        self.assertTrue(lead.partner_id.id)

    def test_convert_twice_raises(self):
        record = self.CorreosLeads.message_new(
            self._build_msg_dict(message_id="<twice@example.com>")
        )
        record.action_convert_to_lead()
        with self.assertRaises(UserError):
            record.action_convert_to_lead()

    def test_reject_spam(self):
        record = self.CorreosLeads.message_new(
            self._build_msg_dict(message_id="<spam@example.com>")
        )
        record.action_reject_spam()
        self.assertEqual(record.state, "rechazado_spam")

    def test_unlink_blocked_when_converted(self):
        converted = self.CorreosLeads.message_new(
            self._build_msg_dict(message_id="<del1@example.com>")
        )
        converted.action_convert_to_lead()
        with self.assertRaises(UserError):
            converted.unlink()
        # Deleting a non-converted record works.
        nuevo = self.CorreosLeads.message_new(
            self._build_msg_dict(message_id="<del2@example.com>")
        )
        nuevo.unlink()
        self.assertFalse(nuevo.exists())
