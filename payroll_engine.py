# -*- coding: utf-8 -*-
"""
payroll_engine.py
------------------
Reproduit fidèlement les formules du classeur Excel "ITS_VPS_CNSS_BENIN.xlsx"
(feuilles "Cal", "P1", "P2") fourni pour la paie béninoise :

  - CNSS :
      * Allocations Familiales (patronale)      : 9,00 % (fixe)
      * Risques Professionnels (patronale)       : taux PARAMÉTRABLE (1% à 4%
        selon l'activité de l'entreprise)
      * Assurance Vieillesse — part patronale    : 6,40 % (fixe)
      * Assurance Vieillesse — part salariale    : 3,60 % (fixe)
  - ITS (Impôt sur les Traitements et Salaires) : barème PROGRESSIF par
    tranches (0% / 10% / 15% / 19% / 30% / 40%), appliqué au Brut Fiscal.
    Affiché sur le bulletin dans la colonne "Part Patronale" (comme dans le
    classeur), mais RETENU SUR LE SALARIÉ (réduit le Net à payer) --
    confirmé explicitement par le client.
  - VPS (Versement Patronal sur Salaires) : taux PARAMÉTRABLE (4% par
    défaut, 2% pour les établissements d'enseignement privé). 100% à la
    charge de l'employeur, n'affecte jamais le Net à payer.
  - TRTV (Taxe Radiophonique + Taxe Télévisuelle) : redevance ANNUELLE de
    4 000 F (1 000 F radio + 3 000 F télé), retenue sur le salarié UNE SEULE
    FOIS PAR AN, uniquement sur le bulletin du mois d'avril.

Toutes les valeurs par défaut proviennent du fichier "ITS_VPS_CNSS_BENIN.xlsx"
fourni par le client (feuille "Cal"), confirmées par les exemples chiffrés
des feuilles "P1" et "P2". À reconfirmer périodiquement auprès de la CNSS
et de la DGI (Direction Générale des Impôts) du Bénin.
"""

import math
from dataclasses import dataclass, asdict, replace
from typing import Optional


# ---------------------------------------------------------------------------
# Paramètres par défaut (identiques à la feuille "Cal" du classeur fourni)
# ---------------------------------------------------------------------------

DEFAULT_PARAMS = {
    # 1. Cotisations CNSS
    "taux_cnss_allocations_familiales": 0.09,   # patronale, fixe
    "taux_cnss_risques_pro": 0.02,              # patronale, PARAMÉTRABLE (1% à 4%)
    "taux_cnss_vieillesse_patronal": 0.064,     # patronale, fixe
    "taux_cnss_vieillesse_salarial": 0.036,     # salariale, fixe

    # 2. VPS -- Versement Patronal sur Salaires
    "taux_vps": 0.04,                           # patronale, PARAMÉTRABLE (4% ou 2% ens. privé)

    # 3. ITS -- Impôt sur les Traitements et Salaires
    # Barème progressif : (borne_basse_incluse, borne_haute_incluse ou None, taux)
    "bareme_its": [
        (0, 60000, 0.0),
        (60000, 150000, 0.10),
        (150000, 250000, 0.15),
        (250000, 500000, 0.19),
        (500000, 1000000, 0.30),
        (1000000, None, 0.40),
    ],

    # 4. TRTV -- Taxe Radiophonique et Taxe Télévisuelle
    "trtv_radiophonique": 1000,
    "trtv_televisuelle": 3000,
    "trtv_mois_prelevement": 4,   # avril -- prélevée UNE SEULE FOIS PAR AN
}


@dataclass
class Employee:
    numero: int = 0
    nom_prenoms: str = ""
    direction: str = ""
    service: str = ""
    emploi: str = ""
    categorie: str = ""
    matricule_cnss: str = ""
    periode: str = ""                 # période de paie, format "AAAA-MM" (ex: "2026-09")
    salaire_base: float = 0.0
    heures_sup: float = 0.0
    primes: float = 0.0
    indemnite_transport: float = 0.0
    indemnite_logement: float = 0.0
    indemnite_communication: float = 0.0
    gratification: float = 0.0
    autres_primes: float = 0.0
    avance_acompte: float = 0.0
    retenue_pret: float = 0.0
    autres_retenues: float = 0.0
    date_saisie: str = ""             # date d'enregistrement dans le logiciel (audit), format ISO

    def to_dict(self):
        return asdict(self)


def _round(x, ndigits=0):
    """Reproduit ROUND() d'Excel (arrondi arithmétique, pas 'banker's rounding')."""
    if ndigits == 0:
        return math.floor(x + 0.5) if x >= 0 else math.ceil(x - 0.5)
    factor = 10 ** ndigits
    return _round(x * factor) / factor


def compute_its(base, bareme):
    """Calcule l'ITS de façon PROGRESSIVE par tranches, exactement comme la
    formule vérifiée dans la feuille "P2" du classeur fourni :
        (90 000 x 10%) + (100 000 x 15%) + (250 000 x 19%) + (158 000 x 30%)
    pour une base de 658 000 F. Chaque tranche du barème ne taxe que la
    portion de la base qui lui correspond (la première tranche à 0% joue
    le rôle d'abattement de 60 000 F)."""
    if base <= 0:
        return 0.0
    total = 0.0
    for (bas, haut, taux) in bareme:
        if base <= bas:
            break
        plafond_tranche = base if haut is None else min(base, haut)
        montant_tranche = plafond_tranche - bas
        if montant_tranche > 0:
            total += montant_tranche * taux
    return total


