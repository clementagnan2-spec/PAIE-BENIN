# -*- coding: utf-8 -*-
"""
main.py
-------
Application de traitement de la paie mensuelle -- Bénin.

Deux niveaux d'accès :
  - Administrateur : mot de passe fixe, accès aux paramètres de paie et au
    mot de passe Utilisateur.
  - Utilisateur : mot de passe qui change automatiquement chaque mois,
    accès à la saisie des employés et au calcul de la paie.

Lancer avec :  python main.py
"""

import datetime
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from dataclasses import replace

import auth
import storage
import expiration
from payroll_engine import Employee, compute_payslip, find_base_for_target_net, DEFAULT_PARAMS

APP_TITLE = "Paie Bénin — Traitement des salaires mensuels"
PAID_SOFTWARE_NOTICE = "Ce logiciel de paie est payant : consultanter280@gmail.com"

MOIS_FR = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet",
           "Août", "Septembre", "Octobre", "Novembre", "Décembre"]


def current_period_key():
    today = datetime.date.today()
    return f"{today.year:04d}-{today.month:02d}"


def normalize_period(text, default=None):
    """Accepte 'MM/AAAA', 'AAAA-MM', 'MM-AAAA', 'AAAA/MM', ou une date Excel,
    et renvoie 'AAAA-MM'. Renvoie `default` (ou la période en cours) si le
    texte est vide/invalide."""
    default = default or current_period_key()
    if isinstance(text, (datetime.date, datetime.datetime)):
        return f"{text.year:04d}-{text.month:02d}"
    text = (text or "").strip()
    if not text:
        return default
    parts = text.replace("/", "-").split("-")
    if len(parts) != 2:
        return default
    a, b = parts
    try:
        if len(a) == 4:
            year, month = int(a), int(b)
        else:
            month, year = int(a), int(b)
        if not (1 <= month <= 12):
            return default
        return f"{year:04d}-{month:02d}"
    except ValueError:
        return default


def format_period(period_key):
    try:
        year, month = period_key.split("-")
        return f"{MOIS_FR[int(month) - 1]} {year}"
    except Exception:
        return period_key or ""


def fmt_amount(v):
    """Formate un montant avec espace comme séparateur de milliers et sans
    décimales inutiles (150000.0 -> '150 000'). Les valeurs non numériques
    (texte, None...) sont renvoyées telles quelles."""
    if v is None or v == "":
        return ""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return v
    return f"{f:,.0f}".replace(",", " ")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1250x720")
        self.minsize(1000, 620)
        try:
            self.state("zoomed")  # démarre en fenêtre maximisée sous Windows
        except tk.TclError:
            pass

        # IMPORTANT : sans ceci, toute erreur inattendue survenant dans un
        # bouton/callback Tkinter est silencieuse (surtout dans un .exe
        # compilé en mode "fenêtre", sans console) -- l'utilisateur voit
        # juste "rien ne se passe". On l'affiche désormais dans une boîte
        # de dialogue explicite, avec le détail technique, pour pouvoir
        # diagnostiquer immédiatement.
        self.report_callback_exception = self._show_error

        try:
            self.config_data = storage.load()
        except Exception as exc:
            messagebox.showerror(
                "Erreur au démarrage",
                "Impossible de charger/créer le fichier de données local.\n\n"
                f"Détail technique : {exc}\n\n"
                "Vérifiez que l'application a le droit d'écrire dans votre "
                "dossier utilisateur (essayez de la lancer en tant "
                "qu'administrateur, ou vérifiez qu'un antivirus ne la bloque pas).")
            raise
        self.role = None  # "admin" ou "user"

        self.container = ttk.Frame(self)
        self.container.pack(fill="both", expand=True)

        if expiration.is_expired(self.config_data):
            self.show_expired()
        else:
            self.show_login()

    def show_expired(self):
        self.role = None
        self.clear()
        ExpiredScreen(self.container, self)

    def _show_error(self, exc_type, exc_value, exc_tb):
        import traceback
        detail = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        messagebox.showerror(
            "Erreur inattendue",
            f"Une erreur s'est produite :\n\n{exc_value}\n\n"
            "Détail technique (à transmettre au support si le problème persiste) :\n"
            f"{detail[-1200:]}")

    # ------------------------------------------------------------------
    def clear(self):
        for w in self.container.winfo_children():
            w.destroy()

    def show_login(self):
        self.role = None
        self.clear()
        LoginScreen(self.container, self)

    def show_main(self):
        self.clear()
        MainScreen(self.container, self)


# ==========================================================================
# ÉCRAN DE BLOCAGE (logiciel expiré)
# ==========================================================================

class ExpiredScreen(ttk.Frame):
    def __init__(self, parent, app: App):
        super().__init__(parent)
        self.app = app
        self.pack(fill="both", expand=True)

        banner = tk.Label(self, text=PAID_SOFTWARE_NOTICE, fg="white", bg="#008751",
                           font=("Segoe UI", 10, "bold"), pady=8)
        banner.pack(fill="x", side="top")

        center = ttk.Frame(self)
        center.pack(expand=True)

        expiration_date = expiration.get_effective_expiration(app.config_data)

        ttk.Label(center, text="⛔", font=("Segoe UI", 40)).pack(pady=(40, 6))
        ttk.Label(center, text="Accès expiré", font=("Segoe UI", 20, "bold")).pack(pady=(0, 10))
        ttk.Label(
            center,
            text=f"Ce logiciel n'est plus valide depuis le "
                 f"{expiration_date.strftime('%d/%m/%Y')}.",
            font=("Segoe UI", 11), justify="center").pack(pady=(0, 6))
        ttk.Label(
            center,
            text="Merci de contacter l'administrateur pour renouveler l'accès :",
            font=("Segoe UI", 10), justify="center", foreground="#555").pack(pady=(6, 2))
        ttk.Label(center, text="consultanter280@gmail.com",
                  font=("Segoe UI", 11, "bold")).pack()


# ==========================================================================
# ÉCRAN DE CONNEXION
# ==========================================================================

class LoginScreen(ttk.Frame):
    def __init__(self, parent, app: App):
        super().__init__(parent)
        self.app = app
        self.pack(fill="both", expand=True)

        banner = tk.Label(self, text=PAID_SOFTWARE_NOTICE, fg="white", bg="#008751",
                           font=("Segoe UI", 10, "bold"), pady=8)
        banner.pack(fill="x", side="top")

        center = ttk.Frame(self)
        center.pack(expand=True)

        ttk.Label(center, text="Paie Bénin", font=("Segoe UI", 22, "bold")).pack(pady=(40, 4))
        ttk.Label(center, text="Traitement des salaires mensuels",
                  font=("Segoe UI", 11)).pack(pady=(0, 24))

        form = ttk.Frame(center)
        form.pack()

        ttk.Label(form, text="Rôle :").grid(row=0, column=0, sticky="e", padx=6, pady=6)
        self.role_var = tk.StringVar(value="Utilisateur")
        role_combo = ttk.Combobox(form, textvariable=self.role_var,
                                   values=["Utilisateur", "Administrateur"],
                                   state="readonly", width=20)
        role_combo.grid(row=0, column=1, sticky="w", padx=6, pady=6)

        ttk.Label(form, text="Mot de passe :").grid(row=1, column=0, sticky="e", padx=6, pady=6)
        self.pwd_var = tk.StringVar()
        pwd_entry = ttk.Entry(form, textvariable=self.pwd_var, width=23)
        pwd_entry.grid(row=1, column=1, sticky="w", padx=6, pady=6)
        pwd_entry.bind("<Return>", lambda e: self.try_login())
        pwd_entry.focus_set()

        ttk.Button(center, text="Se connecter", command=self.try_login).pack(pady=16)

        info = ttk.Label(
            center,
            text="Le mot de passe Utilisateur change automatiquement chaque\n"
                 "mois. Contactez l'administrateur pour l'obtenir.\n"
                 "Clavier AZERTY : pensez à Maj (Shift) pour taper les chiffres.",
            justify="center", foreground="#555")
        info.pack(pady=(6, 0))

        footer = tk.Label(self, text=PAID_SOFTWARE_NOTICE, fg="#008751",
                           font=("Segoe UI", 8, "italic"))
        footer.pack(side="bottom", pady=6)

    def try_login(self):
        role = self.role_var.get()
        pwd = self.pwd_var.get().strip()
        cfg = self.app.config_data

        if role == "Administrateur":
            ok = auth.verify_admin_password(pwd)
            if ok:
                self.app.role = "admin"
                self.app.show_main()
            else:
                messagebox.showerror("Connexion refusée",
                                      "Mot de passe administrateur incorrect.\n\n"
                                      "Astuce : le mot de passe est affiché en clair dans le champ "
                                      "ci-dessus, vérifiez qu'il correspond exactement (attention aux "
                                      "claviers AZERTY pour les chiffres, qui nécessitent la touche Maj).")
        else:
            expected = auth.get_effective_user_password(cfg)
            if pwd == expected:
                self.app.role = "user"
                self.app.show_main()
            else:
                messagebox.showerror("Connexion refusée",
                                      "Mot de passe utilisateur incorrect ou expiré "
                                      "(il change chaque mois).")


# ==========================================================================
# ÉCRAN PRINCIPAL
# ==========================================================================

class MainScreen(ttk.Frame):
    def __init__(self, parent, app: App):
        super().__init__(parent)
        self.app = app
        self.pack(fill="both", expand=True)

        top = ttk.Frame(self)
        top.pack(fill="x")
        role_label = "Administrateur" if app.role == "admin" else "Utilisateur"
        ttk.Label(top, text=f"{APP_TITLE}  —  connecté en tant que {role_label}",
                  font=("Segoe UI", 11, "bold")).pack(side="left", padx=10, pady=8)
        ttk.Button(top, text="Se déconnecter", command=app.show_login).pack(side="right", padx=10, pady=8)

        banner = tk.Label(self, text=PAID_SOFTWARE_NOTICE, fg="white", bg="#008751",
                           font=("Segoe UI", 9, "bold"), pady=4)
        banner.pack(fill="x")

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)

        self.employees_tab = EmployeesTab(notebook, app)
        notebook.add(self.employees_tab, text="Saisie des employés")

        self.payroll_tab = PayrollTab(notebook, app, self.employees_tab)
        notebook.add(self.payroll_tab, text="Bulletins / État de paie")

        self.accounting_tab = AccountingTab(notebook, app, self.payroll_tab)
        notebook.add(self.accounting_tab, text="Écritures comptables")

        self.simulator_tab = SimulatorTab(notebook, app, self.employees_tab)
        notebook.add(self.simulator_tab, text="Simulateur de bulletin")

        if app.role == "admin":
            self.params_tab = ParamsTab(notebook, app)
            notebook.add(self.params_tab, text="Paramètres de paie")

            self.security_tab = SecurityTab(notebook, app)
            notebook.add(self.security_tab, text="Sécurité / Mots de passe")


# ==========================================================================
# ONGLET SAISIE DES EMPLOYÉS
# ==========================================================================

COLUMNS = [
    ("numero", "N°", 40),
    ("nom_prenoms", "Nom & Prénoms", 150),
    ("periode_aff", "Période de paie", 105),
    ("matricule_cnss", "Matricule CNSS", 100),
    ("date_naissance", "Date naissance", 90),
    ("date_embauche", "Date embauche", 90),
    ("contacts", "Contacts", 95),
    ("salaire_base", "Sal. Base", 85),
    ("heures_sup", "Heures Sup", 80),
    ("primes", "Primes", 75),
    ("indemnite_transport", "Ind. Transport", 90),
    ("indemnite_logement", "Ind. Logement", 90),
    ("indemnite_communication", "Ind. Comm.", 85),
    ("gratification", "Gratif.", 75),
    ("autres_primes", "Autres Primes", 90),
    ("avance_acompte", "Avance/Acompte", 95),
    ("retenue_pret", "Retenue Prêt", 90),
    ("autres_retenues", "Autres Ret.", 85),
    ("date_saisie", "Date de saisie", 100),
]

