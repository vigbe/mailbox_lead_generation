from odoo.tests.common import TransactionCase


class TestCorreosLeads(TransactionCase):

    def setUp(self):
        super().setUp()
        self.correos_leads = self.env['correos.leads'].create({
            'name': 'Test Record',
        })

    def test_create(self):
        self.assertTrue(self.correos_leads.id)
        self.assertEqual(self.correos_leads.state, 'draft')

    def test_action_confirm(self):
        self.correos_leads.action_confirm()
        self.assertEqual(self.correos_leads.state, 'confirmed')

    def test_action_done(self):
        self.correos_leads.action_confirm()
        self.correos_leads.action_done()
        self.assertEqual(self.correos_leads.state, 'done')

    def test_unlink_draft_only(self):
        with self.assertRaises(Exception):
            self.correos_leads.action_confirm()
            self.correos_leads.unlink()