def compute_payslip(emp: Employee, params: dict, mois: int = None) -> dict:
    """Calcule un bulletin de paie complet pour un employé, selon les
    paramètres fournis (dict, même structure que DEFAULT_PARAMS).

    `mois` (1 à 12) détermine si la TRTV doit être prélevée ce mois-ci ;
    si non fourni, il est déduit de `emp.periode` (format "AAAA-MM")."""

    F = emp.salaire_base
    G = emp.heures_sup
    H = emp.primes
    I = emp.indemnite_transport
    J = emp.indemnite_logement
    K = emp.indemnite_communication
    L = emp.gratification
    M = emp.autres_primes

    # Total brut = Brut fiscal = Brut social (identique dans le classeur)
    O = F + G + H + I + J + K + L + M

    # --- Retenues salariales (réduisent le Net à payer) --------------------

    # CNSS Assurance Vieillesse -- part salariale (3,6%)
    P = _round(O * params["taux_cnss_vieillesse_salarial"])

    # ITS -- barème progressif sur le Brut fiscal
    Q = _round(compute_its(O, params["bareme_its"]))

    # TRTV -- uniquement sur le bulletin du mois de prélèvement (avril)
    if mois is None:
        try:
            mois = int(emp.periode.split("-")[1])
        except (AttributeError, IndexError, ValueError):
            mois = None
    trtv_due = (mois == params.get("trtv_mois_prelevement", 4))
    R = (params["trtv_radiophonique"] + params["trtv_televisuelle"]) if trtv_due else 0

    # Retenues diverses saisies (avance, prêt, autres)
    S = emp.avance_acompte
    T = emp.retenue_pret
    U = emp.autres_retenues

    total_retenues_salariales = P + Q + R + S + T + U

    # Net à payer
    net_a_payer = O - total_retenues_salariales

    # --- Charges patronales (n'affectent PAS le Net à payer) --------------

    AA = _round(O * params["taux_cnss_allocations_familiales"])
    AB = _round(O * params["taux_cnss_risques_pro"])
    AC = _round(O * params["taux_cnss_vieillesse_patronal"])
    AD = _round(O * params["taux_vps"])

    total_charges_patronales = AA + AB + AC + AD
    cout_total_employeur = O + total_charges_patronales

    # Totaux utiles pour les écritures comptables
    cnss_total = P + AA + AB + AC          # toutes cotisations CNSS (salariale + patronale)

    return {
        "numero": emp.numero,
        "nom_prenoms": emp.nom_prenoms,
        "direction": emp.direction,
        "service": emp.service,
        "emploi": emp.emploi,
        "categorie": emp.categorie,
        "matricule_cnss": emp.matricule_cnss,
        # Détail des éléments de gain
        "salaire_base": F,
        "heures_sup": G,
        "primes": H,
        "indemnite_transport": I,
        "indemnite_logement": J,
        "indemnite_communication": K,
        "gratification": L,
        "autres_primes": M,
        "total_brut": O,
        "brut_fiscal": O,
        "brut_social": O,
        # Retenues salariales
        "cnss_vieillesse_salariale": P,
        "its": Q,
        "trtv": R,
        "trtv_preleve_ce_mois": trtv_due,
        "avance_acompte": S,
        "retenue_pret": T,
        "autres_retenues": U,
        "total_retenues_salariales": total_retenues_salariales,
        "net_a_payer": net_a_payer,
        # Charges patronales
        "cnss_allocations_familiales": AA,
        "cnss_risques_pro": AB,
        "cnss_vieillesse_patronale": AC,
        "vps": AD,
        "total_charges_patronales": total_charges_patronales,
        "cout_total_employeur": cout_total_employeur,
        "cnss_total": cnss_total,
    }


def find_base_for_target_net(emp_template: Employee, params: dict, target_net: float,
                              mois: int = None, target_field: str = "net_a_payer",
                              lo: float = 0.0, hi: float = 5_000_000.0,
                              tol: float = 1.0, max_iter: int = 80):
    """Simulateur 'net -> base' : trouve, par dichotomie, le salaire de base
    (`salaire_base`) à appliquer à `emp_template` (les autres éléments —
    indemnités, primes... — restant fixes) pour que le résultat calculé
    (par défaut le Net à payer) atteigne `target_net`.

    S'appuie sur le fait que le Net à payer est une fonction croissante (au
    sens large) du salaire de base.

    Retourne (salaire_base_trouve, résultat_complet_compute_payslip)."""

    def net_for(base):
        e = replace(emp_template, salaire_base=base)
        r = compute_payslip(e, params, mois=mois)
        return r[target_field], r

    net_hi, result_hi = net_for(hi)
    tries = 0
    while net_hi < target_net and tries < 12:
        hi *= 2
        net_hi, result_hi = net_for(hi)
        tries += 1

    net_lo, result_lo = net_for(lo)
    if net_lo >= target_net:
        return lo, result_lo
    if net_hi < target_net:
        return hi, result_hi

    result = result_hi
    mid = hi
    for _ in range(max_iter):
        mid = (lo + hi) / 2
        net_mid, result = net_for(mid)
        if abs(net_mid - target_net) <= tol:
            break
        if net_mid < target_net:
            lo = mid
        else:
            hi = mid
    return mid, result
