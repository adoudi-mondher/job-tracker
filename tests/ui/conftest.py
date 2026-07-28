import os
import time

import pytest
from dotenv import load_dotenv
from playwright.sync_api import Page, expect

load_dotenv()


@pytest.fixture(scope="session")
def app_password() -> str:
    return os.environ["APP_PASSWORD"]


@pytest.fixture
def authenticated_page(page: Page, app_password: str) -> Page:
    page.goto("/login")
    page.fill("input[name=password]", app_password)
    page.click("button[type=submit]")
    expect(page.locator("h1")).to_have_text("Dashboard")
    return page


@pytest.fixture
def nouvelle_candidature(authenticated_page: Page) -> dict:
    """Crée une entreprise + une candidature uniques, laisse la page sur la fiche détail."""
    page = authenticated_page
    suffix = str(int(time.time() * 1000))
    entreprise_nom = f"Entreprise Test {suffix}"
    poste = f"Testeur QA Automation {suffix}"

    page.goto("/entreprises/nouvelle")
    page.fill("input[name=nom]", entreprise_nom)
    page.click("button[type=submit]")

    page.goto("/candidatures/nouvelle")
    page.select_option("select[name=entreprise_id]", label=entreprise_nom)
    page.fill("input[name=poste]", poste)
    page.click("button[type=submit]")
    expect(page.locator("h1")).to_contain_text(poste)

    return {"page": page, "poste": poste, "entreprise_nom": entreprise_nom}
