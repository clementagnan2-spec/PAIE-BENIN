# Paie Bénin

Logiciel de traitement de la paie mensuelle pour le Bénin, en Python /
Tkinter, compilable en exécutable Windows (`.exe`) via GitHub Actions ou
localement (`build_exe.bat`).

Projet frère de **Paie Togo** et **Paie Burkina** : même architecture
générale (6 onglets, authentification à deux niveaux, verrou d'expiration),
mais moteur de calcul entièrement réécrit pour respecter les règles
fiscales et sociales béninoises.

## Lancer en local

```bash
pip install -r requirements.txt
python main.py
```

## Compiler l'exécutable Windows

- **Localement (sous Windows)** : double-cliquer sur `build_exe.bat`.
- **Via GitHub Actions** : pousser un tag `vX.Y.Z` (ex: `v1.0.0`), ou
  déclencher manuellement le workflow "Compiler PaieBenin.exe" depuis
  l'onglet Actions du dépôt. L'exécutable est publié en artefact et, pour
  les tags, dans une Release GitHub.

## Règles de paie implémentées

Sources : fichier `ITS_VPS_CNSS_BENIN.xlsx` fourni par le client (feuilles
"Cal", "P1", "P2"), validé chiffre par chiffre (`payroll_engine.py`
reproduit exactement l'exemple à 658 000 F de brut → 118 900 F d'ITS).

### Retenues salariales (réduisent le Net à payer)

| Élément | Taux / Montant | Fréquence |
|---|---|---|
| CNSS Assurance Vieillesse (part salariale) | 3,6 % (fixe) | Chaque mois |
| TRTV (Taxe Radiophonique + Télévisuelle) | 4 000 F (1 000 + 3 000) | **Une fois par an, en avril uniquement** (paramétrable) |

Barème ITS (tranches appliquées au Brut fiscal) :

| Tranche | Taux |
|---|---|
| 0 – 60 000 | Exonéré |
| 60 001 – 150 000 | 10 % |
| 150 001 – 250 000 | 15 % |
| 250 001 – 500 000 | 19 % |
| 500 001 – 1 000 000 | 30 % |
| > 1 000 000 | 40 % |

### Charges patronales (n'affectent pas le Net à payer)

| Élément | Taux | Modifiable dans les Paramètres |
|---|---|---|
| CNSS Allocations Familiales | 9,00 % (fixe) | Non |
| CNSS Risques Professionnels | 1 % à 4 % | **Oui** (taux variable) |
| CNSS Assurance Vieillesse (part patronale) | 6,40 % (fixe) | Non |
| VPS (Versement Patronal sur Salaires) | 4 % standard / 2 % enseignement privé | **Oui** (taux variable) |
| ITS (Impôt sur les Traitements et Salaires) | Barème progressif : 0 % / 10 % / 15 % / 19 % / 30 % / 40 % | Non (barème fixe) |

**Note** : l'ITS est **100 % à la charge de l'employeur** — il n'affecte
PAS le Net à payer de l'employé (confirmé explicitement par le client).
Il s'affiche dans la colonne "Part Patronale" du bulletin, exactement
comme le VPS.

## Les 6 onglets

1. **Saisie des employés** — fiche employé + import/export Excel/CSV en masse
2. **Bulletins / État de paie** — calcul mensuel, export Excel, bulletins PDF (individuels ou groupés)
3. **Écritures comptables** — écriture en partie double (plan SYSCOHADA)
4. **Simulateur de bulletin** — retrouve le salaire de base à partir d'un Net souhaité
5. **Paramètres de paie** *(Administrateur)* — taux CNSS/VPS, montants TRTV, en-tête/pied de page PDF, logo
6. **Sécurité / Mots de passe** *(Administrateur)* — mot de passe Utilisateur mensuel, prolongation de licence

## Sécurité et licence (identique à Paie Togo)

- **Administrateur** : mot de passe fixe intégré au code (`auth.py`,
  `ADMIN_PASSWORD`), identique à Paie Togo/Burkina.
- **Utilisateur** : mot de passe qui change automatiquement chaque mois,
  dérivé par HMAC-SHA256 d'une clé secrète propre à chaque installation.
  Mot de passe initial connu : `userbenin741` (valable uniquement le mois
  de l'installation).
- **Expiration du build** : `expiration.py`, `BUILD_EXPIRATION_DATE`
  (actuellement 30/09/2026, comme Paie Togo). L'administrateur peut
  prolonger l'accès depuis l'onglet Sécurité.

## Bug connu (hérité de Paie Togo, à surveiller)

Si le fichier `donnees.json` est supprimé, le mot de passe Utilisateur par
défaut `userbenin741` redevient valable pour le mois en cours (comportement
volontaire pour faciliter la réinstallation, mais qui rouvre aussi l'accès
si quelqu'un supprime le fichier délibérément).

## À reconfirmer périodiquement

Les taux CNSS, le barème ITS et le taux VPS peuvent évoluer par la loi de
finances ou par décret de la CNSS/DGI du Bénin — à vérifier auprès des
administrations compétentes avant chaque nouvelle année fiscale.
