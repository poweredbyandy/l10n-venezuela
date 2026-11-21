# Part of Odoo. See LICENSE file for full copyright and licensing details.
from lxml import etree

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestResPartnerRifView(TransactionCase):
    """Estructura de la vista de partner para el RIF venezolano.

    El RIF solo debe verse una vez en el titulo (h1) con el widget
    l10n_ve_rif, y el bloque de base_vat debe quedar oculto para contactos
    venezolanos.
    """

    def _combined_arch(self):
        return etree.fromstring(
            self.env.ref("base.view_partner_form").get_combined_arch()
        )

    def test_rif_field_in_title_uses_widget(self):
        arch = self._combined_arch()
        h1_vat = arch.xpath("//h1[field[@name='vat']]/field[@name='vat']")
        self.assertTrue(h1_vat, "el RIF debe estar en el titulo del formulario")
        self.assertEqual(h1_vat[0].get("widget"), "l10n_ve_rif")

    def test_base_vat_label_hidden_for_ve(self):
        arch = self._combined_arch()
        labels = arch.xpath("//label[@for='vat']")
        self.assertTrue(labels, "base_vat agrega su propio label para el vat")
        for label in labels:
            self.assertEqual(
                label.get("invisible"),
                "country_code == 'VE'",
                "el label de base_vat no debe duplicar el RIF en contactos VE",
            )

    def test_vies_container_holds_only_vat(self):
        """El contenedor VIES no debe tragarse los campos visibles de la suite."""
        arch = self._combined_arch()
        containers = arch.xpath("//div[@name='vat_vies_container']")
        self.assertEqual(len(containers), 1)
        visible_names = [
            child.get("name")
            for child in containers[0]
            if child.tag == "field"
            and child.get("name") != "vat"
            and child.get("invisible") != "1"
        ]
        self.assertEqual(
            visible_names,
            [],
            "el contenedor VIES no debe contener campos visibles de la suite; "
            "los helpers invisibles (ranks) se permiten",
        )
        self.assertTrue(
            arch.xpath("//div[@name='vat_vies_container']/following-sibling::field[@name='taxpayer_type']"),
            "taxpayer_type debe quedar en el group, fuera del contenedor VIES",
        )
