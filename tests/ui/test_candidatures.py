import time

from playwright.sync_api import Page, expect


def test_ajout_candidature(authenticated_page: Page):
    page = authenticated_page
    suffix = str(int(time.time()))
    entreprise_nom = f"Entreprise Test {suffix}"
    poste = f"Testeur QA Automation {suffix}"

    # Le formulaire de candidature exige une entreprise existante (select) :
    # on la crée d'abord via son propre formulaire.
    page.goto("/entreprises/nouvelle")
    page.fill("input[name=nom]", entreprise_nom)
    page.click("button[type=submit]")
    expect(page.locator("h1")).to_have_text("Entreprises")

    page.goto("/candidatures/nouvelle")
    page.select_option("select[name=entreprise_id]", label=entreprise_nom)
    page.fill("input[name=poste]", poste)
    page.click("button[type=submit]")

    # Redirection vers la fiche détail de la candidature créée
    expect(page.locator("h1")).to_contain_text(poste)
