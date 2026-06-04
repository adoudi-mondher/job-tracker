-- ============================================================
-- Migration Job Tracker — Intégration n8n
-- À exécuter UNE SEULE FOIS en prod via psql
-- Compatibilité SQLite : ALTER TABLE ADD COLUMN supporté
-- ============================================================

-- 1. Champ source : origine de la candidature
--    "manual" = saisie UI | "auto" = scraping n8n | "lba" = La Bonne Alternance
ALTER TABLE candidature
    ADD COLUMN IF NOT EXISTS source VARCHAR(50) NOT NULL DEFAULT 'manual';

-- 2. Stack technique extraite depuis l'URL de l'offre (W2 — enrichissement auto)
ALTER TABLE candidature
    ADD COLUMN IF NOT EXISTS stack_technique TEXT DEFAULT NULL;

-- 3. Résumé de l'offre en 3 lignes (W2 — enrichissement auto)
ALTER TABLE candidature
    ADD COLUMN IF NOT EXISTS resume_offre TEXT DEFAULT NULL;

-- 4. Brouillon de lettre de motivation généré par Claude (W3)
ALTER TABLE candidature
    ADD COLUMN IF NOT EXISTS lettre_motivation TEXT DEFAULT NULL;

-- ============================================================
-- Vérification post-migration
-- ============================================================

-- Doit retourner les colonnes ajoutées (PostgreSQL uniquement)
-- SELECT column_name, data_type, column_default
-- FROM information_schema.columns
-- WHERE table_name = 'candidature'
--   AND column_name IN ('source', 'stack_technique', 'resume_offre', 'lettre_motivation');

-- Toutes les candidatures existantes doivent avoir source = 'manual'
SELECT COUNT(*) AS candidatures_manual FROM candidature WHERE source = 'manual';
