LM_TEMPLATE = """INSTRUCTIONS DE FORMAT STRICT :

Retourne UNIQUEMENT le corps de la lettre, en commençant OBLIGATOIREMENT par "Madame, Monsieur," et en terminant par "Cordialement,".

NE PAS inclure dans ta réponse :
- Les coordonnées du candidat (email, téléphone, LinkedIn, GitHub)
- L'adresse ou le nom de l'entreprise destinataire
- La date
- La ligne "Objet : ..."
- Le nom "Mondher Adoudi" en début ou fin de lettre
- La mention "MSc Développement Informatique / IA Epitech"
Ces éléments sont gérés automatiquement par le système d'export PDF.

STRUCTURE DES PARAGRAPHES (4 max) :
[§1 – Accroche : lien direct avec l'offre et le projet en cours chez l'entreprise]
[§2 – Compétences techniques et projets pertinents pour ce poste]
[§3 – Expérience Siemens et valeur ajoutée terrain]
[§4 – MSc Epitech oct. 2026, rythme majoritairement en entreprise ; mentionner MOSLTRANS si pertinent]

PHRASE DE CLÔTURE OBLIGATOIRE (avant "Cordialement,") :
"Je serais disponible pour échanger sur la manière dont mon profil peut s'intégrer à vos équipes."

FORMAT DE SORTIE ATTENDU :
Madame, Monsieur,

[§1]

[§2]

[§3]

[§4]

Je serais disponible pour échanger sur la manière dont mon profil peut s'intégrer à vos équipes.

Cordialement,
"""
