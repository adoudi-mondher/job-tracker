"""Jeu de test pour verification.check_programmatique (vérificateur LangGraph).

Cas synthétiques construits pour couvrir chaque règle + les bornes de longueur,
pas des LM réelles extraites de la base (pas d'accès à la base de prod depuis
cet environnement) — objectif : détecter une régression sur `regles_redaction.md`
ou sur `_check_programmatique` avant qu'elle parte en candidature réelle.
"""

from verification import check_programmatique

CLOSING = "Je suis disponible pour un échange."


def _lm(total_mots=280, extra=""):
    """Construit une LM factice de `total_mots` mots au total (extra + corps + closing)."""
    extra_mots = len(extra.split())
    closing_mots = len(CLOSING.split())
    n_filler = max(total_mots - extra_mots - closing_mots, 0)
    corps = " ".join(["mot"] * n_filler)
    parts = [p for p in [extra, corps] if p]
    return " ".join(parts) + ". " + CLOSING


def test_lm_conforme_sans_violation():
    assert check_programmatique(_lm()) == []


def test_tiret_em_detecte():
    motifs = check_programmatique(_lm(extra="Une phrase — avec tiret em."))
    assert any("Tiret em" in m for m in motifs)


def test_phrase_interdite_grand_interet():
    motifs = check_programmatique(_lm(extra="C'est avec grand intérêt que je postule."))
    assert any("Phrase interdite" in m for m in motifs)


def test_phrase_interdite_peu_de_profils():
    motifs = check_programmatique(_lm(extra="peu de profils similaires existent."))
    assert any("Phrase interdite" in m for m in motifs)


def test_micro_entreprise_rejetee_si_alternance():
    lm = _lm(extra="Le statut de micro-entreprise convient à cette mission.")
    motifs = check_programmatique(lm, type_contrat="alternance")
    assert any("micro-entreprise" in m for m in motifs)


def test_micro_entreprise_rejetee_si_non_precise():
    lm = _lm(extra="Le statut de micro-entreprise convient à cette mission.")
    motifs = check_programmatique(lm, type_contrat="non précisé")
    assert any("micro-entreprise" in m for m in motifs)


def test_micro_entreprise_rejetee_si_cdi():
    lm = _lm(extra="Le statut de micro-entreprise convient à cette mission.")
    motifs = check_programmatique(lm, type_contrat="CDI")
    assert any("micro-entreprise" in m for m in motifs)


def test_micro_entreprise_acceptee_si_freelance():
    lm = _lm(extra="Le statut de micro-entreprise convient à cette mission.")
    motifs = check_programmatique(lm, type_contrat="freelance")
    assert not any("micro-entreprise" in m for m in motifs)


def test_micro_entreprise_acceptee_si_cdi_et_freelance():
    lm = _lm(extra="Le statut de micro-entreprise convient à cette mission.")
    motifs = check_programmatique(lm, type_contrat="CDI et freelance")
    assert not any("micro-entreprise" in m for m in motifs)


def test_cesedaia_en_production_rejete():
    motifs = check_programmatique(_lm(extra="CesedaIA est aujourd'hui en production."))
    assert any("CesedaIA" in m for m in motifs)


def test_cesedaia_en_cours_accepte():
    motifs = check_programmatique(_lm(extra="CesedaIA est aujourd'hui en cours."))
    assert not any("CesedaIA" in m for m in motifs)


def test_msc_epitech_sans_date_rejete():
    motifs = check_programmatique(_lm(extra="Diplômé du MSc Epitech prochainement."))
    assert any("MSc Epitech" in m for m in motifs)


def test_msc_epitech_avec_date_accepte():
    motifs = check_programmatique(_lm(extra="Diplômé du MSc Epitech en octobre 2026."))
    assert not any("MSc Epitech" in m for m in motifs)


def test_trop_court_rejete():
    motifs = check_programmatique(_lm(total_mots=200))
    assert any("Trop court" in m for m in motifs)


def test_trop_long_rejete():
    motifs = check_programmatique(_lm(total_mots=400))
    assert any("Trop long" in m for m in motifs)


def test_borne_250_mots_ok():
    motifs = check_programmatique(_lm(total_mots=250))
    assert not any("Trop court" in m or "Trop long" in m for m in motifs)


def test_borne_320_mots_ok():
    motifs = check_programmatique(_lm(total_mots=320))
    assert not any("Trop court" in m or "Trop long" in m for m in motifs)


def test_borne_249_mots_rejete():
    motifs = check_programmatique(_lm(total_mots=249))
    assert any("Trop court" in m for m in motifs)


def test_borne_321_mots_rejete():
    motifs = check_programmatique(_lm(total_mots=321))
    assert any("Trop long" in m for m in motifs)


def test_closing_manquant_rejete():
    lm = " ".join(["mot"] * 280) + "."
    motifs = check_programmatique(lm)
    assert any("Closing manquant" in m for m in motifs)


def test_combinaison_plusieurs_violations():
    lm = _lm(total_mots=200, extra="Une phrase — avec tiret em et grand intérêt marqué.")
    motifs = check_programmatique(lm)
    assert any("Tiret em" in m for m in motifs)
    assert any("Trop court" in m for m in motifs)
    assert len(motifs) >= 2
