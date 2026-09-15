# -*- coding: utf-8 -*-
"""
storage.py
----------
Sauvegarde locale des données (paramètres, employés, comptes) dans un
fichier JSON situé dans le dossier utilisateur -- pas à côté du .exe, pour
que ça fonctionne même si le logiciel est installé dans "Program Files"
(dossier en lecture seule pour un utilisateur normal).

Emplacement Windows typique :
    C:\\Users\\<utilisateur>\\PaieBeninData\\donnees.json
"""

import json
import os
import copy

from payroll_engine import DEFAULT_PARAMS
import auth

APP_DIR_NAME = "PaieBeninData"
DATA_FILE_NAME = "donnees.json"


def get_data_dir() -> str:
    home = os.path.expanduser("~")
    path = os.path.join(home, APP_DIR_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def get_data_path() -> str:
    return os.path.join(get_data_dir(), DATA_FILE_NAME)


def _default_config() -> dict:
    return {
        "entreprise": "Mon Entreprise",
        # En-tête / pied de page utilisés sur les bulletins de paie PDF,
        # modifiables par l'administrateur dans l'onglet Paramètres.
        "bulletin_entete": {
            "nom_entreprise": "Mon Entreprise",
            "adresse": "",
            "telephone": "",
            "email": "",
            "note_entete": "",
        },
        "bulletin_pied_de_page": (
            "Pour vous aider à faire valoir vos droits, conservez ce "
            "bulletin de paie sans limitation de durée. Ce bulletin est "
            "établi conformément à la législation du travail en vigueur "
            "au Bénin."
        ),
        # Mot de passe Administrateur : FIXE, intégré au code (voir
        # auth.ADMIN_PASSWORD) -- plus stocké ici du tout.
        # Prolongation de la date d'expiration (voir expiration.py). None =
        # aucune prolongation accordée, seule la date figée dans le code fait foi.
        "access_extended_until": None,
        # Clé propre à CETTE installation, générée aléatoirement une seule
        # fois. Volontairement différente d'un poste à l'autre : ça évite
        # qu'un mot de passe Utilisateur valable sur une installation
        # fonctionne aussi sur une autre (anti-partage entre postes/clients).
        "secret_key": auth.new_secret_key(),
        # Mot de passe Utilisateur par défaut CONNU ("userbenin741"), valable
        # uniquement pour la période de validité en cours au moment de
        # l'installation. Pratique pour l'installation à distance : pas
        # besoin de se connecter en admin juste pour lire le premier mot
        # de passe. Dès que cette période se termine, plus aucun mot de
        # passe forcé n'existe pour la nouvelle période : le logiciel
        # repasse automatiquement sur la génération habituelle (dérivée de
        # la clé secrète ci-dessus).
        "user_password_overrides": {auth.current_period(): "userbenin741"},
        "params": copy.deepcopy(DEFAULT_PARAMS),
        "employees": [],
        "next_numero": 1,
    }


def load() -> dict:
    path = get_data_path()
    if not os.path.exists(path):
        cfg = _default_config()
        save(cfg)
        return cfg
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    # complète les clés manquantes si le fichier vient d'une version antérieure
    default = _default_config()
    for k, v in default.items():
        cfg.setdefault(k, v)
    for k, v in DEFAULT_PARAMS.items():
        cfg["params"].setdefault(k, v)
    return cfg


def save(config: dict) -> None:
    path = get_data_path()
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)
