from playwright.sync_api import Page, expect


def test_login_valide(page: Page, app_password: str):
    page.goto("/login")
    page.fill("input[name=password]", app_password)
    page.click("button[type=submit]")
    expect(page.locator("h1")).to_have_text("Dashboard")


def test_login_invalide(page: Page):
    page.goto("/login")
    page.fill("input[name=password]", "mauvais-mot-de-passe")
    page.click("button[type=submit]")
    expect(page.locator(".alert-warning")).to_have_text("Mot de passe incorrect")
