import unittest

from pipeline import sources
from pipeline.validation import valider

PROMOS = [{"id": 1, "promo": 2026, "nom": "A"}, {"id": 2, "promo": 2027, "nom": "B"}, {"id": 3, "promo": 2028, "nom": "C"}]


def pers(id, prenom, promo, parrain=None, nom="Test"):
    return {"id": id, "prenom": prenom, "nom": nom, "promo": promo, "parrain": parrain}


class TestValidation(unittest.TestCase):
    def test_donnees_saines(self):
        erreurs, avert = valider(PROMOS, [pers(1, "Anne", 2026), pers(2, "Bob", 2027, 1), pers(3, "Cleo", 2028, 2)])
        self.assertEqual(erreurs, [])
        self.assertEqual(avert, [])

    def test_cycle(self):
        erreurs, _ = valider(PROMOS, [pers(1, "Anne", 2026, 2), pers(2, "Bob", 2027, 1)])
        self.assertTrue(any(e.startswith("Cycle") for e in erreurs))

    def test_parrain_inconnu_et_texte(self):
        erreurs, _ = valider(PROMOS, [pers(1, "Anne", 2026, 99), pers(2, "Bob", 2027, "Jean Dupont (2026)")])
        self.assertEqual(sum("Parrain non reconnu" in e for e in erreurs), 2)

    def test_doublon_insensible_aux_accents(self):
        erreurs, _ = valider(PROMOS, [pers(1, "Clément", 2026), pers(2, "clement", 2026)])
        self.assertTrue(any("Doublon" in e for e in erreurs))

    def test_homonymes_de_promos_differentes(self):
        erreurs, _ = valider(PROMOS, [pers(1, "Manon", 2026), pers(2, "Manon", 2027)])
        self.assertEqual(erreurs, [])

    def test_parrain_plus_jeune(self):
        erreurs, _ = valider(PROMOS, [pers(1, "Anne", 2027, 2), pers(2, "Bob", 2027)])
        self.assertTrue(any("pas plus ancien" in e for e in erreurs))

    def test_ecart_et_trop_de_fillots(self):
        ps = [pers(1, "Anne", 2026)] + [pers(i, f"F{i}", 2027, 1) for i in range(2, 6)] + [pers(9, "Z", 2028, 1)]
        erreurs, avert = valider(PROMOS, ps)
        self.assertEqual(erreurs, [])
        self.assertTrue(any("5 fillots" in a for a in avert))
        self.assertTrue(any("Écart de 2 ans" in a for a in avert))

    def test_promo_inconnue(self):
        erreurs, _ = valider(PROMOS, [pers(1, "Anne", 2030)])
        self.assertTrue(any("Promo inconnue" in e for e in erreurs))

    def test_migration_valide(self):
        """Les fichiers d'import issus du Google Sheet passent la validation."""
        erreurs, _ = valider(*sources.lire_csv())
        self.assertEqual(erreurs, [])


if __name__ == "__main__":
    unittest.main()
