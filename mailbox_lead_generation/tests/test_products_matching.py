# pyright: reportMissingImports=false
# (odoo framework imports resolve only inside the Odoo runtime)
import logging

from odoo.tests import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestProductsMatching(TransactionCase):
    """Phase C3: product-catalog matching (``_match_products``).

    Exercises keyword extraction (accent normalization, the neutral
    ``item_category`` key with the legacy ``property_category`` fallback),
    candidate scoring against ``product.template`` of ANY type (goods
    ``consu`` and ``service`` products), top-N, and the ``_run_matching``
    routing for the service and purchase intents. Skipped when ``product``
    (``product.template``) is not installed.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pt_installed = "product.template" in cls.env
        if not cls.pt_installed:
            return
        cls.PT = cls.env["product.template"]
        cls.Lead = cls.env["mailbox.lead.generation"]
        cls.svc_legal = cls.PT.create(
            {"name": "Asesoría Legal Inmobiliaria", "type": "service"}
        )
        cls.svc_asesoria = cls.PT.create(
            {"name": "Asesoría Financiera", "type": "service"}
        )
        cls.svc_destacar = cls.PT.create(
            {"name": "Destacar Anuncio", "type": "service"}
        )
        # A goods (``consu``) product: matched too, since the engine is
        # product-type agnostic.
        cls.prod_bici = cls.PT.create(
            {"name": "Bicicleta Montaña Pro", "type": "consu"}
        )

    def _skip_if_no_pt(self):
        if not self.pt_installed:
            self.skipTest("product.template not installed")

    def test_extract_keywords_normalizes_accents(self):
        self._skip_if_no_pt()
        kw = self.Lead._prod_extract_keywords(
            {"clean_summary": "Asesoría legal rápida"}
        )
        self.assertIn("asesoria", kw)  # accent-stripped
        self.assertIn("legal", kw)
        self.assertIn("rapida", kw)  # accent-stripped from 'rápida'

    def test_extract_keywords_reads_item_category(self):
        self._skip_if_no_pt()
        kw = self.Lead._prod_extract_keywords({"item_category": "bicicleta"})
        self.assertIn("bicicleta", kw)
        # Legacy rows stored before 19.0.1.3.0 keep feeding keywords through
        # the old extraction key.
        kw_legacy = self.Lead._prod_extract_keywords(
            {"property_category": "bicicleta"}
        )
        self.assertIn("bicicleta", kw_legacy)

    def test_match_products_by_keyword_service_type(self):
        self._skip_if_no_pt()
        lead = self.Lead.create(
            {
                "name": "solicita asesoría legal",
                "ai_intent": "service",
                "ai_extracted": {
                    "clean_summary": "Cliente solicita asesoría legal inmobiliaria"
                },
            }
        )
        matches = lead._match_products("service", lead.ai_extracted or {})
        ids = [m["res_id"] for m in matches]
        self.assertIn(self.svc_legal.id, ids)
        # ranked score-descending
        self.assertEqual(
            matches, sorted(matches, key=lambda m: m["score"], reverse=True)
        )
        for m in matches:
            self.assertEqual(m["res_model"], "product.template")
            self.assertEqual(m["match_type"], "producto")
            self.assertTrue(0.0 <= m["score"] <= 1.0)

    def test_match_products_includes_goods_type(self):
        self._skip_if_no_pt()
        lead = self.Lead.create(
            {
                "name": "busca bicicleta",
                "ai_intent": "purchase",
                "ai_extracted": {"item_category": "bicicleta"},
            }
        )
        matches = lead._match_products("purchase", lead.ai_extracted or {})
        ids = [m["res_id"] for m in matches]
        # 'Bicicleta Montaña Pro' is type=consu -> matched (any product type).
        self.assertIn(self.prod_bici.id, ids)
        for m in matches:
            self.assertEqual(m["match_type"], "producto")

    def test_match_products_no_keywords_returns_empty(self):
        self._skip_if_no_pt()
        lead = self.Lead.create(
            {"name": "x", "ai_intent": "service", "ai_extracted": {}}
        )
        self.assertEqual(lead._match_products("service", {}), [])

    def test_run_matching_creates_product_suggestions(self):
        self._skip_if_no_pt()
        lead = self.Lead.create(
            {
                "name": "x",
                "ai_intent": "service",
                "ai_extracted": {"clean_summary": "quiero destacar anuncio"},
            }
        )
        lead._run_matching()
        self.assertTrue(lead.suggestion_ids)
        self.assertTrue(
            all(
                s.res_model == "product.template" and s.match_type == "producto"
                for s in lead.suggestion_ids
            )
        )
        self.assertIn(self.svc_destacar.id, lead.suggestion_ids.mapped("res_id"))

    def test_run_matching_purchase_intent_routes_to_products(self):
        self._skip_if_no_pt()
        lead = self.Lead.create(
            {
                "name": "busca bicicleta",
                "ai_intent": "purchase",
                "ai_extracted": {"item_category": "bicicleta"},
            }
        )
        lead._run_matching()
        product_suggestions = lead.suggestion_ids.filtered(
            lambda s: s.res_model == "product.template"
        )
        self.assertTrue(product_suggestions)
        self.assertIn(self.prod_bici.id, product_suggestions.mapped("res_id"))
        # When real_estate_products is installed, the deep bridge runs too and
        # contributes separate polymorphic rows (match_type 'propiedad').
        if "product.real_estate" in self.env:
            re_suggestions = lead.suggestion_ids.filtered(
                lambda s: s.res_model == "product.real_estate"
            )
            self.assertTrue(
                all(s.match_type == "propiedad" for s in re_suggestions)
            )

    def test_match_products_respects_top_n(self):
        self._skip_if_no_pt()
        for i in range(10):
            self.PT.create({"name": f"Asesoría Legal Variante {i}", "type": "service"})
        lead = self.Lead.create(
            {
                "name": "x",
                "ai_intent": "service",
                "ai_extracted": {"clean_summary": "asesoría legal"},
            }
        )
        matches = lead._match_products("service", lead.ai_extracted or {})
        self.assertLessEqual(len(matches), self.Lead._PRODUCTS_TOP_N)
