# pyright: reportMissingImports=false
# (odoo framework imports resolve only inside the Odoo runtime)
import logging

from odoo.tests import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestServicesMatching(TransactionCase):
    """Phase C3: service-catalog matching (``_match_services``).

    Exercises keyword extraction (accent normalization), candidate scoring against
    ``product.template`` service products, type filtering, top-N, and the
    ``_run_matching`` routing for service intent. Skipped when ``product``
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
        # A non-service product that must NOT match under the type=service filter.
        cls.prod_fisico = cls.PT.create(
            {"name": "Asesoría Fisica Producto", "type": "consu"}
        )

    def _skip_if_no_pt(self):
        if not self.pt_installed:
            self.skipTest("product.template not installed")

    def test_extract_keywords_normalizes_accents(self):
        self._skip_if_no_pt()
        kw = self.Lead._svc_extract_keywords({"clean_summary": "Asesoría legal rápida"})
        self.assertIn("asesoria", kw)  # accent-stripped
        self.assertIn("legal", kw)
        self.assertIn("rapida", kw)  # accent-stripped from 'rápida'

    def test_match_services_by_keyword(self):
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
        matches = lead._match_services("service", lead.ai_extracted or {})
        ids = [m["res_id"] for m in matches]
        self.assertIn(self.svc_legal.id, ids)
        # ranked score-descending
        self.assertEqual(
            matches, sorted(matches, key=lambda m: m["score"], reverse=True)
        )
        for m in matches:
            self.assertEqual(m["res_model"], "product.template")
            self.assertEqual(m["match_type"], "servicio")
            self.assertTrue(0.0 <= m["score"] <= 1.0)

    def test_match_services_excludes_non_service_type(self):
        self._skip_if_no_pt()
        lead = self.Lead.create(
            {
                "name": "x",
                "ai_intent": "service",
                "ai_extracted": {"clean_summary": "asesoria fisica"},
            }
        )
        matches = lead._match_services("service", lead.ai_extracted or {})
        ids = [m["res_id"] for m in matches]
        # 'Asesoría Fisica Producto' is type=consu -> excluded by the filter.
        self.assertNotIn(self.prod_fisico.id, ids)

    def test_match_services_no_keywords_returns_empty(self):
        self._skip_if_no_pt()
        lead = self.Lead.create(
            {"name": "x", "ai_intent": "service", "ai_extracted": {}}
        )
        self.assertEqual(lead._match_services("service", {}), [])

    def test_run_matching_creates_service_suggestions(self):
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
            all(s.res_model == "product.template" for s in lead.suggestion_ids)
        )
        self.assertIn(self.svc_destacar.id, lead.suggestion_ids.mapped("res_id"))

    def test_match_services_respects_top_n(self):
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
        matches = lead._match_services("service", lead.ai_extracted or {})
        self.assertLessEqual(len(matches), self.Lead._SERVICES_TOP_N)
