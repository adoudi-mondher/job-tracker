# Plan QA — Playwright + Jira (Job Tracker)

> À exploiter en session de travail dédiée. Objectif : case à cocher CV/entretien QA, pas de sur-ingénierie.

---

## Contexte / objectif

Positionnement QA logiciel en plus de MOA/PO et Dev. Besoin d'une référence concrète et vécue sur :
- Un outil de test **UI** : **Playwright** (Python) sur **Job Tracker** (Flask/HTMX) — cohérent avec la stack existante du projet
- **Jira** (suivi de bugs/tickets)

**Discours entretien :** *"J'ai pratiqué Playwright en Python sur Job Tracker, un projet Flask/HTMX en production, avec un suivi structuré des anomalies sous Jira."*

---

## Partie 1 — Playwright (tests UI)

### Pourquoi Playwright plutôt que Selenium
- Setup auto (pas de driver navigateur à gérer manuellement)
- Attentes automatiques intégrées (pas de `WebDriverWait` verbeux)
- Reconnu et de plus en plus standard sur le marché
- Python natif, cohérent avec la stack existante

**Discours entretien :** connaître les deux logiques, avoir choisi Playwright pour sa simplicité = recul et veille technique (bon réflexe QA).

### Installation

```bash
pip install pytest-playwright --break-system-packages
playwright install
```

### Structure de dossier suggérée

```
job-tracker/
  tests/
    ui/
      test_auth.py
      test_offres.py
      conftest.py
```

### 5-8 scénarios UI à couvrir (Job Tracker)

1. **Connexion / authentification**
   - Login avec identifiants valides → redirection dashboard
   - Login avec identifiants invalides → message d'erreur affiché

2. **Ajout d'une offre**
   - Remplir formulaire (entreprise, poste, lien) → soumettre
   - Vérifier que l'offre apparaît dans la liste

3. **Archivage / soft delete**
   - Sélectionner une offre → bouton archiver
   - Vérifier qu'elle disparaît de la liste active
   - Vérifier qu'elle apparaît dans la liste archivée

4. **Recherche / filtre**
   - Filtrer par statut (candidature envoyée, entretien, etc.)
   - Vérifier que seules les offres correspondantes s'affichent

5. **Navigation générale**
   - Vérifier que les liens principaux du menu fonctionnent (pas de 404)

### Exemple de test (squelette, à adapter)

```python
# tests/ui/test_auth.py
from playwright.sync_api import Page, expect

def test_login_valide(page: Page):
    page.goto("https://jobs.mondher.ch/login")
    page.fill("#email", "adoudi@mondher.ch")
    page.fill("#password", "xxxxx")
    page.click("button[type=submit]")
    expect(page).to_have_url("https://jobs.mondher.ch/dashboard")

def test_login_invalide(page: Page):
    page.goto("https://jobs.mondher.ch/login")
    page.fill("#email", "faux@mondher.ch")
    page.fill("#password", "wrong")
    page.click("button[type=submit]")
    expect(page.locator(".error-message")).to_be_visible()
```

### Commande d'exécution

```bash
pytest tests/ui/ --headed   # mode visuel pour debug
pytest tests/ui/            # mode headless pour CI
```

### Étape optionnelle (si temps disponible)
- Ajouter un job CI GitHub Actions qui lance les tests Playwright à chaque push
- Rapport HTML : `pytest --html=report.html`

---

## Partie 2 — Jira (suivi de bugs)

### Usage réaliste et honnête
Jira n'est pas un outil de test — c'est un outil de suivi. Usage légitime : board personnel gratuit pour suivre les anomalies de Job Tracker.

### Mise en place

1. Créer un compte Jira Cloud gratuit (atlassian.com)
2. Créer un projet type "Kanban" : `QA-JobTracker`
3. Colonnes : **À trier → À corriger → En cours → Vérifié → Fermé**

### Structure des tickets

Chaque ticket bug doit contenir :
- **Titre** court et descriptif
- **Sévérité** (Bloquant / Majeur / Mineur / Cosmétique)
- **Étapes de reproduction**
- **Résultat attendu vs résultat observé**
- **Lien vers le test Playwright concerné** (si applicable)

### Exemples de tickets à créer (réels, basés sur Job Tracker)

| Titre | Sévérité | Origine |
|---|---|---|
| Erreur 500 si champ "entreprise" vide | Majeur | Job Tracker |
| Offre archivée réapparaît après refresh | Mineur | Job Tracker |
| Timeout sur enrichissement URL via n8n | Majeur | Job Tracker |

**Discours entretien :** *"J'ai structuré mon suivi de bugs sous Jira avec des tickets classés par sévérité, en lien avec mes tests automatisés Playwright."*

---

## Placement CV / aboutme / LM

| Élément | Où | Formulation |
|---|---|---|
| Playwright | CV — Compétences (ligne Tests/QA) | "Playwright (tests UI, Python)" |
| Jira | CV — Compétences (Conception & Produit ou nouvelle ligne QA) | "Jira (suivi anomalies)" |
| Les deux | aboutme.md — section Stack technique + Cibles QA | Détail usage réel sur Job Tracker (Playwright + Jira) |
| Les deux | LM (offres QA uniquement) | *"J'ai mis en place des tests UI automatisés (Playwright) et un suivi structuré des anomalies (Jira) sur mon application Job Tracker en production."* |

Règle d'honnêteté : ne présenter ces outils que **après** avoir réellement écrit les tests et créé le board — pas avant.

Si une offre spécifique insiste sur Selenium, Cypress ou un outil non pratiqué : nommer le gap honnêtement dans la LM plutôt que d'improviser une compétence non pratiquée (cf. règle gaps techniques d'aboutme.md).

---

## Checklist d'exécution (session dédiée)

### Volet Playwright / Job Tracker
- [ ] `pip install pytest-playwright` + `playwright install`
- [ ] Écrire 5-8 tests UI sur Job Tracker
- [ ] Faire tourner les tests, vérifier qu'ils passent

### Jira
- [ ] Créer compte Jira Cloud + board `QA-JobTracker`
- [ ] Créer tickets réels basés sur bugs déjà rencontrés sur Job Tracker

### Documents
- [ ] Mettre à jour CV (ligne Compétences : Playwright + Jira)
- [ ] Mettre à jour aboutme.md (section Stack + Cibles QA)
- [ ] Ajouter mention ISTQB (en préparation) au même endroit
