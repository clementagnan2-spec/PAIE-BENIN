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

# Identité de l'entreprise pré-remplie à l'installation (modifiable ensuite
# dans l'onglet « Paramètres de paie » par l'administrateur).
ENTREPRISE_NOM = "EGO BENIN SARL"
ENTREPRISE_IFU = "3202632850060"
ENTREPRISE_ADRESSE = "BP 04 Cotonou"

# Anciennes valeurs par défaut : si le fichier de données contient encore
# l'une d'elles (ou rien du tout), on la remplace par l'identité ci-dessus.
_PLACEHOLDERS = ("", "Mon Entreprise")


def get_data_dir() -> str:
    home = os.path.expanduser("~")
    path = os.path.join(home, APP_DIR_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def get_data_path() -> str:
    return os.path.join(get_data_dir(), DATA_FILE_NAME)


def _default_config() -> dict:
    return {
        "entreprise": ENTREPRISE_NOM,
        # En-tête / pied de page utilisés sur les bulletins de paie PDF,
        # modifiables par l'administrateur dans l'onglet Paramètres.
        "bulletin_entete": {
            "nom_entreprise": ENTREPRISE_NOM,
            "ifu": ENTREPRISE_IFU,
            "adresse": ENTREPRISE_ADRESSE,
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
    for k, v in default["bulletin_entete"].items():
        cfg["bulletin_entete"].setdefault(k, v)
    _prefill_entreprise(cfg)
    return cfg


def _prefill_entreprise(cfg: dict) -> None:
    """Pré-remplit le nom, l'IFU et l'adresse de l'entreprise sur les
    installations existantes où ces champs sont encore vides (ou contiennent
    l'ancien texte d'exemple « Mon Entreprise »). Une valeur déjà saisie par
    l'utilisateur n'est jamais écrasée."""
    entete = cfg["bulletin_entete"]
    changed = False
    if str(cfg.get("entreprise", "")).strip() in _PLACEHOLDERS:
        cfg["entreprise"] = ENTREPRISE_NOM
        changed = True
    if str(entete.get("nom_entreprise", "")).strip() in _PLACEHOLDERS:
        entete["nom_entreprise"] = ENTREPRISE_NOM
        changed = True
    if not str(entete.get("ifu", "")).strip():
        entete["ifu"] = ENTREPRISE_IFU
        changed = True
    if not str(entete.get("adresse", "")).strip():
        entete["adresse"] = ENTREPRISE_ADRESSE
        changed = True
    if changed:
        try:
            save(cfg)
        except Exception:
            # pas bloquant : les valeurs sont déjà correctes en mémoire
            pass


def save(config: dict) -> None:
    path = get_data_path()
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)
