# Suivi du projet Paie Bénin

## Contexte

Projet créé "de zéro" (pas de copie du code de Paie Togo/Burkina), mais en
reproduisant la même architecture et les mêmes 6 onglets, à la demande
explicite du client. Le moteur de calcul (`payroll_engine.py`) a été écrit
entièrement à partir du fichier `ITS_VPS_CNSS_BENIN.xlsx` fourni par le
client (feuilles "Cal", "P1", "P2"), et validé chiffre par chiffre contre
les deux exemples du classeur.

## Décisions prises avec le client (à date de création du projet)

1. **ITS = charge 100% patronale** (décision finale, après une première
   clarification erronée où l'ITS avait été implémenté comme retenue
   salariale — corrigée le jour même sur retour du client, capture d'écran
   à l'appui : Net à payer attendu = 634 312 F pour un brut de 658 000 F,
   soit brut − CNSS salariale UNIQUEMENT). L'ITS reste affiché dans la
   colonne "Part Patronale" du bulletin (fidèle au classeur Excel) et
   compte dans le coût total employeur et les écritures comptables
   (comptes 664500 / 447210), mais n'affecte JAMAIS le Net à payer.
2. **TRTV (4 000 F)** : retenue sur le salarié, mais **une seule fois par
   an, uniquement sur le bulletin du mois d'avril** — pas une retenue
   mensuelle. Le mois de prélèvement est paramétrable (`trtv_mois_prelevement`,
   défaut = 4).
3. **VPS** : 100 % charge patronale, n'affecte jamais le Net à payer.
4. **Taux CNSS Risques Professionnels (1% à 4%)** et **Taux VPS (4%/2%)** :
   tous deux laissés en **taux variables/paramétrables** dans l'onglet
   Paramètres de paie (pas de logique automatique de bascule liée au
   secteur d'activité — l'administrateur saisit directement le taux
   applicable à son entreprise).
5. **Mot de passe Administrateur** : identique à Paie Togo/Burkina
   (`ouaga2001@@@`).
6. **Date d'expiration du premier build** : identique à Paie Togo
   (30/09/2026).

## Points non couverts / à clarifier si besoin plus tard

- Le fichier Excel source mentionne un champ "Parts IGR" (informationnel,
  non utilisé dans les formules confirmées) — non repris dans
  `payroll_engine.py`. À ajouter si le client confirme une règle de calcul
  liée aux parts fiscales/charges de famille pour l'ITS.
- Le champ "Catégorie" du bulletin (visible dans le classeur, valeur "-"
  dans les exemples) est repris comme simple champ informatif sur la fiche
  employé, sans impact sur le calcul.
- Pas de distinction "Gérant / Employé" comme dans Paie Togo — rien dans le
  fichier Excel béninois ne suggère une telle distinction pour l'ITS.
- La bascule automatique VPS 4%→2% "si enseignement privé" n'a PAS été
  implémentée comme case à cocher : le client a demandé un simple champ de
  taux libre à la place (voir décision n°4 ci-dessus).

## Bug hérité de Paie Togo (volontairement conservé)

Suppression de `donnees.json` → le mot de passe Utilisateur par défaut
`userbenin741` redevient valable pour le mois en cours. Comportement
identique à Paie Togo, non corrigé sauf demande explicite du client.

## Prochaines étapes possibles

- Tests avec des cas réels de paie béninoise supplémentaires (autres
  tranches ITS, TRTV en avril avec import Excel, etc.)
- Décider si le champ "Catégorie"/"Parts IGR" doit influencer le calcul
- Ajouter un logo par défaut / une charte graphique béninoise si souhaité
