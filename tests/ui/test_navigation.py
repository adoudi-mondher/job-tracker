import re

import pytest
from playwright.sync_api import Page, expect

# Chemins réels derrière les liens du menu principal (app/templates/base/layout.html)
LIENS_MENU = {
    "Dashboard": "/",
    "Candidatures": "/candidatures/",
    "Entreprises": "/entreprises/",
    "Découvrir": "/offres/",  # appelle une API externe (LBA) — un peu plus lent
    "France Travail": "/offres/france-travail",
}


@pytest.mark.parametrize("chemin", LIENS_MENU.values(), ids=LIENS_MENU.keys())
def test_lien_menu_ne_404_pas(authenticated_page: Page, chemin):
    response = authenticated_page.goto(chemin)
    assert response.status == 200


def test_lien_rapport_ouvre_nouvel_onglet(authenticated_page: Page):
    page = authenticated_page

    # "Rapport" a target="_blank" : la navigation se fait dans un nouvel onglet
    with page.context.expect_page() as popup_info:
        page.click("a[target='_blank']:has-text('Rapport')")
    rapport_page = popup_info.value
    rapport_page.wait_for_load_state()

    expect(rapport_page).to_have_url(re.compile(r"/rapport$"))
