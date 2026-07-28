from playwright.sync_api import expect


def test_archivage_candidature(nouvelle_candidature: dict):
    page = nouvelle_candidature["page"]
    poste = nouvelle_candidature["poste"]

    # Le bouton "Archiver" déclenche un confirm() JS natif : il faut
    # l'accepter explicitement, sinon Playwright le rejette par défaut.
    page.on("dialog", lambda dialog: dialog.accept())
    page.click("button:has-text('Archiver')")

    # Retour sur la liste active : la candidature ne doit plus y apparaître
    expect(page.locator("h1")).to_have_text("Candidatures")
    expect(page.locator("table")).not_to_contain_text(poste)

    # Elle doit en revanche apparaître dans les archives
    page.goto("/candidatures/?archives=1")
    expect(page.locator("table")).to_contain_text(poste)