MONEY_COLUMNS = {
    "salaire_base", "heures_sup", "primes", "indemnite_transport", "indemnite_logement",
    "indemnite_communication", "gratification", "autres_primes", "avance_acompte",
    "retenue_pret", "autres_retenues",
}


class EmployeesTab(ttk.Frame):
    def __init__(self, parent, app: App):
        super().__init__(parent)
        self.app = app

        # --- Taux Risques Professionnels : accessible à TOUS les rôles (pas
        # seulement l'Administrateur), car il dépend du secteur d'activité et
        # doit pouvoir être ajusté sans mot de passe Administrateur.
        risque_bar = ttk.Frame(self)
        risque_bar.pack(side="top", fill="x", padx=6, pady=(6, 0))
        ttk.Label(risque_bar, text="Taux CNSS Risques Professionnels (%) :",
                  font=("Segoe UI", 9, "bold")).pack(side="left")
        current_rate = self.app.config_data["params"].get("taux_cnss_risques_pro", 0.04) * 100
        self.risque_pro_var = tk.StringVar(value=f"{current_rate:g}")
        ttk.Entry(risque_bar, textvariable=self.risque_pro_var, width=6).pack(side="left", padx=(6, 4))
        ttk.Label(risque_bar, text="%").pack(side="left")
        ttk.Button(risque_bar, text="Enregistrer ce taux",
                   command=self.save_risque_pro_rate).pack(side="left", padx=(10, 0))
        ttk.Label(risque_bar, text="(selon l'activité de l'entreprise, généralement entre 1% et 4%)",
                  foreground="#666").pack(side="left", padx=(10, 0))

        # --- Barre d'import en masse (Excel/CSV), utile quand il y a beaucoup
        # d'employés à saisir : on remplit un fichier plutôt que le formulaire.
        toolbar = ttk.Frame(self)
        toolbar.pack(side="top", fill="x", padx=6, pady=(6, 0))
        ttk.Label(toolbar, text="Saisie volumineuse :", font=("Segoe UI", 9, "bold")).pack(side="left")
        ttk.Button(toolbar, text="Importer depuis Excel/CSV",
                   command=self.import_from_file).pack(side="left", padx=(8, 4))
        ttk.Button(toolbar, text="Télécharger le modèle Excel",
                   command=self.download_template).pack(side="left", padx=4)

        # IMPORTANT : on réserve d'abord la place du panneau de droite (largeur
        # fixe) AVANT de placer le tableau (qui a beaucoup de colonnes et
        # utilise fill="both", expand=True). Si on faisait l'inverse, le
        # tableau engloutirait toute la largeur de la fenêtre et le panneau
        # de saisie serait poussé hors champ (invisible), même s'il existe
        # bien dans le code.
        right = ttk.Frame(self, width=340)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)  # garde la largeur réservée même si le contenu est plus petit

        left = ttk.Frame(self)
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))

        cols = [c[0] for c in COLUMNS]
        self.tree = ttk.Treeview(left, columns=cols, show="headings", height=20)
        for key, label, width in COLUMNS:
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, anchor="center")
        self.tree.grid(row=0, column=0, sticky="nsew")

        vsb = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(left, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        left.grid_rowconfigure(0, weight=1)
        left.grid_columnconfigure(0, weight=1)

        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        ttk.Label(right, text="Fiche employé", font=("Segoe UI", 11, "bold")).pack(pady=(4, 10))

        # IMPORTANT : les boutons sont packés AVANT la zone défilante des
        # champs, et ancrés en bas ("side=bottom"), pour qu'ils restent
        # TOUJOURS visibles même si la liste de champs est longue -- sinon
        # le canvas défilant (fill="both", expand=True) engloutit toute la
        # hauteur restante et les boutons se retrouvent invisibles, hors
        # de la fenêtre.
        ttk.Button(right, text="Vider le formulaire", command=self.clear_form).pack(side="bottom", pady=(0, 10))
        btns = ttk.Frame(right)
        btns.pack(side="bottom", pady=(6, 4))
        ttk.Button(btns, text="Ajouter", command=self.add_employee).grid(row=0, column=0, padx=4)
        ttk.Button(btns, text="Mettre à jour", command=self.update_employee).grid(row=0, column=1, padx=4)
        ttk.Button(btns, text="Supprimer", command=self.delete_employee).grid(row=0, column=2, padx=4)
        ttk.Separator(right).pack(side="bottom", fill="x", pady=(4, 4))

        canvas = tk.Canvas(right, highlightthickness=0, width=320)
        scrollbar = ttk.Scrollbar(right, orient="vertical", command=canvas.yview)
        form = ttk.Frame(canvas)
        form.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=form, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(8, 0))
        scrollbar.pack(side="right", fill="y")

        self.form_vars = {}

        fields = [
            ("nom_prenoms", "Nom & Prénoms", "text"),
            ("periode", "Période de paie (MM/AAAA)", "period"),
            ("matricule_cnss", "Matricule CNSS", "text"),
            ("date_naissance", "Date de naissance (JJ/MM/AAAA)", "text"),
            ("date_embauche", "Date d'embauche (JJ/MM/AAAA)", "text"),
            ("contacts", "Contacts (téléphone)", "text"),
            ("direction", "Direction", "text"),
            ("service", "Service", "text"),
            ("emploi", "Emploi", "text"),
            ("categorie", "Catégorie", "text"),
            ("salaire_base", "Salaire de base", "num"),
            ("heures_sup", "Heures supplémentaires", "num"),
            ("primes", "Primes", "num"),
            ("indemnite_transport", "Indemnité de Transport", "num"),
            ("indemnite_logement", "Indemnité de Logement", "num"),
            ("indemnite_communication", "Indemnité de Communication", "num"),
            ("gratification", "Gratification", "num"),
            ("autres_primes", "Autres Primes", "num"),
            ("avance_acompte", "Avance/Acompte sur Salaires", "num"),
            ("retenue_pret", "Retenue sur prêts", "num"),
            ("autres_retenues", "Autres retenues", "num"),
        ]
        for i, (key, label, kind) in enumerate(fields):
            ttk.Label(form, text=label).grid(row=i, column=0, sticky="w", pady=2)
            var = tk.StringVar()
            if kind == "period":
                w = ttk.Entry(form, textvariable=var, width=18)
                today = datetime.date.today()
                var.set(f"{today.month:02d}/{today.year:04d}")
            else:
                w = ttk.Entry(form, textvariable=var, width=18)
                if kind == "num":
                    var.set("0")
            w.grid(row=i, column=1, pady=2, sticky="w")
            self.form_vars[key] = var

        self.selected_numero = None
        self.selected_date_saisie = None
        self.refresh_tree()

    # ------------------------------------------------------------------
    def save_risque_pro_rate(self):
        text = self.risque_pro_var.get().strip().replace(",", ".").replace("%", "")
        try:
            pct = float(text)
        except ValueError:
            messagebox.showerror("Erreur", "Merci de saisir un nombre (ex : 4 pour 4%).")
            return
        if not (0 <= pct <= 100):
            messagebox.showerror("Erreur", "Le taux doit être compris entre 0 et 100.")
            return
        self.app.config_data["params"]["taux_cnss_risques_pro"] = pct / 100
        try:
            storage.save(self.app.config_data)
        except Exception as exc:
            messagebox.showerror("Erreur", f"Impossible d'enregistrer : {exc}")
            return
        messagebox.showinfo("Enregistré",
                             f"Taux Risques Professionnels mis à jour : {pct:g}%.\n"
                             "Il sera appliqué à tous les prochains calculs de paie.")

    def get_employees(self):
        return self.app.config_data["employees"]

    def refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        for emp in self.get_employees():
            values = []
            for key, _, _ in COLUMNS:
                if key == "periode_aff":
                    values.append(format_period(emp.get("periode", "")))
                elif key in MONEY_COLUMNS:
                    values.append(fmt_amount(emp.get(key, "")))
                else:
                    values.append(emp.get(key, ""))
            self.tree.insert("", "end", iid=str(emp["numero"]), values=values)

    def _read_form(self):
        v = self.form_vars
        try:
            emp = Employee(
                numero=self.selected_numero or self.app.config_data["next_numero"],
                nom_prenoms=v["nom_prenoms"].get().strip(),
                matricule_cnss=v["matricule_cnss"].get().strip(),
                date_naissance=v["date_naissance"].get().strip(),
                date_embauche=v["date_embauche"].get().strip(),
                contacts=v["contacts"].get().strip(),
                direction=v["direction"].get().strip(),
                service=v["service"].get().strip(),
                emploi=v["emploi"].get().strip(),
                categorie=v["categorie"].get().strip(),
                periode=normalize_period(v["periode"].get()),
                salaire_base=float(v["salaire_base"].get() or 0),
                heures_sup=float(v["heures_sup"].get() or 0),
                primes=float(v["primes"].get() or 0),
                indemnite_transport=float(v["indemnite_transport"].get() or 0),
                indemnite_logement=float(v["indemnite_logement"].get() or 0),
                indemnite_communication=float(v["indemnite_communication"].get() or 0),
                gratification=float(v["gratification"].get() or 0),
                autres_primes=float(v["autres_primes"].get() or 0),
                avance_acompte=float(v["avance_acompte"].get() or 0),
                retenue_pret=float(v["retenue_pret"].get() or 0),
                autres_retenues=float(v["autres_retenues"].get() or 0),
                date_saisie=self.selected_date_saisie or datetime.date.today().isoformat(),
            )
        except ValueError:
            messagebox.showerror("Erreur de saisie", "Merci de vérifier les valeurs numériques saisies.")
            return None
        if not emp.nom_prenoms:
            messagebox.showerror("Erreur de saisie", "Le nom de l'employé est obligatoire.")
            return None
        return emp

    def _save_or_report(self):
        """Enregistre les données locales ; affiche une erreur claire en cas
        d'échec (ex: permissions) au lieu de laisser l'action passer inaperçue."""
        try:
            storage.save(self.app.config_data)
            return True
        except Exception as exc:
            messagebox.showerror(
                "Impossible d'enregistrer",
                "L'enregistrement local a échoué. Vérifiez que l'application "
                "peut écrire dans votre dossier utilisateur (lancez-la en tant "
                "qu'administrateur, ou vérifiez qu'un antivirus/Windows Defender "
                "ne la bloque pas).\n\n"
                f"Détail technique : {exc}")
            return False

    def add_employee(self):
        emp = self._read_form()
        if emp is None:
            return
        emp.numero = self.app.config_data["next_numero"]
        self.app.config_data["employees"].append(emp.to_dict())
        self.app.config_data["next_numero"] += 1
        if not self._save_or_report():
            # on annule l'ajout en mémoire si l'enregistrement a échoué,
            # pour ne pas désynchroniser l'affichage et le fichier de données
            self.app.config_data["employees"].pop()
            self.app.config_data["next_numero"] -= 1
            return
        self.refresh_tree()
        self.clear_form()
        messagebox.showinfo("Ajouté", f"Employé « {emp.nom_prenoms} » ajouté avec succès.")

    def update_employee(self):
        if self.selected_numero is None:
            messagebox.showinfo("Info", "Sélectionnez d'abord un employé dans la liste.")
            return
        emp = self._read_form()
        if emp is None:
            return
        employees = self.app.config_data["employees"]
        for i, e in enumerate(employees):
            if e["numero"] == self.selected_numero:
                employees[i] = emp.to_dict()
                break
        if not self._save_or_report():
            return
        self.refresh_tree()

    def delete_employee(self):
        if self.selected_numero is None:
            messagebox.showinfo("Info", "Sélectionnez d'abord un employé dans la liste.")
            return
        if not messagebox.askyesno("Confirmer", "Supprimer cet employé ?"):
            return
        employees = self.app.config_data["employees"]
        self.app.config_data["employees"] = [e for e in employees if e["numero"] != self.selected_numero]
        if not self._save_or_report():
            return
        self.refresh_tree()
        self.clear_form()

    def clear_form(self):
        self.selected_numero = None
        self.selected_date_saisie = None
        for key, var in self.form_vars.items():
            if key == "periode":
                today = datetime.date.today()
                var.set(f"{today.month:02d}/{today.year:04d}")
            elif key in ("nom_prenoms", "matricule_cnss", "date_naissance", "date_embauche",
                         "contacts", "direction", "service", "emploi", "categorie"):
                var.set("")
            else:
                var.set("0")
        self.tree.selection_remove(self.tree.selection())

    def on_select(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        numero = int(sel[0])
        self.selected_numero = numero
        emp = next((e for e in self.get_employees() if e["numero"] == numero), None)
        if not emp:
            return
        self.selected_date_saisie = emp.get("date_saisie", "")
        for key, var in self.form_vars.items():
            if key == "periode":
                var.set(self._periode_to_input(emp.get("periode", "")))
            elif key in MONEY_COLUMNS:
                # champ modifiable : pas de séparateur de milliers (garde une
                # valeur ré-éditable/parsable), juste sans ".0" superflu
                val = emp.get(key, 0)
                try:
                    f = float(val)
                    var.set(str(int(f)) if f == int(f) else str(f))
                except (TypeError, ValueError):
                    var.set(str(val))
            else:
                var.set(str(emp.get(key, "")))

    @staticmethod
    def _periode_to_input(period_key):
        """Convertit 'AAAA-MM' (stockage) vers 'MM/AAAA' (saisie)."""
        try:
            year, month = period_key.split("-")
            return f"{int(month):02d}/{year}"
        except Exception:
            today = datetime.date.today()
            return f"{today.month:02d}/{today.year:04d}"

    # ------------------------------------------------------------------
    # IMPORT EN MASSE (Excel / CSV)
    # ------------------------------------------------------------------

    # En-têtes reconnus dans le fichier importé -> champ interne de l'employé.
    # Plusieurs variantes acceptées pour plus de souplesse (accents, casse
    # ignorés à la comparaison).
    IMPORT_HEADER_MAP = {
        "nom & prenoms": "nom_prenoms", "nom et prenoms": "nom_prenoms",
        "nom & prénoms": "nom_prenoms", "nom prenoms": "nom_prenoms", "nom": "nom_prenoms",
        "periode de paie": "periode", "période de paie": "periode", "periode": "periode", "mois": "periode",
        "matricule cnss": "matricule_cnss", "matricule": "matricule_cnss", "n cnss": "matricule_cnss",
        "n° cnss": "matricule_cnss",
        "date de naissance": "date_naissance", "date naissance": "date_naissance",
        "date d'embauche": "date_embauche", "date embauche": "date_embauche",
        "contacts": "contacts", "contact": "contacts", "telephone": "contacts", "téléphone": "contacts",
        "direction": "direction", "service": "service", "emploi": "emploi", "categorie": "categorie",
        "catégorie": "categorie",
        "salaire de base": "salaire_base", "sal de base": "salaire_base", "sal. base": "salaire_base",
        "heures supplementaires": "heures_sup", "heures sup": "heures_sup", "heure sup": "heures_sup",
        "primes": "primes", "prime": "primes",
        "indemnite de transport": "indemnite_transport", "indem. transport": "indemnite_transport",
        "transport": "indemnite_transport",
        "indemnite de logement": "indemnite_logement", "indem. logement": "indemnite_logement",
        "logement": "indemnite_logement",
        "indemnite de communication": "indemnite_communication", "indem. comm.": "indemnite_communication",
        "communication": "indemnite_communication",
        "gratification": "gratification", "gratif.": "gratification", "gratif": "gratification",
        "autres primes": "autres_primes",
        "avance/acompte sur salaires": "avance_acompte", "avance": "avance_acompte", "acompte": "avance_acompte",
        "retenue sur prets": "retenue_pret", "retenue pret": "retenue_pret", "retenue prêt": "retenue_pret",
        "autres retenues": "autres_retenues",
    }

    @staticmethod
    def _normalize_header(text):
        import unicodedata
        text = str(text or "").strip().lower()
        text = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
        return text

    def _parse_rows(self, path):
        """Lit un fichier .xlsx ou .csv et retourne une liste de dicts
        {champ_interne: valeur_brute}, à partir de la ligne d'en-tête."""
        ext = path.lower().rsplit(".", 1)[-1]
        header_map = {self._normalize_header(k): v for k, v in self.IMPORT_HEADER_MAP.items()}

        if ext in ("xlsx", "xlsm"):
            import openpyxl
            try:
                wb = openpyxl.load_workbook(path, data_only=True)
            except Exception as exc:
                raise ValueError(
                    "Impossible d'ouvrir ce fichier Excel.\n"
                    "Vérifiez qu'il est bien au format .xlsx (Excel 2007 ou plus récent — "
                    "pas l'ancien .xls), et qu'il n'est pas ouvert dans Excel en ce moment.\n\n"
                    f"Détail : {exc}")

            # On cherche la feuille qui contient les bons en-têtes, plutôt que
            # de se fier uniquement à la feuille "active" (qui peut être une
            # autre feuille selon la dernière feuille consultée dans Excel).
            best_rows, best_score = None, -1
            for ws in wb.worksheets:
                rows = list(ws.iter_rows(values_only=True))
                if not rows:
                    continue
                header = rows[0]
                score = sum(1 for h in header if self._normalize_header(h) in header_map)
                if score > best_score:
                    best_rows, best_score = rows, score
            all_rows = best_rows or []
        elif ext == "xls":
            raise ValueError(
                "Ce fichier est au format Excel 97-2003 (.xls), pas pris en charge.\n"
                "Ouvrez-le dans Excel puis faites « Fichier > Enregistrer sous » "
                "et choisissez le type « Classeur Excel (*.xlsx) », puis réimportez ce nouveau fichier.")
        elif ext == "csv":
            import csv
            # Les CSV exportés par Excel en français sont souvent encodés en
            # Windows-1252 (cp1252) ou Latin-1, pas en UTF-8 : on essaie
            # plusieurs encodages avant d'abandonner.
            raw_bytes = open(path, "rb").read()
            text = None
            for encoding in ("utf-8-sig", "cp1252", "latin-1"):
                try:
                    text = raw_bytes.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            if text is None:
                raise ValueError("Impossible de lire l'encodage de ce fichier CSV.")

            sample = text[:4096]
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=";,")
            except csv.Error:
                dialect = csv.excel
                dialect.delimiter = ";" if sample.count(";") > sample.count(",") else ","
            reader = csv.reader(text.splitlines(), dialect)
            all_rows = [tuple(row) for row in reader]
        else:
            raise ValueError("Format non pris en charge. Utilisez un fichier .xlsx (Excel) ou .csv.")

        if not all_rows:
            return []

        header_row = all_rows[0]
        field_by_col = {}
        for idx, h in enumerate(header_row):
            norm = self._normalize_header(h)
            if norm in header_map:
                field_by_col[idx] = header_map[norm]

        if "nom_prenoms" not in field_by_col.values():
            raise ValueError("Colonne obligatoire manquante : « Nom & Prénoms ».\n"
                              "Utilisez le bouton « Télécharger le modèle Excel » pour avoir "
                              "les bons en-têtes.")

        records = []
        for row in all_rows[1:]:
            if row is None or all(c in (None, "") for c in row):
                continue
            rec = {}
            for idx, field in field_by_col.items():
                if idx < len(row):
                    rec[field] = row[idx]
            records.append(rec)
        return records

    def import_from_file(self):
        path = filedialog.askopenfilename(
            title="Importer des employés",
            filetypes=[("Excel / CSV", "*.xlsx *.xlsm *.csv"), ("Tous les fichiers", "*.*")],
        )
        if not path:
            return

        try:
            records = self._parse_rows(path)
        except Exception as exc:
            messagebox.showerror("Import impossible", str(exc))
            return

        if not records:
            messagebox.showinfo("Import", "Aucune ligne exploitable trouvée dans ce fichier.")
            return

        def to_float(v):
            if v is None or v == "":
                return 0.0
            if isinstance(v, str):
                v = v.strip()
                # tolère les espaces (séparateur de milliers), le symbole
                # FCFA/CFA, et la virgule décimale française
                v = (v.replace("\xa0", "").replace(" ", "")
                      .replace("FCFA", "").replace("CFA", "").replace("F", "")
                      .replace(",", "."))
            try:
                return float(v)
            except (TypeError, ValueError):
                return 0.0

        imported, skipped = 0, 0
        for rec in records:
            nom = str(rec.get("nom_prenoms", "")).strip()
            if not nom:
                skipped += 1
                continue
            periode = normalize_period(rec.get("periode", ""))
            emp = Employee(
                numero=self.app.config_data["next_numero"],
                nom_prenoms=nom,
                matricule_cnss=str(rec.get("matricule_cnss", "") or "").strip(),
                date_naissance=str(rec.get("date_naissance", "") or "").strip(),
                date_embauche=str(rec.get("date_embauche", "") or "").strip(),
                contacts=str(rec.get("contacts", "") or "").strip(),
                direction=str(rec.get("direction", "") or "").strip(),
                service=str(rec.get("service", "") or "").strip(),
                emploi=str(rec.get("emploi", "") or "").strip(),
                categorie=str(rec.get("categorie", "") or "").strip(),
                periode=periode,
                salaire_base=to_float(rec.get("salaire_base")),
                heures_sup=to_float(rec.get("heures_sup")),
                primes=to_float(rec.get("primes")),
                indemnite_transport=to_float(rec.get("indemnite_transport")),
                indemnite_logement=to_float(rec.get("indemnite_logement")),
                indemnite_communication=to_float(rec.get("indemnite_communication")),
                gratification=to_float(rec.get("gratification")),
                autres_primes=to_float(rec.get("autres_primes")),
                avance_acompte=to_float(rec.get("avance_acompte")),
                retenue_pret=to_float(rec.get("retenue_pret")),
                autres_retenues=to_float(rec.get("autres_retenues")),
                date_saisie=datetime.date.today().isoformat(),
            )
            self.app.config_data["employees"].append(emp.to_dict())
            self.app.config_data["next_numero"] += 1
            imported += 1

        storage.save(self.app.config_data)
        self.refresh_tree()
        msg = f"{imported} employé(s) importé(s)."
        if skipped:
            msg += f"\n{skipped} ligne(s) ignorée(s) (nom manquant)."
        messagebox.showinfo("Import terminé", msg)

    def download_template(self):
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill
            from openpyxl.utils import get_column_letter
        except ImportError:
            messagebox.showerror("Module manquant",
                                  "Le module 'openpyxl' n'est pas installé.\n"
                                  "Installez-le avec : pip install openpyxl")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Classeur Excel", "*.xlsx")],
            initialfile="Modele_import_employes.xlsx",
        )
        if not path:
            return

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Employés"
        headers = ["Nom & Prénoms", "Période de paie (MM/AAAA)", "Matricule CNSS",
                   "Date de naissance", "Date d'embauche", "Contacts",
                   "Salaire de base", "Heures supplémentaires", "Primes",
                   "Indemnité de Transport", "Indemnité de Logement", "Indemnité de Communication",
                   "Gratification", "Autres Primes", "Avance/Acompte sur Salaires",
                   "Retenue sur prêts", "Autres retenues"]
        ws.append(headers)
        for cell in ws[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="008751")
        today = datetime.date.today()
        ws.append(["AZA Faustin", f"{today.month:02d}/{today.year:04d}", "",
                   "01/01/1995", "01/01/2024", "01 90 00 00 00",
                   150000, 0, 0, 25000, 0, 10000, 0, 0, 0, 0, 0])
        for i, col in enumerate(ws.columns, start=1):
            length = max((len(str(c.value)) for c in col if c.value is not None), default=12)
            ws.column_dimensions[get_column_letter(i)].width = max(14, length + 2)
        wb.save(path)
        messagebox.showinfo(
            "Modèle créé",
            f"Modèle enregistré :\n{path}\n\n"
            "Remplissez une ligne par employé, puis utilisez "
            "« Importer depuis Excel/CSV ».")


