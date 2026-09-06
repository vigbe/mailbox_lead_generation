# pyright: reportMissingImports=false
# (odoo framework imports resolve only inside the Odoo runtime)
import logging

from odoo.tests import TransactionCase, tagged

_logger = logging.getLogger(__name__)

# NOTE: product.real_estate may declare additional required fields depending on
# the installed real_estate_products version. The fixtures below set the fields
# the matching engine reads; if create() raises on a missing required field at
# runtime, add that field here. These tests are skipped entirely when
# real_estate_products is not installed (the bridge is not loaded then).


@tagged("post_install", "-at_install")
class TestRealEstateMatching(TransactionCase):
    """Phase C2: real-estate retrieval engine (``_match_real_estate``).

    Exercises candidate filtering (operation / comuna / tipo / state exclusion),
    ranking, top-N, the routing of the neutral ``item_category`` extraction key
    into the tipo filter (with the legacy ``property_category`` fallback), and
    the end-to-end ``_run_matching`` -> suggestion creation flow, against real
    ``product.real_estate`` records.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.re_installed = "product.real_estate" in cls.env
        if not cls.re_installed:
            return
        cls.RE = cls.env["product.real_estate"]
        cls.Lead = cls.env["mailbox.lead.generation"]
        cls.owner = cls.env["res.partner"].create({"name": "Propietario Test"})

        def _prop(name, **kw):
            vals = {
                "name": name,
                "propietario_id": cls.owner.id,
                "operacion": "venta",
                "tipo_propiedad": "departamento",
                "comuna": "Las Condes",
                "habitaciones": 2,
                "state": "available",
                "active": True,
            }
            vals.update(kw)
            return cls.RE.create(vals)

        cls.prop_venta_lascondes_depto2 = _prop("Depto Las Condes 2d")
        cls.prop_venta_providencia_casa4 = _prop(
            "Casa Providencia 4d",
            tipo_propiedad="casa",
            comuna="Providencia",
            habitaciones=4,
        )
        cls.prop_arriendo_lascondes_depto3 = _prop(
            "Depto Las Condes 3d arriendo", operacion="arriendo", habitaciones=3
        )
        cls.prop_sold = _prop("Depto vendido", state="sold")

    def _skip_if_no_re(self):
        if not self.re_installed:
            self.skipTest("real_estate_products not installed")

    # ------------------------------------------------------------------
    # Pure helpers
    # ------------------------------------------------------------------
    def test_map_tipo_propiedad_synonyms(self):
        self._skip_if_no_re()
        m = self.Lead._re_map_tipo_propiedad
        self.assertEqual(m("departamento"), "departamento")
        self.assertEqual(m("Depto"), "departamento")
        self.assertEqual(m("CASA"), "casa")
        self.assertEqual(m("local"), "local_comercial")
        self.assertEqual(m("terreno"), "terreno")
        self.assertFalse(m("xyz_unknown"))

    def test_extract_bedrooms_aliases(self):
        self._skip_if_no_re()
        e = self.Lead._re_extract_bedrooms
        self.assertEqual(e({"bedrooms": 2}), 2)
        self.assertEqual(e({"dormitorios": "3"}), 3)
        self.assertIsNone(e({"rooms": "two"}))
        self.assertIsNone(e({}))

    def test_extract_budget(self):
        self._skip_if_no_re()
        e = self.Lead._re_extract_budget
        self.assertEqual(e({"budget": 300000000}), 300000000.0)
        self.assertEqual(e({"budget": "2000"}), 2000.0)
        self.assertIsNone(e({"budget": "UF 3000"}))
        self.assertIsNone(e({}))

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------
    def test_match_purchase_returns_ventas_in_comuna(self):
        self._skip_if_no_re()
        lead = self.Lead.create(
            {
                "name": "busco depto Las Condes",
                "ai_intent": "purchase",
                "ai_extracted": {
                    "location": "Las Condes",
                    "item_category": "departamento",
                },
            }
        )
        matches = lead._match_real_estate("purchase", lead.ai_extracted or {})
        ids = [m["res_id"] for m in matches]
        self.assertIn(self.prop_venta_lascondes_depto2.id, ids)
        # arriendo and sold must be excluded by operacion + state filters
        self.assertNotIn(self.prop_arriendo_lascondes_depto3.id, ids)
        self.assertNotIn(self.prop_sold.id, ids)
        # ranking is score-descending
        self.assertEqual(
            matches, sorted(matches, key=lambda m: m["score"], reverse=True)
        )
        # every returned row is a well-formed suggestion value
        for m in matches:
            self.assertEqual(m["res_model"], "product.real_estate")
            self.assertEqual(m["match_type"], "propiedad")
            self.assertTrue(0.0 <= m["score"] <= 1.0)

    def test_match_rent_filters_arriendo(self):
        self._skip_if_no_re()
        lead = self.Lead.create(
            {
                "name": "arriendo Las Condes",
                "ai_intent": "rent",
                "ai_extracted": {"location": "Las Condes"},
            }
        )
        matches = lead._match_real_estate("rent", lead.ai_extracted or {})
        ids = [m["res_id"] for m in matches]
        self.assertIn(self.prop_arriendo_lascondes_depto3.id, ids)
        self.assertNotIn(self.prop_venta_lascondes_depto2.id, ids)

    def test_match_respects_top_n(self):
        self._skip_if_no_re()
        for i in range(10):
            self.RE.create(
                {
                    "name": f"Extra depto Las Condes {i}",
                    "propietario_id": self.owner.id,
                    "operacion": "venta",
                    "tipo_propiedad": "departamento",
                    "comuna": "Las Condes",
                    "habitaciones": 2,
                    "state": "available",
                    "active": True,
                }
            )
        lead = self.Lead.create(
            {
                "name": "topn",
                "ai_intent": "purchase",
                "ai_extracted": {"location": "Las Condes"},
            }
        )
        matches = lead._match_real_estate("purchase", lead.ai_extracted or {})
        self.assertLessEqual(len(matches), self.Lead._RE_TOP_N)

    def test_run_matching_creates_suggestions(self):
        self._skip_if_no_re()
        lead = self.Lead.create(
            {
                "name": "e2e",
                "ai_intent": "purchase",
                "ai_extracted": {"location": "Las Condes"},
            }
        )
        lead._run_matching()
        self.assertTrue(lead.suggestion_ids)
        self.assertTrue(
            all(s.res_model == "product.real_estate" for s in lead.suggestion_ids)
        )
        # the suggested record is the property we created
        self.assertIn(
            self.prop_venta_lascondes_depto2.id,
            lead.suggestion_ids.mapped("res_id"),
        )

    # ------------------------------------------------------------------
    # item_category routing (neutral extraction key + legacy fallback)
    # ------------------------------------------------------------------
    def test_match_purchase_routes_item_category_to_tipo(self):
        self._skip_if_no_re()
        lead = self.Lead.create(
            {
                "name": "busco casa",
                "ai_intent": "purchase",
                "ai_extracted": {"item_category": "casa"},
            }
        )
        matches = lead._match_real_estate("purchase", lead.ai_extracted or {})
        ids = [m["res_id"] for m in matches]
        self.assertIn(self.prop_venta_providencia_casa4.id, ids)
        # Non-casa sale listings are excluded by the tipo filter routed
        # from the neutral ``item_category`` key.
        self.assertNotIn(self.prop_venta_lascondes_depto2.id, ids)

    def test_match_purchase_legacy_property_category_still_maps(self):
        self._skip_if_no_re()
        lead = self.Lead.create(
            {
                "name": "busco casa",
                "ai_intent": "purchase",
                "ai_extracted": {"property_category": "casa"},
            }
        )
        matches = lead._match_real_estate("purchase", lead.ai_extracted or {})
        ids = [m["res_id"] for m in matches]
        self.assertIn(self.prop_venta_providencia_casa4.id, ids)
        self.assertNotIn(self.prop_venta_lascondes_depto2.id, ids)
