from playwright.sync_api import expect


def test_filtre_par_statut(nouvelle_candidature: dict):
    # Une candidature fraîchement créée a le statut par défaut "À envoyer"
    page = nouvelle_candidature["page"]
    poste = nouvelle_candidature["poste"]

    page.goto("/candidatures/")

    # Filtre sur un autre statut : la candidature ne doit pas apparaître.
    # On vérifie sur <body> (pas <table>) car si aucune candidature ne matche,
    # le template affiche un .empty-state à la place du tableau.
    page.click("a.filter-btn:has-text('Entretien')")
    expect(page.locator("body")).not_to_contain_text(poste)

    # Filtre sur son propre statut : elle doit réapparaître
    page.click("a.filter-btn:has-text('À envoyer')")
    expect(page.locator("table")).to_contain_text(poste)