# ==========================================================================
# ONGLET BULLETINS / ÉTAT DE PAIE
# ==========================================================================

class PayrollTab(ttk.Frame):
    def __init__(self, parent, app: App, employees_tab: EmployeesTab):
        super().__init__(parent)
        self.app = app
        self.employees_tab = employees_tab

        top = ttk.Frame(self)
        top.pack(fill="x", pady=6, padx=6)

        today = datetime.date.today()
        ttk.Label(top, text="Période de paie :").pack(side="left")
        self.mois_var = tk.StringVar(value=MOIS_FR[today.month - 1])
        ttk.Combobox(top, textvariable=self.mois_var, values=MOIS_FR, state="readonly",
                     width=12).pack(side="left", padx=6)
        self.annee_var = tk.StringVar(value=str(today.year))
        ttk.Entry(top, textvariable=self.annee_var, width=6).pack(side="left")

        self.all_periods_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="Toutes périodes confondues",
                         variable=self.all_periods_var).pack(side="left", padx=(10, 0))

        ttk.Button(top, text="Calculer la paie", command=self.calculate).pack(side="left", padx=16)
        ttk.Button(top, text="Exporter vers Excel", command=self.export_excel).pack(side="left", padx=(0, 6))
        ttk.Button(top, text="Bordereau des salaires (Excel)",
                   command=self.export_bordereau).pack(side="left", padx=(0, 6))
        ttk.Button(top, text="Bulletin PDF (sélection)", command=self.export_selected_payslip).pack(side="left", padx=(0, 6))
        ttk.Button(top, text="Tous les bulletins (PDF)", command=self.export_all_payslips).pack(side="left")

        result_cols = ["numero", "nom_prenoms", "total_brut", "cnss_vieillesse_salariale",
                        "its", "trtv", "total_retenues_salariales", "net_a_payer",
                        "cout_total_employeur"]
        headers = ["N°", "Nom & Prénoms", "Total Brut", "CNSS (3,6%)",
                   "ITS (charge patr.)", "TRTV", "Total Retenues", "Net à payer", "Coût Employeur"]

        self.result_cols = result_cols
        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=6, pady=6)
        self.tree = ttk.Treeview(tree_frame, columns=result_cols, show="headings", height=20)
        for key, label in zip(result_cols, headers):
            self.tree.heading(key, text=label)
            self.tree.column(key, width=105, anchor="center")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        totals = ttk.Frame(self)
        totals.pack(fill="x", padx=6, pady=(0, 6))
        self.totals_label = ttk.Label(totals, text="", font=("Segoe UI", 10, "bold"))
        self.totals_label.pack(side="left")

        self.last_results = []

    def selected_period_key(self):
        month = MOIS_FR.index(self.mois_var.get()) + 1
        try:
            year = int(self.annee_var.get())
        except ValueError:
            year = datetime.date.today().year
        return f"{year:04d}-{month:02d}"

    def selected_month_num(self):
        return MOIS_FR.index(self.mois_var.get()) + 1

    def calculate(self):
        params = self.app.config_data["params"]
        employees = self.app.config_data["employees"]
        all_periods = self.all_periods_var.get()
        if not all_periods:
            period_key = self.selected_period_key()
            employees = [e for e in employees if e.get("periode") == period_key]
        mois = None if all_periods else self.selected_month_num()

        self.tree.delete(*self.tree.get_children())
        results = []
        total_net = total_cnss = total_its = total_trtv = total_cout = 0.0
        for e in employees:
            emp = Employee(**e)
            r = compute_payslip(emp, params, mois=mois)
            results.append(r)
            values = [r["numero"] if k == "numero" else
                      r["nom_prenoms"] if k == "nom_prenoms" else
                      fmt_amount(r[k]) for k in self.result_cols]
            self.tree.insert("", "end", values=values)
            total_net += r["net_a_payer"]
            total_cnss += r["cnss_total"]
            total_its += r["its"]
            total_trtv += r["trtv"]
            total_cout += r["cout_total_employeur"]
        self.last_results = results
        self.totals_label.config(
            text=(f"Total Net à payer : {total_net:,.0f}  |  Total CNSS : {total_cnss:,.0f}  |  "
                  f"Total ITS : {total_its:,.0f}  |  Total TRTV : {total_trtv:,.0f}  |  "
                  f"Coût total employeur : {total_cout:,.0f}  FCFA")
            .replace(",", " ")
        )
        if not employees:
            messagebox.showinfo("Info", "Aucun employé saisi pour le moment.")

    def export_excel(self):
        if not self.last_results:
            self.calculate()
        if not self.last_results:
            return
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment
            from openpyxl.utils import get_column_letter
        except ImportError:
            messagebox.showerror("Module manquant",
                                  "Le module 'openpyxl' n'est pas installé.\n"
                                  "Installez-le avec : pip install openpyxl")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Classeur Excel", "*.xlsx")],
            initialfile=f"Etat_de_paie_{self.mois_var.get()}_{self.annee_var.get()}.xlsx",
        )
        if not path:
            return

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "État de paie"

        title = f"ÉTAT DE PAIE — {self.mois_var.get().upper()} {self.annee_var.get()}"
        ws.merge_cells("A1:L1")
        ws["A1"] = title
        ws["A1"].font = Font(size=14, bold=True)

        headers = ["N°", "Nom & Prénoms", "Total Brut", "CNSS Salariale (3,6%)",
                   "ITS", "TRTV", "Avance/Prêt/Autres", "Total Retenues",
                   "Net à payer", "Coût Total Employeur"]
        ws.append([])
        ws.append(headers)
        header_row = ws.max_row
        for cell in ws[header_row]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="008751")
            cell.alignment = Alignment(horizontal="center")

        for r in self.last_results:
            ws.append([
                r["numero"], r["nom_prenoms"], r["total_brut"],
                r["cnss_vieillesse_salariale"], r["its"], r["trtv"],
                r["avance_acompte"] + r["retenue_pret"] + r["autres_retenues"],
                r["total_retenues_salariales"], r["net_a_payer"],
                r["cout_total_employeur"],
            ])

        for i, col in enumerate(ws.columns, start=1):
            length = max((len(str(c.value)) for c in col if c.value is not None), default=10)
            ws.column_dimensions[get_column_letter(i)].width = max(12, length + 2)

        notice_row = ws.max_row + 2
        ws.cell(row=notice_row, column=1, value=PAID_SOFTWARE_NOTICE).font = Font(italic=True, color="008751")

        wb.save(path)
        messagebox.showinfo("Export réussi", f"Fichier exporté :\n{path}")

    def export_bordereau(self):
        """Génère le « Bordereau des salaires » au format agence (une ligne
        par employé + colonnes IFU/CNSS/dates + détail CNSS patronale-ouvrière
        + VPS + ITS + Net + Total employeur), conforme au modèle fourni par
        le client, avec ligne TOTAL et récapitulatif des charges du mois."""
        if not self.last_results:
            self.calculate()
        if not self.last_results:
            return
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
            from openpyxl.utils import get_column_letter
        except ImportError:
            messagebox.showerror("Module manquant",
                                  "Le module 'openpyxl' n'est pas installé.\n"
                                  "Installez-le avec : pip install openpyxl")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Classeur Excel", "*.xlsx")],
            initialfile=f"Bordereau_des_salaires_{self.mois_var.get()}_{self.annee_var.get()}.xlsx",
        )
        if not path:
            return

        entete = self.app.config_data.get("bulletin_entete", {}) or {}
        ifu_entreprise = entete.get("ifu", "")
        entreprise_nom = entete.get("nom_entreprise") or self.app.config_data.get("entreprise", "")

        def split_nom_prenoms(full):
            full = (full or "").strip()
            if " " in full:
                nom, prenoms = full.split(" ", 1)
            else:
                nom, prenoms = full, ""
            return nom, prenoms

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Bordereau des salaires"

        header_fill = PatternFill("solid", fgColor="008751")
        header_font = Font(bold=True, color="FFFFFF", size=9)
        title_font = Font(bold=True, size=13)
        center = Alignment(horizontal="center", vertical="center", wrap_text=True)
        thin = Side(style="thin", color="AAAAAA")
        border = Border(left=thin, right=thin, top=thin, bottom=thin)

        n_cols = 19
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=n_cols)
        title_txt = f"DÉTAILS DES SALAIRES DES AGENTS"
        if entreprise_nom:
            title_txt += f" — {entreprise_nom.upper()}"
        title_txt += f" — {self._period_display().upper()}"
        ws.cell(row=1, column=1, value=title_txt).font = title_font

        # --- En-têtes (2 lignes, avec cellules fusionnées pour les groupes) --
        r1, r2 = 3, 4
        simple_headers = ["N°", "IFU", "NOM", "PRÉNOMS", "N° CNSS", "DATE DE\nNAISSANCE",
                           "DATE\nD'EMBAUCHE", "CONTACTS", "FONCTION", "SALAIRE DE\nBASE",
                           "TOTAL\nPRIMES", "AUTRES\nGRATIFICATIONS", "SALAIRE\nBRUT"]
        for i, h in enumerate(simple_headers, start=1):
            ws.merge_cells(start_row=r1, start_column=i, end_row=r2, end_column=i)
            cell = ws.cell(row=r1, column=i, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center
            cell.border = border

        col = len(simple_headers) + 1  # 14
        ws.merge_cells(start_row=r1, start_column=col, end_row=r1, end_column=col + 1)
        c = ws.cell(row=r1, column=col, value="COTISATIONS CNSS")
        c.font = header_font; c.fill = header_fill; c.alignment = center; c.border = border
        ws.cell(row=r2, column=col, value="PART\nPATRONALE").font = header_font
        ws.cell(row=r2, column=col + 1, value="PART\nOUVRIÈRE").font = header_font
        for cc in (col, col + 1):
            ws.cell(row=r2, column=cc).fill = header_fill
            ws.cell(row=r2, column=cc).alignment = center
            ws.cell(row=r2, column=cc).border = border
        col += 2  # 16

        ws.merge_cells(start_row=r1, start_column=col, end_row=r1, end_column=col + 1)
        c = ws.cell(row=r1, column=col, value="RETENUES FISCALES")
        c.font = header_font; c.fill = header_fill; c.alignment = center; c.border = border
        ws.cell(row=r2, column=col, value="VPS").font = header_font
        ws.cell(row=r2, column=col + 1, value="ITS").font = header_font
        for cc in (col, col + 1):
            ws.cell(row=r2, column=cc).fill = header_fill
            ws.cell(row=r2, column=cc).alignment = center
            ws.cell(row=r2, column=cc).border = border
        col += 2  # 18

        for label in ("SALAIRE NET", "TOTAL EMPLOYEUR"):
            ws.merge_cells(start_row=r1, start_column=col, end_row=r2, end_column=col)
            cell = ws.cell(row=r1, column=col, value=label)
            cell.font = header_font; cell.fill = header_fill; cell.alignment = center; cell.border = border
            col += 1
        n_cols = col - 1

        # --- Lignes employés -----------------------------------------------
        row_idx = r2 + 1
        first_data_row = row_idx
        total_row_values = None

        for r in self.last_results:
            nom, prenoms = split_nom_prenoms(r["nom_prenoms"])
            total_primes = (r["heures_sup"] + r["primes"] + r["indemnite_transport"]
                             + r["indemnite_logement"] + r["indemnite_communication"])
            autres_gratifications = r["gratification"] + r["autres_primes"]
            # Arrondi une seule fois sur la somme des 3 taux CNSS patronaux
            # (plutôt que d'additionner 3 montants déjà arrondis séparément)
            # pour éviter un écart de +/- 1 F par rapport au bordereau de référence.
            params = self.app.config_data["params"]
            taux_patronal_total = (params["taux_cnss_allocations_familiales"]
                                    + params["taux_cnss_risques_pro"]
                                    + params["taux_cnss_vieillesse_patronal"])
            cnss_patronale = round(r["total_brut"] * taux_patronal_total)
            cnss_ouvriere = r["cnss_vieillesse_salariale"]
            total_employeur_bordereau = r["net_a_payer"] + cnss_patronale + r["vps"] + r["its"]

            values = [r["numero"], ifu_entreprise, nom, prenoms, r.get("matricule_cnss", ""),
                      r.get("date_naissance", ""), r.get("date_embauche", ""), r.get("contacts", ""),
                      r.get("emploi", ""), r["salaire_base"], total_primes, autres_gratifications,
                      r["total_brut"], cnss_patronale, cnss_ouvriere, r["vps"], r["its"],
                      r["net_a_payer"], total_employeur_bordereau]
            for i, v in enumerate(values, start=1):
                cell = ws.cell(row=row_idx, column=i, value=v)
                cell.border = border
                if i >= 10:
                    cell.number_format = "#,##0"
                if i in (1,):
                    cell.alignment = Alignment(horizontal="center")
            row_idx += 1

        last_data_row = row_idx - 1

        # --- Ligne TOTAL -----------------------------------------------------
        ws.cell(row=row_idx, column=9, value="TOTAL").font = Font(bold=True)
        numeric_cols = list(range(10, n_cols + 1))
        for i in numeric_cols:
            col_letter = get_column_letter(i)
            cell = ws.cell(row=row_idx, column=i,
                            value=f"=SUM({col_letter}{first_data_row}:{col_letter}{last_data_row})")
            cell.font = Font(bold=True)
            cell.number_format = "#,##0"
            cell.border = border
            cell.fill = PatternFill("solid", fgColor="EEF2F7")
        total_row = row_idx
        row_idx += 2

        # --- Récapitulatif « Charges totales / mois » -----------------------
        ws.cell(row=row_idx, column=9, value="CHARGES TOTALES / MOIS").font = Font(bold=True)
        brut_col, patronale_col, vps_col, its_col = "M", "N", "P", "Q"
        formula = (f"={brut_col}{total_row}+{patronale_col}{total_row}"
                   f"+{vps_col}{total_row}+{its_col}{total_row}")
        cell = ws.cell(row=row_idx, column=n_cols, value=formula)
        cell.font = Font(bold=True)
        cell.number_format = "#,##0"
        ws.cell(row=row_idx + 1, column=9,
                value="(= Total Salaire Brut + Cotisations CNSS patronale + VPS + ITS)").font = Font(italic=True, size=8)

        for i in range(1, n_cols + 1):
            length = 14
            header_txt = simple_headers[i - 1] if i <= len(simple_headers) else ""
            length = max(length, len(header_txt.replace("\n", " ")) + 2)
            ws.column_dimensions[get_column_letter(i)].width = max(10, min(length, 22))
        ws.row_dimensions[r1].height = 30
        ws.row_dimensions[r2].height = 26

        notice_row = row_idx + 3
        ws.cell(row=notice_row, column=1, value=PAID_SOFTWARE_NOTICE).font = Font(italic=True, color="008751")

        wb.save(path)
        messagebox.showinfo("Export réussi", f"Bordereau des salaires généré :\n{path}")

    def _period_display(self):
        return f"{self.mois_var.get()} {self.annee_var.get()}"

    def export_selected_payslip(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Sélectionnez d'abord un employé dans le tableau ci-dessus "
                                         "(après avoir cliqué sur « Calculer la paie »).")
            return
        if not self.last_results:
            messagebox.showinfo("Info", "Cliquez d'abord sur « Calculer la paie ».")
            return
        values = self.tree.item(sel[0], "values")
        numero = int(values[0])
        result = next((r for r in self.last_results if r["numero"] == numero), None)
        if result is None:
            messagebox.showerror("Erreur", "Employé introuvable dans les résultats calculés.")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile=f"Bulletin_{result['nom_prenoms'].replace(' ', '_')}_{self.mois_var.get()}_{self.annee_var.get()}.pdf",
        )
        if not path:
            return
        try:
            self._generate_payslips_pdf([result], path)
        except ImportError:
            messagebox.showerror("Module manquant",
                                  "Le module 'reportlab' n'est pas installé.\n"
                                  "Installez-le avec : pip install reportlab")
            return
        messagebox.showinfo("Export réussi", f"Bulletin de paie généré :\n{path}")

    def export_all_payslips(self):
        if not self.last_results:
            self.calculate()
        if not self.last_results:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile=f"Bulletins_de_paie_{self.mois_var.get()}_{self.annee_var.get()}.pdf",
        )
        if not path:
            return
        try:
            self._generate_payslips_pdf(self.last_results, path)
        except ImportError:
            messagebox.showerror("Module manquant",
                                  "Le module 'reportlab' n'est pas installé.\n"
                                  "Installez-le avec : pip install reportlab")
            return
        messagebox.showinfo("Export réussi",
                             f"{len(self.last_results)} bulletin(s) de paie généré(s) dans :\n{path}")

    def _generate_payslips_pdf(self, results, path):
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas as pdf_canvas

        entete = self.app.config_data.get("bulletin_entete", {}) or {}
        pied = self.app.config_data.get("bulletin_pied_de_page", "") or ""
        periode_txt = self._period_display()

        width, height = A4
        c = pdf_canvas.Canvas(path, pagesize=A4)

        for result in results:
            self._draw_payslip_page(c, width, height, mm, entete, pied, periode_txt, result)
            c.showPage()

        c.save()

    def _draw_payslip_page(self, c, width, height, mm, entete, pied, periode_txt, r):
        import base64
        import io
        from reportlab.lib.utils import ImageReader

        x_left = 18 * mm
        x_right = width - 18 * mm
        y = height - 18 * mm

        # --- En-tête ---------------------------------------------------
        text_x = x_left
        logo_bottom_y = None
        logo_b64 = entete.get("logo_base64")
        if logo_b64:
            try:
                img_bytes = base64.b64decode(logo_b64)
                img = ImageReader(io.BytesIO(img_bytes))
                iw, ih = img.getSize()
                logo_h = 18 * mm
                logo_w = logo_h * (iw / ih) if ih else logo_h
                logo_w = min(logo_w, 35 * mm)
                logo_top_y = y
                c.drawImage(img, x_left, logo_top_y - logo_h + 3 * mm, width=logo_w, height=logo_h,
                            preserveAspectRatio=True, mask="auto")
                logo_bottom_y = logo_top_y - logo_h + 1 * mm
                text_x = x_left + logo_w + 6 * mm
            except Exception:
                pass  # logo illisible : on continue sans bloquer la génération du bulletin

        c.setFont("Helvetica-Bold", 14)
        c.drawString(text_x, y, entete.get("nom_entreprise") or "Mon Entreprise")
        y -= 6 * mm
        c.setFont("Helvetica", 9)
        coords = [v for v in (entete.get("adresse"), entete.get("telephone"), entete.get("email")) if v]
        if entete.get("ifu"):
            coords.append(f"IFU : {entete['ifu']}")
        if coords:
            c.drawString(text_x, y, "  •  ".join(coords))
            y -= 5 * mm
        if entete.get("note_entete"):
            c.setFont("Helvetica-Oblique", 8)
            c.drawString(text_x, y, entete["note_entete"])
            y -= 5 * mm

        if logo_bottom_y is not None:
            y = min(y, logo_bottom_y)

        y -= 2 * mm
        c.setLineWidth(1)
        c.line(x_left, y, x_right, y)
        y -= 8 * mm

        c.setFont("Helvetica-Bold", 13)
        c.drawCentredString(width / 2, y, f"BULLETIN DE PAIE — {periode_txt.upper()}")
        y -= 10 * mm

        # --- Bloc employé -----------------------------------------------
        c.setFont("Helvetica", 10)
        c.drawString(x_left, y, f"N° employé : {r['numero']}")
        c.drawString(width / 2, y, f"Matricule CNSS : {r.get('matricule_cnss') or '-'}")
        y -= 6 * mm
        c.setFont("Helvetica-Bold", 11)
        c.drawString(x_left, y, f"{r['nom_prenoms']}")
        y -= 5 * mm
        c.setFont("Helvetica", 10)
        details = " / ".join(v for v in (r.get("direction"), r.get("service"), r.get("emploi")) if v)
        if details:
            c.drawString(x_left, y, details)
            y -= 5 * mm
        y -= 4 * mm

        def money(v):
            return f"{v:,.0f}".replace(",", " ") + " FCFA"

        def row(label, value, y, bold=False, indent=0):
            c.setFont("Helvetica-Bold" if bold else "Helvetica", 10)
            c.drawString(x_left + indent, y, label)
            c.drawRightString(x_right, y, money(value))
            return y - 5.5 * mm

        c.setLineWidth(0.7)
        c.line(x_left, y, x_right, y)
        y -= 6 * mm
        c.setFont("Helvetica-Bold", 10)
        c.drawString(x_left, y, "GAINS")
        y -= 6 * mm

        gain_lines = [
            ("Salaire de base", r["salaire_base"]),
            ("Heures supplémentaires", r["heures_sup"]),
            ("Primes", r["primes"]),
            ("Indemnité de Transport", r["indemnite_transport"]),
            ("Indemnité de Logement", r["indemnite_logement"]),
            ("Indemnité de Communication", r["indemnite_communication"]),
            ("Gratification", r["gratification"]),
            ("Autres Primes", r["autres_primes"]),
        ]
        for label, value in gain_lines:
            if value:  # on n'affiche pas les lignes à 0, pour un bulletin plus lisible
                y = row(label, value, y, indent=2 * mm)
        y -= 1 * mm
        c.setLineWidth(0.4)
        c.line(x_left + 2 * mm, y, x_right, y)
        y -= 5.5 * mm
        y = row("Total Brut (= Brut fiscal = Brut social)", r["total_brut"], y, bold=True)
        y -= 3 * mm

        c.setFont("Helvetica-Bold", 10)
        c.drawString(x_left, y, "RETENUES")
        y -= 6 * mm
        y = row("CNSS Assurance Vieillesse (part salariale, 3,6%)", r["cnss_vieillesse_salariale"], y)
        if r.get("trtv_preleve_ce_mois") and r["trtv"]:
            y = row("TRTV (Taxe Radio + Télé, annuelle)", r["trtv"], y)
        if r["avance_acompte"]:
            y = row("Avance / Acompte sur salaires", r["avance_acompte"], y)
        if r["retenue_pret"]:
            y = row("Retenue sur prêts", r["retenue_pret"], y)
        if r["autres_retenues"]:
            y = row("Autres retenues", r["autres_retenues"], y)
        y -= 3 * mm

        c.setLineWidth(1)
        c.line(x_left, y, x_right, y)
        y -= 8 * mm
        c.setFont("Helvetica-Bold", 13)
        c.drawString(x_left, y, "NET À PAYER")
        c.drawRightString(x_right, y, money(r["net_a_payer"]))
        y -= 8 * mm
        c.setLineWidth(1)
        c.line(x_left, y, x_right, y)
        y -= 10 * mm

        c.setFont("Helvetica", 9)
        c.drawString(x_left, y, "PART PATRONALE (charges employeur, n'affecte pas le Net à payer) :")
        y -= 5 * mm
        patronal_lines = [
            ("Cotisations Familiales (9,00%)", r["cnss_allocations_familiales"]),
            ("Risques Professionnels", r["cnss_risques_pro"]),
            ("Assurance Vieillesse (part patronale, 6,40%)", r["cnss_vieillesse_patronale"]),
            ("Versement Patronal sur Salaires (VPS)", r["vps"]),
            ("ITS (Impôt sur Traitements et Salaires)", r["its"]),
        ]
        for label, value in patronal_lines:
            c.setFont("Helvetica", 8.5)
            c.drawString(x_left + 2 * mm, y, label)
            c.drawRightString(x_right, y, money(value))
            y -= 4.5 * mm
        y -= 1 * mm
        c.setFont("Helvetica", 9)
        c.drawString(x_left, y, f"Coût total employeur : {money(r['cout_total_employeur'])}")

        # --- Pied de page -------------------------------------------------
        bottom = 30 * mm
        c.setLineWidth(0.5)
        c.line(x_left, bottom + 14 * mm, x_right, bottom + 14 * mm)
        c.setFont("Helvetica", 9)
        c.drawString(x_left, bottom + 8 * mm, "Signature de l'employeur")
        c.drawRightString(x_right, bottom + 8 * mm, "Signature de l'employé")

        if pied:
            c.setFont("Helvetica-Oblique", 7.5)
            text_obj = c.beginText(x_left, bottom)
            text_obj.setLeading(9)
            for line in pied.split("\n"):
                text_obj.textLine(line)
            c.drawText(text_obj)


