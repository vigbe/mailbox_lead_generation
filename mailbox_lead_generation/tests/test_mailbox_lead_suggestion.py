# pyright: reportMissingImports=false
# (odoo framework imports resolve only inside the Odoo runtime)
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMailboxLeadSuggestion(TransactionCase):
    """Phase B — structural plumbing tests for ``mailbox.lead.suggestion``.

    No AI, no network: these tests exercise the polymorphic suggestion model,
    the ``suggestion_ids`` One2many, the source registry scaffolds, and the
    conditional ``property_ids`` mirror.
    """

    def setUp(self):
        super().setUp()
        self.Lead = self.env["mailbox.lead.generation"]
        self.Suggestion = self.env["mailbox.lead.suggestion"]

    def _create_lead(self, **vals):
        base = {"name": "Lead prueba sugerencias", "email_from": "tester@example.com"}
        base.update(vals)
        return self.Lead.create(base)

    # ------------------------------------------------------------------
    # Suggestion CRUD + computed ``record_ref``
    # ------------------------------------------------------------------
    def test_suggestion_record_ref_resolves_product_template(self):
        if "product.template" not in self.env:
            self.skipTest("product.template not installed in this DB")
        product = self.env["product.template"].create({"name": "Asesoría legal"})
        lead = self._create_lead()
        suggestion = self.Suggestion.create(
            {
                "lead_id": lead.id,
                "res_model": "product.template",
                "res_id": product.id,
                "match_type": "producto",
                "score": 0.42,
                "reason": "Producto coincidente por intent.",
            }
        )
        self.assertTrue(suggestion.id)
        self.assertTrue(suggestion.record_ref)
        self.assertEqual(suggestion.record_ref._name, "product.template")
        self.assertEqual(suggestion.record_ref.id, product.id)
        self.assertEqual(suggestion.match_type, "producto")
        self.assertAlmostEqual(suggestion.score, 0.42, places=2)
        self.assertEqual(suggestion.state, "suggested")

    def test_record_ref_false_for_unknown_model(self):
        lead = self._create_lead()
        suggestion = self.Suggestion.create(
            {
                "lead_id": lead.id,
                "res_model": "x.non.existent.model",
                "res_id": 1,
            }
        )
        self.assertFalse(suggestion.record_ref)

    # ------------------------------------------------------------------
    # One2many relation (lead.suggestion_ids) + cascade
    # ------------------------------------------------------------------
    def test_lead_suggestion_ids_one2many(self):
        lead = self._create_lead()
        s1 = self.Suggestion.create(
            {"lead_id": lead.id, "res_model": "product.template", "res_id": 1}
        )
        s2 = self.Suggestion.create(
            {"lead_id": lead.id, "res_model": "product.template", "res_id": 2}
        )
        self.assertEqual(len(lead.suggestion_ids), 2)
        self.assertIn(s1, lead.suggestion_ids)
        self.assertIn(s2, lead.suggestion_ids)
        # Default order is by score desc; both default 0.0 -> stable.
        self.assertEqual(lead.suggestion_ids._name, "mailbox.lead.suggestion")

    def test_lead_unlink_cascades_to_suggestions(self):
        lead = self._create_lead()
        suggestion = self.Suggestion.create(
            {"lead_id": lead.id, "res_model": "product.template", "res_id": 1}
        )
        lead.unlink()
        self.assertFalse(suggestion.exists())

    # ------------------------------------------------------------------
    # Source registry (_get_matching_sources)
    # ------------------------------------------------------------------
    def test_get_matching_sources_products_always(self):
        sources = self.Lead._get_matching_sources()
        keys = [key for key, _ in sources]
        self.assertIn("products", keys)
        self.assertIsInstance(sources, list)

    def test_get_matching_sources_real_estate_conditional(self):
        sources = self.Lead._get_matching_sources()
        keys = [key for key, _ in sources]
        if "product.real_estate" in self.env:
            self.assertIn("real_estate", keys)
        else:
            self.assertNotIn("real_estate", keys)

    # ------------------------------------------------------------------
    # _run_matching no-op scaffold
    # ------------------------------------------------------------------
    def test_run_matching_returns_empty_recordset(self):
        lead = self._create_lead()
        result = lead._run_matching()
        self.assertEqual(result._name, "mailbox.lead.suggestion")
        self.assertEqual(len(result), 0)

    # ------------------------------------------------------------------
    # Computed property_ids mirror (conditional bridge)
    # ------------------------------------------------------------------
    def test_property_ids_mirror_when_real_estate_installed(self):
        if "product.real_estate" not in self.env:
            self.skipTest("product.real_estate not installed in this DB")
        lead_model = self.env["mailbox.lead.generation"]
        if "property_ids" not in lead_model._fields:
            self.skipTest("real_estate_bridge not loaded (property_ids absent)")
        re_model = self.env["product.real_estate"]
        owner = self.env["res.partner"].create({"name": "Dueño espejo"})
        prop = re_model.create(
            {
                "name": "Depto prueba espejo",
                "propietario_id": owner.id,
                "operacion": "venta",
                "tipo_propiedad": "departamento",
            }
        )
        lead = self._create_lead()
        self.Suggestion.create(
            {
                "lead_id": lead.id,
                "res_model": "product.real_estate",
                "res_id": prop.id,
                "match_type": "propiedad",
            }
        )
        # Non real-estate suggestions must NOT pollute the mirror.
        if "product.template" in self.env:
            svc = self.env["product.template"].create({"name": "Servicio extra"})
            self.Suggestion.create(
                {
                    "lead_id": lead.id,
                    "res_model": "product.template",
                    "res_id": svc.id,
                    "match_type": "producto",
                }
            )
        self.assertIn(prop, lead.property_ids)
        self.assertEqual(len(lead.property_ids), 1)
