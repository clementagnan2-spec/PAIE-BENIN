# -*- coding: utf-8 -*-
"""
expiration.py
--------------
Verrou de date d'expiration du logiciel.

BUILD_EXPIRATION_DATE est une date FIGÉE dans le code, intégrée au .exe à
la compilation. Après cette date, le logiciel refuse totalement de démarrer
(blocage avant même l'écran de connexion) -- quel que soit l'état du
fichier de données local.

L'administrateur peut prolonger l'accès depuis l'onglet Sécurité : la
nouvelle date choisie est enregistrée dans le fichier de données local
(config["access_extended_until"]). La date EFFECTIVE utilisée est toujours
la PLUS TARDIVE entre BUILD_EXPIRATION_DATE et cette prolongation.

Conséquence volontaire : si quelqu'un supprime le fichier de données pour
tenter de "réinitialiser" quelque chose, il perd du même coup toute
prolongation accordée -- l'expiration retombe sur BUILD_EXPIRATION_DATE,
qui ne peut donc jamais avantager qui que ce soit, seulement pénaliser.

Pour publier un nouveau build (ex: reconduire un abonnement client) :
modifier BUILD_EXPIRATION_DATE ci-dessous, puis recompiler et redistribuer
un nouveau .exe.
"""

import datetime

# ---------------------------------------------------------------------------
# À modifier avant chaque nouvelle compilation destinée à repousser
# l'échéance (ex: renouvellement mensuel d'un abonnement).
# ---------------------------------------------------------------------------
BUILD_EXPIRATION_DATE = datetime.date(2026, 9, 30)


def get_effective_expiration(config: dict) -> datetime.date:
    """Renvoie la date d'expiration effective : la plus tardive entre la
    date figée dans le code et une éventuelle prolongation enregistrée par
    l'administrateur dans le fichier de données local."""
    dates = [BUILD_EXPIRATION_DATE]
    override = config.get("access_extended_until")
    if override:
        try:
            dates.append(datetime.date.fromisoformat(override))
        except ValueError:
            pass
    return max(dates)


def is_expired(config: dict, today: datetime.date = None) -> bool:
    today = today or datetime.date.today()
    return today > get_effective_expiration(config)


def set_extension(config: dict, new_date: datetime.date) -> None:
    """Enregistre une prolongation. Toujours autorisé même si new_date est
    dans le passé ou antérieure à la date déjà stockée -- get_effective_expiration
    prend de toute façon le maximum, donc une prolongation "vers le bas" n'a
    simplement aucun effet réel."""
    config["access_extended_until"] = new_date.isoformat()
