-- ============================================================
-- Migration Job Tracker — Soft delete / archivage
-- À exécuter UNE SEULE FOIS en prod via psql
-- ============================================================

-- 1. Ajouter la colonne archived_at sur la table candidature
--    NULL = active, TIMESTAMP = archivée
ALTER TABLE candidature
    ADD COLUMN IF NOT EXISTS archived_at TIMESTAMP DEFAULT NULL;

-- 2. Fix bug secteur fantôme (entrées avec secteur = '' au lieu de NULL)
UPDATE entreprise
    SET secteur = NULL
    WHERE secteur = '';

-- ============================================================
-- Vérification post-migration
-- ============================================================

-- Doit retourner 0 (aucune candidature archivée pour l'instant)
SELECT COUNT(*) AS nb_archivees FROM candidature WHERE archived_at IS NOT NULL;

-- Doit retourner 0 (plus de secteurs vides)
SELECT COUNT(*) AS secteurs_vides FROM entreprise WHERE secteur = '';