# Génère l'écriture de paie en partie double (Débit / Crédit), à partir des
# résultats calculés dans l'onglet "Bulletins / État de paie". Comptes basés
# sur le plan comptable SYSCOHADA habituellement utilisé pour la paie.

class AccountingTab(ttk.Frame):
    def __init__(self, parent, app: App, payroll_tab: "PayrollTab"):
        super().__init__(parent)
        self.app = app
        self.payroll_tab = payroll_tab

        top = ttk.Frame(self)
        top.pack(fill="x", padx=6, pady=6)
        ttk.Label(top, text="Écritures comptables de la paie :",
                  font=("Segoe UI", 11, "bold")).pack(side="left")

        today = datetime.date.today()
        ttk.Label(top, text="  Période :").pack(side="left")
        self.mois_var = tk.StringVar(value=MOIS_FR[today.month - 1])
        ttk.Combobox(top, textvariable=self.mois_var, values=MOIS_FR, state="readonly",
                     width=12).pack(side="left", padx=4)
        self.annee_var = tk.StringVar(value=str(today.year))
        ttk.Entry(top, textvariable=self.annee_var, width=6).pack(side="left")

        self.all_periods_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="Toutes périodes confondues",
                         variable=self.all_periods_var).pack(side="left", padx=(10, 0))

        ttk.Button(top, text="Générer", command=self.generate).pack(side="left", padx=16)
        ttk.Button(top, text="Exporter vers Excel", command=self.export_excel).pack(side="left")

        cols = ["compte", "libelle", "debit", "credit"]
        headers = ["N° Compte", "Libellé", "Débit", "Crédit"]
        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=6, pady=6)
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=20)
        widths = [100, 380, 130, 130]
        for key, label, w in zip(cols, headers, widths):
            self.tree.heading(key, text=label)
            self.tree.column(key, width=w, anchor="center" if key != "libelle" else "w")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        self.totals_label = ttk.Label(self, text="", font=("Segoe UI", 10, "bold"))
        self.totals_label.pack(anchor="w", padx=6, pady=(0, 6))

        self.last_rows = []

    def selected_period_key(self):
        month = MOIS_FR.index(self.mois_var.get()) + 1
        try:
            year = int(self.annee_var.get())
        except ValueError:
            year = datetime.date.today().year
        return f"{year:04d}-{month:02d}"

    def selected_month_num(self):
        return MOIS_FR.index(self.mois_var.get()) + 1

    def _filtered_employees(self):
        raw = self.app.config_data["employees"]
        if not self.all_periods_var.get():
            period_key = self.selected_period_key()
            raw = [e for e in raw if e.get("periode") == period_key]
        return [Employee(**e) for e in raw]

    def _build_rows(self, employees, results):
        def s(key):
            return sum(r[key] for r in results)

        rows = []
        sum_sal_base = sum(e.salaire_base for e in employees)
        sum_primes = sum(e.primes + e.gratification + e.autres_primes for e in employees)
        sum_hs = sum(e.heures_sup for e in employees)
        sum_transport = sum(e.indemnite_transport for e in employees)
        sum_log = sum(e.indemnite_logement for e in employees)
        sum_comm = sum(e.indemnite_communication for e in employees)

        rows.append(("661100", "SALAIRES DE BASE", sum_sal_base, 0))
        rows.append(("661200", "PRIMES ET GRATIFICATIONS", sum_primes, 0))
        rows.append(("661800", "HEURES SUPPLÉMENTAIRES", sum_hs, 0))
        rows.append(("663400", "INDEMNITÉ DE TRANSPORT", sum_transport, 0))
        rows.append(("663100", "INDEMNITÉ DE LOGEMENT", sum_log, 0))
        rows.append(("663800", "INDEMNITÉ DE COMMUNICATION", sum_comm, 0))

        total_net = s("net_a_payer")
        total_divers = s("avance_acompte") + s("retenue_pret") + s("autres_retenues")
        total_cnss_sal = s("cnss_vieillesse_salariale")
        total_trtv = s("trtv")

        rows.append(("422000", "SALAIRES NETS À PAYER", 0, total_net))
        rows.append(("421000", "AVANCES / PRÊTS / AUTRES RETENUES AU PERSONNEL", 0, total_divers))
        rows.append(("431300", "CNSS ASSURANCE VIEILLESSE — PART SALARIALE", 0, total_cnss_sal))
        if total_trtv:
            rows.append(("447250", "TRTV (TAXE RADIO + TÉLÉ) À REVERSER", 0, total_trtv))

        sous_total_1_debit = sum_sal_base + sum_primes + sum_hs + sum_transport + sum_log + sum_comm
        sous_total_1_credit = total_net + total_divers + total_cnss_sal + total_trtv
        rows.append(("", "SOUS-TOTAL 1 (charges de personnel)", sous_total_1_debit, sous_total_1_credit))

        # --- Charges patronales (dont l'ITS, 100% à la charge de l'employeur)
        total_allocs_fam = s("cnss_allocations_familiales")
        total_risques_pro = s("cnss_risques_pro")
        total_cnss_pat = s("cnss_vieillesse_patronale")
        total_vps = s("vps")
        total_its = s("its")

        rows.append(("664100", "CHARGES SOCIALES — CNSS PATRONALE (ALLOC. FAM. + RISQUES PRO + VIEILLESSE)",
                      total_allocs_fam + total_risques_pro + total_cnss_pat, 0))
        rows.append(("431300", "CNSS — PART PATRONALE (à reverser)", 0,
                      total_allocs_fam + total_risques_pro + total_cnss_pat))
        rows.append(("664400", "VERSEMENT PATRONAL SUR SALAIRES (VPS)", total_vps, 0))
        rows.append(("447230", "VPS À REVERSER", 0, total_vps))
        rows.append(("664500", "ITS (CHARGE PATRONALE)", total_its, 0))
        rows.append(("447210", "ITS À REVERSER", 0, total_its))

        sous_total_2 = total_allocs_fam + total_risques_pro + total_cnss_pat + total_vps + total_its
        rows.append(("", "SOUS-TOTAL 2 (charges patronales)", sous_total_2, sous_total_2))

        grand_total_debit = sous_total_1_debit + sous_total_2
        grand_total_credit = sous_total_1_credit + sous_total_2
        rows.append(("", "GRAND TOTAL", grand_total_debit, grand_total_credit))

        return rows

    def generate(self):
        params = self.app.config_data["params"]
        employees = self._filtered_employees()
        if not employees:
            period_txt = "toutes périodes" if self.all_periods_var.get() else format_period(self.selected_period_key())
            messagebox.showinfo("Info", f"Aucun employé pour la période sélectionnée ({period_txt}).")
            self.tree.delete(*self.tree.get_children())
            self.last_rows = []
            self.totals_label.config(text="")
            return
        mois = None if self.all_periods_var.get() else self.selected_month_num()
        results = [compute_payslip(emp, params, mois=mois) for emp in employees]

        rows = self._build_rows(employees, results)
        self.last_rows = rows
        self.tree.delete(*self.tree.get_children())
        for compte, libelle, debit, credit in rows:
            bold = libelle.startswith(("SOUS-TOTAL", "GRAND TOTAL"))
            values = (compte, libelle, f"{debit:,.0f}".replace(",", " ") if debit else "",
                      f"{credit:,.0f}".replace(",", " ") if credit else "")
            self.tree.insert("", "end", values=values, tags=("total",) if bold else ())
        self.tree.tag_configure("total", font=("Segoe UI", 9, "bold"), background="#eef2f7")

        total_debit = rows[-1][2]
        total_credit = rows[-1][3]
        equilibre = "✓ Écriture équilibrée" if abs(total_debit - total_credit) < 1 else "⚠ ÉCRITURE DÉSÉQUILIBRÉE"
        self.totals_label.config(text=f"{equilibre}  —  Total Débit : {total_debit:,.0f}  |  "
                                       f"Total Crédit : {total_credit:,.0f}  FCFA".replace(",", " "))

    def export_excel(self):
        if not self.last_rows:
            self.generate()
        if not self.last_rows:
            return
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment
            from openpyxl.utils import get_column_letter
        except ImportError:
            messagebox.showerror("Module manquant",
                                  "Le module 'openpyxl' n'est pas installé.\n"
                                  "Installez-le avec : pip install openpyxl")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Classeur Excel", "*.xlsx")],
            initialfile="Ecritures_comptables_paie.xlsx",
        )
        if not path:
            return

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Écritures comptables"

        ws.merge_cells("A1:D1")
        ws["A1"] = "ÉCRITURE COMPTABLE DE PAIE"
        ws["A1"].font = Font(size=14, bold=True)

        ws.append([])
        ws.append(["N° Compte", "Libellé", "Débit", "Crédit"])
        for cell in ws[ws.max_row]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="008751")
            cell.alignment = Alignment(horizontal="center")

        for compte, libelle, debit, credit in self.last_rows:
            ws.append([compte, libelle, debit or None, credit or None])

        for i, col in enumerate(ws.columns, start=1):
            length = max((len(str(c.value)) for c in col if c.value is not None), default=10)
            ws.column_dimensions[get_column_letter(i)].width = max(14, length + 2)

        notice_row = ws.max_row + 2
        ws.cell(row=notice_row, column=1, value=PAID_SOFTWARE_NOTICE).font = Font(italic=True, color="008751")

        wb.save(path)
        messagebox.showinfo("Export réussi", f"Fichier exporté :\n{path}")


# ==========================================================================
# ONGLET SIMULATEUR DE BULLETIN (net -> base + indemnités)
# ==========================================================================

class SimulatorTab(ttk.Frame):
    def __init__(self, parent, app: App, employees_tab: "EmployeesTab"):
        super().__init__(parent)
        self.app = app
        self.employees_tab = employees_tab
        self.last_result = None
        self.last_employee_template = None

        left = ttk.Frame(self)
        left.pack(side="left", fill="y", padx=10, pady=10)

        ttk.Label(left, text="Simulateur : Net → Salaire de base",
                  font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 4))
        ttk.Label(left, text="Entrez le net souhaité, le logiciel retrouve\n"
                              "automatiquement le salaire de base à appliquer.",
                  foreground="#555", justify="left").pack(anchor="w", pady=(0, 12))

        form = ttk.Frame(left)
        form.pack(anchor="w")
        self.vars = {}

        def field(label, key, default, row, kind="num"):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", pady=3)
            var = tk.StringVar(value=str(default))
            w = ttk.Entry(form, textvariable=var, width=20)
            w.grid(row=row, column=1, pady=3, sticky="w")
            self.vars[key] = var
            return w

        field("Nom & Prénoms (optionnel)", "nom_prenoms", "", 0, kind="text")
        field("Mois de paie (1 à 12)", "mois", str(datetime.date.today().month), 1)
        field("Heures supplémentaires", "heures_sup", "0", 2)
        field("Primes", "primes", "0", 3)
        field("Indemnité Transport", "indemnite_transport", "0", 4)
        field("Indemnité Logement", "indemnite_logement", "0", 5)
        field("Indemnité Communication", "indemnite_communication", "0", 6)
        field("Gratification", "gratification", "0", 7)
        field("Autres Primes", "autres_primes", "0", 8)
        field("Retenue prêt/avance", "retenue_pret", "0", 9)

        ttk.Separator(left).pack(fill="x", pady=12)
        ttk.Label(left, text="Net à payer souhaité (FCFA)", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.target_var = tk.StringVar(value="150000")
        ttk.Entry(left, textvariable=self.target_var, width=22, font=("Segoe UI", 11)).pack(anchor="w", pady=(2, 10))

        ttk.Button(left, text="Simuler", command=self.simulate).pack(anchor="w", pady=(0, 6))
        self.create_btn = ttk.Button(left, text="Créer l'employé à partir de cette simulation",
                                      command=self.create_employee, state="disabled")
        self.create_btn.pack(anchor="w")

        # --- Zone de résultat --------------------------------------------
        right = ttk.Frame(self)
        right.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        ttk.Label(right, text="Résultat de la simulation", font=("Segoe UI", 12, "bold")).pack(anchor="w")

        self.result_text = tk.Text(right, width=56, height=26, font=("Consolas", 10),
                                    state="disabled", relief="solid", borderwidth=1)
        self.result_text.pack(anchor="w", pady=(8, 0), fill="y")

    def _read_template(self):
        v = self.vars
        try:
            emp = Employee(
                numero=0,
                nom_prenoms=v["nom_prenoms"].get().strip() or "Simulation",
                periode="",
                salaire_base=0.0,
                heures_sup=float(v["heures_sup"].get() or 0),
                primes=float(v["primes"].get() or 0),
                indemnite_transport=float(v["indemnite_transport"].get() or 0),
                indemnite_logement=float(v["indemnite_logement"].get() or 0),
                indemnite_communication=float(v["indemnite_communication"].get() or 0),
                gratification=float(v["gratification"].get() or 0),
                autres_primes=float(v["autres_primes"].get() or 0),
                retenue_pret=float(v["retenue_pret"].get() or 0),
            )
            mois = int(float(v["mois"].get() or datetime.date.today().month))
        except ValueError:
            messagebox.showerror("Erreur de saisie", "Merci de vérifier les valeurs numériques saisies.")
            return None
        if not (1 <= mois <= 12):
            messagebox.showerror("Erreur de saisie", "Le mois doit être compris entre 1 et 12.")
            return None
        try:
            target = float(self.target_var.get().replace(" ", "").replace(",", "."))
        except ValueError:
            messagebox.showerror("Erreur de saisie", "Le « Net à payer souhaité » doit être un nombre.")
            return None
        if target <= 0:
            messagebox.showerror("Erreur de saisie", "Le « Net à payer souhaité » doit être positif.")
            return None
        return emp, mois, target

    def simulate(self):
        parsed = self._read_template()
        if parsed is None:
            return
        emp_template, mois, target = parsed
        params = self.app.config_data["params"]

        base, r = find_base_for_target_net(emp_template, params, target_net=target, mois=mois)
        self.last_result = r
        self.last_employee_template = replace(emp_template, salaire_base=base)
        self.create_btn.config(state="normal")

        def money(v):
            return f"{v:,.0f}".replace(",", " ") + " FCFA"

        ecart = r["net_a_payer"] - target
        lines = [
            f"Net à payer souhaité      : {money(target)}",
            f"Net à payer obtenu        : {money(r['net_a_payer'])}  (écart : {ecart:+.0f})",
            "",
            f"→ Salaire de base à payer : {money(base)}",
            "",
            "── Détail du bulletin obtenu ──────────────────",
            f"Heures supplémentaires     {money(r['heures_sup'])}",
            f"Primes                     {money(r['primes'])}",
            f"Indemnité Transport        {money(r['indemnite_transport'])}",
            f"Indemnité Logement         {money(r['indemnite_logement'])}",
            f"Indemnité Communication    {money(r['indemnite_communication'])}",
            f"Gratification              {money(r['gratification'])}",
            f"Autres Primes              {money(r['autres_primes'])}",
            "─────────────────────────────────────────────",
            f"Total Brut                 {money(r['total_brut'])}",
            "",
            f"CNSS Vieillesse (3,6%)      {money(r['cnss_vieillesse_salariale'])}",
        ]
        if r["trtv_preleve_ce_mois"] and r["trtv"]:
            lines.append(f"TRTV (annuelle, mois d'avril) {money(r['trtv'])}")
        lines += [
            f"Retenue prêt/avance         {money(r['retenue_pret'])}",
            "─────────────────────────────────────────────",
            f"NET À PAYER                 {money(r['net_a_payer'])}",
            "",
            f"ITS (charge patronale)      {money(r['its'])}",
            f"Coût total employeur        {money(r['cout_total_employeur'])}",
        ]

        self.result_text.config(state="normal")
        self.result_text.delete("1.0", "end")
        self.result_text.insert("1.0", "\n".join(lines))
        self.result_text.config(state="disabled")

    def create_employee(self):
        if self.last_employee_template is None:
            return
        emp = self.last_employee_template
        if not emp.nom_prenoms or emp.nom_prenoms == "Simulation":
            messagebox.showinfo("Nom requis",
                                 "Renseignez le champ « Nom & Prénoms » avant de créer l'employé.")
            return
        emp = replace(emp, numero=self.app.config_data["next_numero"],
                      periode=current_period_key(),
                      date_saisie=datetime.date.today().isoformat())
        self.app.config_data["employees"].append(emp.to_dict())
        self.app.config_data["next_numero"] += 1
        try:
            storage.save(self.app.config_data)
        except Exception as exc:
            messagebox.showerror("Erreur", f"Impossible d'enregistrer : {exc}")
            return
        self.employees_tab.refresh_tree()
        messagebox.showinfo("Employé créé",
                             f"« {emp.nom_prenoms} » a été ajouté à la liste des employés\n"
                             f"(période : {format_period(emp.periode)}).")


# ==========================================================================
# ONGLET PARAMÈTRES (Administrateur uniquement)
# ==========================================================================

class ParamsTab(ttk.Frame):
    def __init__(self, parent, app: App):
        super().__init__(parent)
        self.app = app
        params = app.config_data["params"]

        canvas = tk.Canvas(self, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.vars = {}
        row = 0

        def section(title):
            nonlocal row
            ttk.Label(inner, text=title, font=("Segoe UI", 11, "bold")).grid(
                row=row, column=0, columnspan=2, sticky="w", pady=(14, 4), padx=8)
            row += 1

        def field(label, key, value):
            nonlocal row
            ttk.Label(inner, text=label).grid(row=row, column=0, sticky="w", padx=8, pady=2)
            var = tk.StringVar(value=str(value))
            ttk.Entry(inner, textvariable=var, width=16).grid(row=row, column=1, sticky="w", padx=8, pady=2)
            self.vars[key] = var
            row += 1

        section("1. Cotisations CNSS")
        field("Cotisations Familiales — patronale (fixe)", "taux_cnss_allocations_familiales",
              params["taux_cnss_allocations_familiales"])
        field("Assurance Vieillesse — part patronale (fixe)", "taux_cnss_vieillesse_patronal",
              params["taux_cnss_vieillesse_patronal"])
        field("Assurance Vieillesse — part salariale (fixe)", "taux_cnss_vieillesse_salarial",
              params["taux_cnss_vieillesse_salarial"])
        ttk.Label(inner, text="Le taux « Risques Professionnels » (variable) se règle "
                               "désormais directement dans l'onglet « Saisie des employés »,\n"
                               "accessible aussi bien à l'Administrateur qu'à l'Utilisateur.",
                  foreground="#666", justify="left").grid(
            row=row, column=0, columnspan=2, sticky="w", padx=8, pady=(2, 4))
        row += 1

        section("2. VPS — Versement Patronal sur Salaires")
        field("Taux VPS (variable — 4% standard, 2% enseignement privé)", "taux_vps", params["taux_vps"])

        section("3. ITS — Impôt sur les Traitements et Salaires")
        ttk.Label(inner, text="Barème progressif par tranches, retenu sur le salarié.\n"
                               "(modifiable uniquement dans le fichier de données JSON — "
                               "voir le bouton ci-dessous)", foreground="#666", justify="left").grid(
            row=row, column=0, columnspan=2, sticky="w", padx=8)
        row += 1
        bareme_txt = "\n".join(
            f"  {int(b):,} F – {('+' if h is None else f'{int(h):,} F')} : {t*100:.0f}%".replace(",", " ")
            for (b, h, t) in params["bareme_its"])
        ttk.Label(inner, text=bareme_txt, foreground="#333", font=("Consolas", 9), justify="left").grid(
            row=row, column=0, columnspan=2, sticky="w", padx=8, pady=(2, 4))
        row += 1

        section("4. TRTV — Taxe Radiophonique et Télévisuelle (annuelle)")
        field("Montant Taxe Radiophonique", "trtv_radiophonique", params["trtv_radiophonique"])
        field("Montant Taxe Télévisuelle", "trtv_televisuelle", params["trtv_televisuelle"])
        field("Mois de prélèvement (1 à 12 — 4 = avril)", "trtv_mois_prelevement",
              params["trtv_mois_prelevement"])

        # --- En-tête / pied de page du bulletin de paie (PDF) ---------------
        section("5. En-tête et pied de page du bulletin de paie (PDF)")
        entete = self.app.config_data.get("bulletin_entete", {})
        self.text_vars = {}

        def text_field(label, key, value, width=40):
            nonlocal row
            ttk.Label(inner, text=label).grid(row=row, column=0, sticky="w", padx=8, pady=2)
            var = tk.StringVar(value=str(value or ""))
            ttk.Entry(inner, textvariable=var, width=width).grid(
                row=row, column=1, sticky="w", padx=8, pady=2)
            self.text_vars[key] = var
            row += 1

        text_field("Nom de l'entreprise (en-tête)", "nom_entreprise", entete.get("nom_entreprise", ""))
        text_field("IFU de l'entreprise", "ifu", entete.get("ifu", ""))
        text_field("Adresse", "adresse", entete.get("adresse", ""))
        text_field("Téléphone", "telephone", entete.get("telephone", ""))
        text_field("Email", "email", entete.get("email", ""))
        text_field("Note supplémentaire en en-tête (optionnel)", "note_entete", entete.get("note_entete", ""))

        ttk.Label(inner, text="Texte du pied de page (mentions légales, signature...)").grid(
            row=row, column=0, columnspan=2, sticky="w", padx=8, pady=(8, 2))
        row += 1
        self.footer_text = tk.Text(inner, width=60, height=4, wrap="word")
        self.footer_text.insert("1.0", self.app.config_data.get("bulletin_pied_de_page", ""))
        self.footer_text.grid(row=row, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 6))
        row += 1

        # --- Logo de l'entreprise ------------------------------------------
        ttk.Label(inner, text="Logo de l'entreprise (en-tête du bulletin PDF)").grid(
            row=row, column=0, columnspan=2, sticky="w", padx=8, pady=(10, 2))
        row += 1

        self._logo_base64 = entete.get("logo_base64")  # peut être None
        logo_name = entete.get("logo_filename", "")
        self._logo_filename = logo_name
        self.logo_status_var = tk.StringVar(
            value=f"Logo actuel : {logo_name}" if self._logo_base64 else "Aucun logo défini")
        ttk.Label(inner, textvariable=self.logo_status_var, foreground="#555").grid(
            row=row, column=0, columnspan=2, sticky="w", padx=8)
        row += 1

        logo_btns = ttk.Frame(inner)
        logo_btns.grid(row=row, column=0, columnspan=2, sticky="w", padx=8, pady=(2, 6))
        ttk.Button(logo_btns, text="Choisir un logo...", command=self.choose_logo).pack(side="left")
        ttk.Button(logo_btns, text="Retirer le logo", command=self.remove_logo).pack(side="left", padx=(8, 0))
        row += 1
        ttk.Label(inner, text="Formats acceptés : PNG ou JPG. Le logo apparaîtra en haut à\n"
                               "gauche de chaque bulletin de paie généré.",
                  foreground="#666", justify="left").grid(row=row, column=0, columnspan=2, sticky="w", padx=8)
        row += 1

        ttk.Button(inner, text="Ouvrir le dossier des données",
                   command=self.open_data_folder).grid(row=row, column=0, pady=16, padx=8, sticky="w")
        ttk.Button(inner, text="Enregistrer les paramètres",
                   command=self.save_params).grid(row=row, column=1, pady=16, padx=8, sticky="w")

    def choose_logo(self):
        path = filedialog.askopenfilename(
            title="Choisir un logo",
            filetypes=[("Images", "*.png *.jpg *.jpeg"), ("Tous les fichiers", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "rb") as f:
                raw = f.read()
        except Exception as exc:
            messagebox.showerror("Erreur", f"Impossible de lire le fichier : {exc}")
            return
        if len(raw) > 3_000_000:
            messagebox.showerror("Fichier trop volumineux",
                                  "Merci de choisir une image de moins de 3 Mo.")
            return
        import base64
        self._logo_base64 = base64.b64encode(raw).decode("ascii")
        filename = os.path.basename(path)
        self.logo_status_var.set(f"Logo sélectionné : {filename}  (cliquez sur « Enregistrer les paramètres »)")
        self._logo_filename = filename

    def remove_logo(self):
        self._logo_base64 = None
        self._logo_filename = ""
        self.logo_status_var.set("Aucun logo défini  (cliquez sur « Enregistrer les paramètres »)")

    def save_params(self):
        try:
            p = self.app.config_data["params"]
            v = self.vars
            p["taux_cnss_allocations_familiales"] = float(v["taux_cnss_allocations_familiales"].get())
            p["taux_cnss_vieillesse_patronal"] = float(v["taux_cnss_vieillesse_patronal"].get())
            p["taux_cnss_vieillesse_salarial"] = float(v["taux_cnss_vieillesse_salarial"].get())
            p["taux_vps"] = float(v["taux_vps"].get())
            p["trtv_radiophonique"] = float(v["trtv_radiophonique"].get())
            p["trtv_televisuelle"] = float(v["trtv_televisuelle"].get())
            mois_trtv = int(float(v["trtv_mois_prelevement"].get()))
            if not (1 <= mois_trtv <= 12):
                raise ValueError("mois TRTV hors plage")
            p["trtv_mois_prelevement"] = mois_trtv
        except ValueError:
            messagebox.showerror("Erreur", "Merci de vérifier les valeurs saisies (nombres attendus, "
                                            "mois TRTV entre 1 et 12).")
            return

        self.app.config_data["bulletin_entete"] = {
            "nom_entreprise": self.text_vars["nom_entreprise"].get().strip(),
            "ifu": self.text_vars["ifu"].get().strip(),
            "adresse": self.text_vars["adresse"].get().strip(),
            "telephone": self.text_vars["telephone"].get().strip(),
            "email": self.text_vars["email"].get().strip(),
            "note_entete": self.text_vars["note_entete"].get().strip(),
            "logo_base64": getattr(self, "_logo_base64", None),
            "logo_filename": getattr(self, "_logo_filename", ""),
        }
        self.app.config_data["bulletin_pied_de_page"] = self.footer_text.get("1.0", "end").strip()
        self.app.config_data["entreprise"] = self.text_vars["nom_entreprise"].get().strip() or "Mon Entreprise"

        storage.save(self.app.config_data)
        messagebox.showinfo("Enregistré", "Paramètres de paie mis à jour.")

    def open_data_folder(self):
        import subprocess, sys, os as _os
        path = storage.get_data_dir()
        try:
            if sys.platform.startswith("win"):
                _os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception:
            messagebox.showinfo("Dossier de données", path)


# ==========================================================================
# ONGLET SÉCURITÉ (Administrateur uniquement)
# ==========================================================================

class SecurityTab(ttk.Frame):
    def __init__(self, parent, app: App):
        super().__init__(parent)
        self.app = app

        frame = ttk.Frame(self)
        frame.pack(padx=20, pady=20, anchor="nw")

        ttk.Label(frame, text="Mot de passe Utilisateur du mois en cours",
                  font=("Segoe UI", 12, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        period = auth.current_period()
        current_pwd = auth.get_effective_user_password(app.config_data)
        ttk.Label(frame, text=f"Mois : {auth.period_label(period)}").grid(row=1, column=0, sticky="w")
        self.pwd_display = tk.StringVar(value=current_pwd)
        entry = ttk.Entry(frame, textvariable=self.pwd_display, width=20, state="readonly",
                           font=("Consolas", 12, "bold"))
        entry.grid(row=2, column=0, sticky="w", pady=6)
        ttk.Label(frame, text="(généré automatiquement — change chaque 1er du mois)",
                  foreground="#666").grid(row=3, column=0, columnspan=2, sticky="w")
        ttk.Label(frame, text="Propre à cette installation : communiquez ce code à l'utilisateur\n"
                               "de cet ordinateur à chaque changement de mois (téléphone, SMS...).",
                  foreground="#666", justify="left").grid(row=4, column=0, columnspan=2, sticky="w", pady=(4, 0))

        ttk.Separator(frame).grid(row=5, column=0, columnspan=2, sticky="ew", pady=16)

        ttk.Label(frame, text="Forcer un mot de passe Utilisateur pour ce mois-ci",
                  font=("Segoe UI", 11, "bold")).grid(row=6, column=0, columnspan=2, sticky="w")
        self.override_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.override_var, width=20).grid(row=7, column=0, sticky="w", pady=6)
        ttk.Button(frame, text="Appliquer", command=self.apply_override).grid(row=7, column=1, padx=8)
        ttk.Button(frame, text="Revenir à la génération automatique",
                   command=self.clear_override).grid(row=8, column=0, columnspan=2, sticky="w", pady=(0, 6))

        ttk.Separator(frame).grid(row=9, column=0, columnspan=2, sticky="ew", pady=16)

        ttk.Label(frame, text="Validité du logiciel",
                  font=("Segoe UI", 11, "bold")).grid(row=10, column=0, columnspan=2, sticky="w")
        current_expiration = expiration.get_effective_expiration(self.app.config_data)
        self.expiration_display = tk.StringVar(value=current_expiration.strftime("%d/%m/%Y"))
        ttk.Label(frame, text="Expire actuellement le :").grid(row=11, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(frame, textvariable=self.expiration_display, width=14, state="readonly",
                  font=("Consolas", 11, "bold")).grid(row=12, column=0, sticky="w", pady=4)

        ttk.Label(frame, text="Prolonger jusqu'au (JJ/MM/AAAA) :").grid(row=13, column=0, sticky="w", pady=(10, 0))
        self.extend_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.extend_var, width=14).grid(row=14, column=0, sticky="w", pady=4)
        ttk.Button(frame, text="Prolonger", command=self.extend_expiration).grid(row=14, column=1, padx=8)
        ttk.Label(frame, text="Le mot de passe Administrateur est fixe et ne peut pas être\n"
                               "changé depuis cette fenêtre.",
                  foreground="#666", justify="left").grid(row=15, column=0, columnspan=2, sticky="w", pady=(10, 0))

        ttk.Separator(frame).grid(row=16, column=0, columnspan=2, sticky="ew", pady=16)
        ttk.Label(frame, text=PAID_SOFTWARE_NOTICE, foreground="#008751",
                  font=("Segoe UI", 9, "italic")).grid(row=17, column=0, columnspan=2, sticky="w")

    def apply_override(self):
        pwd = self.override_var.get().strip()
        if not pwd:
            messagebox.showerror("Erreur", "Saisissez un mot de passe.")
            return
        period = auth.current_period()
        self.app.config_data.setdefault("user_password_overrides", {})[period] = pwd
        storage.save(self.app.config_data)
        self.pwd_display.set(pwd)
        messagebox.showinfo("Appliqué", f"Mot de passe Utilisateur forcé pour {auth.period_label(period)}.")

    def clear_override(self):
        period = auth.current_period()
        self.app.config_data.get("user_password_overrides", {}).pop(period, None)
        storage.save(self.app.config_data)
        auto_pwd = auth.get_effective_user_password(self.app.config_data)
        self.pwd_display.set(auto_pwd)
        messagebox.showinfo("Réinitialisé", "Le mot de passe Utilisateur est de nouveau généré automatiquement.")

    def extend_expiration(self):
        text = self.extend_var.get().strip()
        try:
            day, month, year = text.split("/")
            new_date = datetime.date(int(year), int(month), int(day))
        except (ValueError, TypeError):
            messagebox.showerror("Erreur", "Format attendu : JJ/MM/AAAA (ex : 31/12/2026).")
            return
        expiration.set_extension(self.app.config_data, new_date)
        try:
            storage.save(self.app.config_data)
        except Exception as exc:
            messagebox.showerror("Erreur", f"Impossible d'enregistrer : {exc}")
            return
        new_effective = expiration.get_effective_expiration(self.app.config_data)
        self.expiration_display.set(new_effective.strftime("%d/%m/%Y"))
        self.extend_var.set("")
        messagebox.showinfo("Prolongé", f"Accès valide jusqu'au {new_effective.strftime('%d/%m/%Y')}.")


# ==========================================================================

if __name__ == "__main__":
    app = App()
    app.mainloop()
