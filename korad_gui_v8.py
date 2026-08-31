import tkinter as tk
from tkinter import ttk, messagebox
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import serial
import serial.tools.list_ports
import time
import threading
import queue
import re
import json
import os

CONFIG_FILE = 'korad_config.json'
APP_VERSION = "v1.0"
APP_AUTHOR = "by Horde97"

# Czcionki "cyfrowe" - probujemy po kolei, uzywamy pierwszej dostepnej w systemie.
# OCR A Extended i Consolas sa standardowo w Windows; DS-Digital/Digital-7 to
# popularne czcionki 7-segmentowe, ktore uzytkownik moze doinstalowac.
DIGIT_FONT_CANDIDATES = [
    # Czcionki 7-segmentowe (jesli uzytkownik je doinstaluje - najlepszy efekt)
    "DSEG7 Classic", "DS-Digital", "Digital-7",
    # Czytelne, kanciaste czcionki dostepne standardowo w Windows
    "Bahnschrift SemiBold", "Bahnschrift", "Consolas", "Courier New",
]


def pick_digit_font():
    """Zwraca nazwe pierwszej dostepnej czcionki 'cyfrowej' z listy."""
    try:
        from tkinter import font as tkfont
        available = set(tkfont.families())
        for name in DIGIT_FONT_CANDIDATES:
            if name in available:
                return name
    except Exception as e:
        print("pick_digit_font error:", repr(e))
    return "Consolas"

# ===================== TLUMACZENIA / TRANSLATIONS =====================
TRANSLATIONS = {
    'pl': {
        'window_title': "KORAD KWR 102 - Zaawansowany Monitor",
        'comm': "PORT:",
        'baud': "Predkosc:",
        'connect': "Polacz",
        'connected': "Polaczono",
        'no_com': "BRAK PORTU",
        'com_error': "BLAD PORTU",
        'reset_settings': "RESET USTAWIEN",
        'settings': "Ustawienia",
        'waveform': "Wykres pradu",
        'power_meas': "Pomiary",
        'mode': "Tryb",
        'peak_i': "Rekord I / A",
        'reset_peak': "Reset rekordu",
        'setting': "Nastawy",
        'step': "Krok:",
        'output': "Wyjscie",
        'fast_call': "Szybkie profile (zapisywane lokalnie)",
        'profile': "Profil",
        'load': "Wczytaj",
        'save': "Zapisz",
        'saved': "Zapisano!",
        'protection': "Zabezpieczenia i konfiguracja",
        'lock': "BLOKADA",
        'compen': "Kompensacja",
        'priority': "Priorytet CV/CC",
        'enable': "Wlacz",
        'disable': "Wylacz",
        'active': "Aktywne",
        'reset_confirm_title': "Reset ustawien",
        'reset_confirm_msg': ("Na pewno zresetowac wszystkie ustawienia?\n"
                              "Wyjscie zostanie wylaczone, a napiecie/prad, blokady i "
                              "zabezpieczenia wroca do wartosci domyslnych."),
        'settings_title': "Ustawienia",
        'language': "Jezyk:",
        'polish': "Polski",
        'english': "Angielski",
        'about': "O programie",
        'version': "Wersja",
        'close': "Zamknij",
        'no_response': "Brak odpowiedzi na *IDN? - zasilacz nie odpowiada.",
        'device_info': "Podlaczone urzadzenie",
        'not_connected': "Nie polaczono",
        'serial_no': "Numer seryjny:",
    },
    'en': {
        'window_title': "KORAD KWR 102 - Advanced Monitor",
        'comm': "COMM:",
        'baud': "Baud Rate:",
        'connect': "Establish connection",
        'connected': "Connected",
        'no_com': "NO COM",
        'com_error': "COM ERROR",
        'reset_settings': "RESET SETTINGS",
        'settings': "Settings",
        'waveform': "Current Waveform",
        'power_meas': "Power Measurement",
        'mode': "Mode",
        'peak_i': "Peak I / A",
        'reset_peak': "Reset peak",
        'setting': "Setting",
        'step': "Step:",
        'output': "Output",
        'fast_call': "Fast Call - Profiles (saved locally)",
        'profile': "Profile",
        'load': "Load",
        'save': "Save",
        'saved': "Saved!",
        'protection': "Protection & Config",
        'lock': "LOCK",
        'compen': "Compen.",
        'priority': "CV/CC Priority",
        'enable': "Enable",
        'disable': "Disable",
        'active': "Active",
        'reset_confirm_title': "Reset settings",
        'reset_confirm_msg': ("Reset all settings?\n"
                              "The output will be turned off, and voltage/current, locks "
                              "and protections will return to default values."),
        'settings_title': "Settings",
        'language': "Language:",
        'polish': "Polish",
        'english': "English",
        'about': "About",
        'version': "Version",
        'close': "Close",
        'no_response': "No response to *IDN? - power supply not responding.",
        'device_info': "Connected device",
        'not_connected': "Not connected",
        'serial_no': "Serial number:",
    },
}


class ModernKoradGUI:
    def __init__(self, root):
        self.root = root
        self.lang = 'pl'  # domyslny jezyk, nadpisywany przez load_config()
        self.digit_font = pick_digit_font()

        self.root.geometry("1300x1000")
        self.root.configure(bg='#1e1e1e')
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        style = ttk.Style()
        style.theme_use('default')
        style.configure('TCombobox', fieldbackground='#333333', background='#2d2d2d', foreground='white')

        self.serial_conn = None
        self.is_output_on = False
        self.ovp_active = False
        self.ocp_active = False
        self.lock_active = False
        self.compen_active = False
        self.priority_cv = True

        self.running = False
        self.cmd_queue = queue.Queue()
        self.last_v = 0.0
        self.last_i = 0.0
        self.peak_i = 0.0
        self.start_time = 0
        # Pelna odpowiedz na *IDN? (z numerem seryjnym). Na pasku gornym
        # pokazujemy tylko model - numer seryjny jest widoczny wylacznie
        # w oknie Ustawien, zeby nie trafial przypadkiem na zrzuty ekranu.
        self.device_idn = None

        # Kontenery glowne
        self.top_bar = tk.Frame(root, bg='#2d2d2d', height=40)
        self.top_bar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        self.main_content = tk.Frame(root, bg='#1e1e1e')
        self.main_content.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.left_panel = tk.Frame(self.main_content, bg='#1e1e1e')
        self.left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        self.right_panel = tk.Frame(self.main_content, bg='#2d2d2d', width=320)
        self.right_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))

        # Inicjalizacja interfejsu
        self.setup_top_bar()
        self.setup_plot()
        self.setup_measurements()
        self.setup_controls()
        self.setup_fast_call()
        self.setup_right_panel()

        self.load_config()
        self.apply_language()

        self.x_data = []
        self.y_data = []

        self.update_ui()
        self.animate_plot()

    def t(self, key):
        """Zwraca tekst w aktualnie wybranym jezyku."""
        return TRANSLATIONS[self.lang].get(key, key)

    def setup_top_bar(self):
        self.lbl_comm = tk.Label(self.top_bar, text="COMM:", bg='#2d2d2d', fg='white')
        self.lbl_comm.pack(side=tk.LEFT, padx=5)
        available_ports = [port.device for port in serial.tools.list_ports.comports()]

        self.com_cb = ttk.Combobox(self.top_bar, values=available_ports, width=15)
        if available_ports: self.com_cb.set(available_ports[0])
        self.com_cb.pack(side=tk.LEFT, padx=5)

        self.lbl_baud = tk.Label(self.top_bar, text="Baud Rate:", bg='#2d2d2d', fg='white')
        self.lbl_baud.pack(side=tk.LEFT, padx=5)
        self.baud_cb = ttk.Combobox(self.top_bar, values=["9600", "38400", "57600", "115200"], width=8)
        self.baud_cb.set("115200")
        self.baud_cb.pack(side=tk.LEFT, padx=5)

        self.btn_connect = tk.Button(
            self.top_bar, text="Establish connection", bg='#007acc', fg='white',
            relief=tk.FLAT, command=self.toggle_connection, width=20
        )
        self.btn_connect.pack(side=tk.LEFT, padx=15)

        self.lbl_status = tk.Label(self.top_bar, text="", bg='#2d2d2d', fg='#ff8800')
        self.lbl_status.pack(side=tk.LEFT, padx=10)

        # Kolo zebate - ustawienia (jezyk, informacje o programie)
        self.btn_settings = tk.Button(
            self.top_bar, text="\u2699", bg='#2d2d2d', fg='white',
            relief=tk.FLAT, font=("Arial", 16), command=self.open_settings,
            activebackground='#444444', activeforeground='white', bd=0, cursor='hand2'
        )
        self.btn_settings.pack(side=tk.RIGHT, padx=(0, 10))

        self.btn_reset = tk.Button(
            self.top_bar, text="RESET USTAWIEN", bg='#8b2e2e', fg='white',
            relief=tk.FLAT, command=self.reset_settings
        )
        self.btn_reset.pack(side=tk.RIGHT, padx=10)

    def setup_plot(self):
        self.plot_frame = tk.LabelFrame(self.left_panel, text="Waveform", bg='#2d2d2d', fg='white', bd=1)
        self.plot_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(0, 5))

        self.fig = Figure(figsize=(6, 3), dpi=100, facecolor='#000000')
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor('#000000')
        self.ax.tick_params(colors='white')
        self.ax.grid(color='#333333', linestyle='-', linewidth=1)

        self.line, = self.ax.plot([], [], color='#33ff33', linewidth=2.5, solid_joinstyle='round')

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def make_tile(self, parent):
        """Tworzy 'mechaniczny' kafelek z ramka na pojedyncza wartosc."""
        outer = tk.Frame(parent, bg='#111111', bd=2, relief=tk.RIDGE)
        outer.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=5, pady=8)
        inner = tk.Frame(outer, bg='#252525', bd=1, relief=tk.SUNKEN)
        inner.pack(expand=True, fill=tk.BOTH, padx=3, pady=3)
        return inner

    def setup_measurements(self):
        self.meas_frame = tk.LabelFrame(self.left_panel, text="Power Measurement", bg='#2d2d2d', fg='white', bd=1)
        self.meas_frame.pack(side=tk.TOP, fill=tk.X, pady=5)

        labels = [("U / V", "#ff3333", "lbl_v"), ("I / A", "#33ff33", "lbl_i"), ("P / W", "#3399ff", "lbl_p")]
        for title, color, attr in labels:
            f = self.make_tile(self.meas_frame)
            tk.Label(f, text=title, fg="#888888", bg='#252525', font=("Arial", 12)).pack(pady=(6, 0))
            setattr(self, attr, tk.Label(f, text="00.000", fg=color, bg='#252525',
                                         font=(self.digit_font, 30, "bold")))
            getattr(self, attr).pack(pady=(0, 8))

        f = self.make_tile(self.meas_frame)
        self.lbl_mode_title = tk.Label(f, text="Mode", fg="#888888", bg='#252525', font=("Arial", 12))
        self.lbl_mode_title.pack(pady=(6, 0))
        self.lbl_mode = tk.Label(f, text="OFF", fg="#ff3333", bg='#252525',
                                 font=(self.digit_font, 26, "bold"))
        self.lbl_mode.pack(pady=(0, 8))

        # Rekord pradu (Peak I) - przetrwa restart programu, zapisywany do pliku
        f = self.make_tile(self.meas_frame)
        self.lbl_peak_title = tk.Label(f, text="Peak I / A", fg="#888888", bg='#252525', font=("Arial", 12))
        self.lbl_peak_title.pack(pady=(6, 0))
        self.lbl_peak = tk.Label(f, text="00.000", fg="#ffcc00", bg='#252525',
                                 font=(self.digit_font, 24, "bold"))
        self.lbl_peak.pack()
        self.btn_reset_peak = tk.Button(f, text="Reset", bg='#444444', fg='white', relief=tk.FLAT,
                                        font=("Arial", 8), command=self.reset_peak)
        self.btn_reset_peak.pack(pady=(2, 8))

    def setup_controls(self):
        self.ctrl_frame = tk.LabelFrame(self.left_panel, text="Setting", bg='#2d2d2d', fg='white', bd=1)
        self.ctrl_frame.pack(side=tk.TOP, fill=tk.X, pady=5)

        # Napiecie
        v_frame = self.make_tile(self.ctrl_frame)
        tk.Label(v_frame, text="U / V", fg="white", bg='#555555', font=("Arial", 14), width=12).pack(pady=(8, 0))

        v_inputs = tk.Frame(v_frame, bg='#252525')
        v_inputs.pack(pady=5)
        tk.Button(v_inputs, text=" - ", font=("Consolas", 14, "bold"), bg='#444444', fg='white', relief=tk.FLAT, command=lambda: self.adjust_value('v', -1)).pack(side=tk.LEFT, padx=2)
        self.set_v = tk.Entry(v_inputs, font=(self.digit_font, 20), bg='#1e1e1e', fg='#ff3333', justify='center', width=8)
        self.set_v.insert(0, "19.500")
        self.set_v.bind('<Return>', self.apply_settings)
        self.set_v.pack(side=tk.LEFT, padx=2)
        tk.Button(v_inputs, text=" + ", font=("Consolas", 14, "bold"), bg='#444444', fg='white', relief=tk.FLAT, command=lambda: self.adjust_value('v', 1)).pack(side=tk.LEFT, padx=2)

        v_step_f = tk.Frame(v_frame, bg='#252525')
        v_step_f.pack(pady=(0, 8))
        self.lbl_step_v = tk.Label(v_step_f, text="Step:", fg="#888888", bg='#252525')
        self.lbl_step_v.pack(side=tk.LEFT)
        self.step_v = tk.Entry(v_step_f, width=6, bg='#1e1e1e', fg='white', justify='center')
        self.step_v.insert(0, "1.000")
        self.step_v.pack(side=tk.LEFT)
        self.btn_save_step_v = tk.Button(v_step_f, text="Zapisz", bg='#444444', fg='white',
                                         relief=tk.FLAT, font=("Arial", 8),
                                         command=lambda: self.save_step('v'))
        self.btn_save_step_v.pack(side=tk.LEFT, padx=(4, 0))

        # Prad
        i_frame = self.make_tile(self.ctrl_frame)
        tk.Label(i_frame, text="I / A", fg="white", bg='#555555', font=("Arial", 14), width=12).pack(pady=(8, 0))

        i_inputs = tk.Frame(i_frame, bg='#252525')
        i_inputs.pack(pady=5)
        tk.Button(i_inputs, text=" - ", font=("Consolas", 14, "bold"), bg='#444444', fg='white', relief=tk.FLAT, command=lambda: self.adjust_value('i', -1)).pack(side=tk.LEFT, padx=2)
        self.set_i = tk.Entry(i_inputs, font=(self.digit_font, 20), bg='#1e1e1e', fg='#33ff33', justify='center', width=8)
        self.set_i.insert(0, "02.500")
        self.set_i.bind('<Return>', self.apply_settings)
        self.set_i.pack(side=tk.LEFT, padx=2)
        tk.Button(i_inputs, text=" + ", font=("Consolas", 14, "bold"), bg='#444444', fg='white', relief=tk.FLAT, command=lambda: self.adjust_value('i', 1)).pack(side=tk.LEFT, padx=2)

        i_step_f = tk.Frame(i_frame, bg='#252525')
        i_step_f.pack(pady=(0, 8))
        self.lbl_step_i = tk.Label(i_step_f, text="Step:", fg="#888888", bg='#252525')
        self.lbl_step_i.pack(side=tk.LEFT)
        self.step_i = tk.Entry(i_step_f, width=6, bg='#1e1e1e', fg='white', justify='center')
        self.step_i.insert(0, "0.100")
        self.step_i.pack(side=tk.LEFT)
        self.btn_save_step_i = tk.Button(i_step_f, text="Zapisz", bg='#444444', fg='white',
                                         relief=tk.FLAT, font=("Arial", 8),
                                         command=lambda: self.save_step('i'))
        self.btn_save_step_i.pack(side=tk.LEFT, padx=(4, 0))

        # Output ON/OFF
        btn_frame = self.make_tile(self.ctrl_frame)
        self.lbl_output = tk.Label(btn_frame, text="Output", fg="white", bg='#555555', font=("Arial", 14), width=10)
        self.lbl_output.pack(pady=(8, 0))
        self.btn_output = tk.Button(btn_frame, text="ON/OFF", font=("Arial", 16, "bold"), bg='#444444', fg='white', width=8, command=self.toggle_output)
        self.btn_output.pack(pady=(8, 14))

    def setup_fast_call(self):
        self.fc_frame = tk.LabelFrame(self.left_panel, text="Fast Call", bg='#2d2d2d', fg='white', bd=1)
        self.fc_frame.pack(side=tk.TOP, fill=tk.X, pady=5)

        self.fast_call_entries = []
        self.profile_boxes = []
        defaults = [("20.000", "16.000"), ("12.000", "27.500"), ("1.000", "2.000"),
                    ("5.000", "1.000"), ("5.000", "1.000")]

        for i in range(1, 6):
            box = tk.LabelFrame(self.fc_frame, text=f"Profil {i}", bg='#333333', fg='#cccccc', bd=1)
            box.grid(row=(i - 1) // 3, column=(i - 1) % 3, padx=8, pady=8, sticky='nsew')
            self.profile_boxes.append(box)

            row = tk.Frame(box, bg='#333333')
            row.pack(padx=8, pady=(6, 4))

            e_v = tk.Entry(row, width=7, font=("Consolas", 12), bg='#1e1e1e', fg='#ff3333', justify='center')
            e_v.insert(0, defaults[i - 1][0])
            e_v.pack(side=tk.LEFT)
            tk.Label(row, text="V", bg='#333333', fg='white').pack(side=tk.LEFT, padx=(2, 8))

            e_i = tk.Entry(row, width=7, font=("Consolas", 12), bg='#1e1e1e', fg='#33ff33', justify='center')
            e_i.insert(0, defaults[i - 1][1])
            e_i.pack(side=tk.LEFT)
            tk.Label(row, text="A", bg='#333333', fg='white').pack(side=tk.LEFT, padx=(2, 0))

            btn_row = tk.Frame(box, bg='#333333')
            btn_row.pack(pady=(0, 8))
            load_btn = tk.Button(btn_row, text="Load", bg='#007acc', fg='white', relief=tk.FLAT,
                                 width=9, command=lambda idx=i: self.call_profile(idx))
            load_btn.pack(side=tk.LEFT, padx=3)
            save_btn = tk.Button(btn_row, text="Save", bg='#444444', fg='white', relief=tk.FLAT,
                                 width=9, command=lambda idx=i: self.save_profile(idx))
            save_btn.pack(side=tk.LEFT, padx=3)

            self.fast_call_entries.append({'v': e_v, 'i': e_i, 'save_btn': save_btn, 'load_btn': load_btn})

        for col in range(3):
            self.fc_frame.grid_columnconfigure(col, weight=1)

    def setup_right_panel(self):
        self.lbl_protection = tk.Label(self.right_panel, text="Protection & Config", bg='#2d2d2d', fg='white', font=("Arial", 12, "bold"))
        self.lbl_protection.pack(pady=10)
        prot_frame = tk.Frame(self.right_panel, bg='#2d2d2d')
        prot_frame.pack(fill=tk.X, padx=10, pady=5)

        # OVP
        tk.Label(prot_frame, text="OVP (V)", bg='#2d2d2d', fg='#888888').grid(row=0, column=0, sticky='w')
        self.entry_ovp = tk.Entry(prot_frame, width=10, bg='#1e1e1e', fg='white', justify='center')
        self.entry_ovp.grid(row=1, column=0, pady=2)
        self.btn_ovp = tk.Button(prot_frame, text="Enable", bg='#444444', fg='white', relief=tk.FLAT, width=8, command=self.toggle_ovp)
        self.btn_ovp.grid(row=1, column=1, padx=5, pady=2)

        # OCP
        tk.Label(prot_frame, text="OCP (A)", bg='#2d2d2d', fg='#888888').grid(row=2, column=0, sticky='w', pady=(10, 0))
        self.entry_ocp = tk.Entry(prot_frame, width=10, bg='#1e1e1e', fg='white', justify='center')
        self.entry_ocp.grid(row=3, column=0, pady=2)
        self.btn_ocp = tk.Button(prot_frame, text="Enable", bg='#444444', fg='white', relief=tk.FLAT, width=8, command=self.toggle_ocp)
        self.btn_ocp.grid(row=3, column=1, padx=5, pady=2)

        # LOCK
        self.lbl_lock = tk.Label(prot_frame, text="LOCK", bg='#2d2d2d', fg='#888888')
        self.lbl_lock.grid(row=4, column=0, sticky='w', pady=(10, 0))
        self.btn_lock = tk.Button(prot_frame, text="Enable", bg='#444444', fg='white', relief=tk.FLAT, width=12, command=self.toggle_lock)
        self.btn_lock.grid(row=5, column=0, pady=2, sticky='w')

        # Compensation
        self.lbl_compen = tk.Label(prot_frame, text="Compen.", bg='#2d2d2d', fg='#888888')
        self.lbl_compen.grid(row=6, column=0, sticky='w', pady=(10, 0))
        self.btn_compen = tk.Button(prot_frame, text="Disable", bg='#444444', fg='white', relief=tk.FLAT, width=12, command=self.toggle_compen)
        self.btn_compen.grid(row=7, column=0, pady=2, sticky='w')

        # CV/CC Priority
        self.lbl_priority = tk.Label(prot_frame, text="CV/CC Priority", bg='#2d2d2d', fg='#888888')
        self.lbl_priority.grid(row=8, column=0, sticky='w', pady=(10, 0))
        self.btn_priority = tk.Button(prot_frame, text="CV", bg='#444444', fg='white', relief=tk.FLAT, width=12, command=self.toggle_priority)
        self.btn_priority.grid(row=9, column=0, pady=2, sticky='w')

    # ================= JEZYK =================

    def apply_language(self):
        """Podmienia wszystkie widoczne napisy na aktualnie wybrany jezyk."""
        t = self.t
        self.root.title(f"{t('window_title')}  {APP_VERSION}  {APP_AUTHOR}")

        self.lbl_comm.config(text=t('comm'))
        self.lbl_baud.config(text=t('baud'))
        self.btn_connect.config(text=t('connected') if self.running else t('connect'))
        self.btn_reset.config(text=t('reset_settings'))

        self.plot_frame.config(text=t('waveform'))
        self.meas_frame.config(text=t('power_meas'))
        self.lbl_mode_title.config(text=t('mode'))
        self.lbl_peak_title.config(text=t('peak_i'))
        self.btn_reset_peak.config(text=t('reset_peak'))

        self.ctrl_frame.config(text=t('setting'))
        self.lbl_step_v.config(text=t('step'))
        self.lbl_step_i.config(text=t('step'))
        self.btn_save_step_v.config(text=t('save'))
        self.btn_save_step_i.config(text=t('save'))
        self.lbl_output.config(text=t('output'))

        self.fc_frame.config(text=t('fast_call'))
        for idx, box in enumerate(self.profile_boxes, start=1):
            box.config(text=f"{t('profile')} {idx}")
        for entry in self.fast_call_entries:
            entry['load_btn'].config(text=t('load'))
            entry['save_btn'].config(text=t('save'))

        self.lbl_protection.config(text=t('protection'))
        self.lbl_lock.config(text=t('lock'))
        self.lbl_compen.config(text=t('compen'))
        self.lbl_priority.config(text=t('priority'))

        self.btn_ovp.config(text=t('active') if self.ovp_active else t('enable'))
        self.btn_ocp.config(text=t('active') if self.ocp_active else t('enable'))
        self.btn_lock.config(text=t('active') if self.lock_active else t('enable'))
        self.btn_compen.config(text=t('enable') if self.compen_active else t('disable'))

    def set_language(self, lang):
        if lang in TRANSLATIONS and lang != self.lang:
            self.lang = lang
            self.apply_language()
            self.save_config()

    def open_settings(self):
        t = self.t
        win = tk.Toplevel(self.root)
        win.title(t('settings_title'))
        win.configure(bg='#2d2d2d')
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()

        tk.Label(win, text=t('settings_title'), bg='#2d2d2d', fg='white',
                 font=("Arial", 14, "bold")).pack(pady=(15, 10), padx=30)

        lang_frame = tk.Frame(win, bg='#2d2d2d')
        lang_frame.pack(pady=5, padx=30, fill=tk.X)
        tk.Label(lang_frame, text=t('language'), bg='#2d2d2d', fg='#cccccc').pack(side=tk.LEFT)

        lang_var = tk.StringVar(value=self.lang)

        def on_lang_change():
            self.set_language(lang_var.get())
            win.destroy()
            self.open_settings()  # otwieramy ponownie, juz w nowym jezyku

        tk.Radiobutton(lang_frame, text=t('polish'), variable=lang_var, value='pl',
                       command=on_lang_change, bg='#2d2d2d', fg='white', selectcolor='#1e1e1e',
                       activebackground='#2d2d2d', activeforeground='white').pack(side=tk.LEFT, padx=8)
        tk.Radiobutton(lang_frame, text=t('english'), variable=lang_var, value='en',
                       command=on_lang_change, bg='#2d2d2d', fg='white', selectcolor='#1e1e1e',
                       activebackground='#2d2d2d', activeforeground='white').pack(side=tk.LEFT, padx=8)

        tk.Frame(win, bg='#444444', height=1).pack(fill=tk.X, padx=20, pady=15)

        # Informacje o podlaczonym urzadzeniu (w tym numer seryjny)
        tk.Label(win, text=t('device_info'), bg='#2d2d2d', fg='#cccccc',
                 font=("Arial", 11, "bold")).pack()
        if self.device_idn:
            model = self.device_idn.split("SN:")[0].strip() if "SN:" in self.device_idn else self.device_idn
            tk.Label(win, text=model, bg='#2d2d2d', fg='white',
                     font=("Arial", 10)).pack(pady=(6, 0))
            if "SN:" in self.device_idn:
                sn = self.device_idn.split("SN:")[1].strip()
                sn_row = tk.Frame(win, bg='#2d2d2d')
                sn_row.pack(pady=(2, 10))
                tk.Label(sn_row, text=t('serial_no'), bg='#2d2d2d', fg='#888888',
                         font=("Arial", 9)).pack(side=tk.LEFT, padx=(0, 5))
                tk.Label(sn_row, text=sn, bg='#2d2d2d', fg='#33ff33',
                         font=("Consolas", 10)).pack(side=tk.LEFT)
        else:
            tk.Label(win, text=t('not_connected'), bg='#2d2d2d', fg='#888888',
                     font=("Arial", 10, "italic")).pack(pady=(6, 10))

        tk.Frame(win, bg='#444444', height=1).pack(fill=tk.X, padx=20, pady=15)

        tk.Label(win, text=t('about'), bg='#2d2d2d', fg='#cccccc',
                 font=("Arial", 11, "bold")).pack()
        tk.Label(win, text="KORAD KWR 102 Monitor", bg='#2d2d2d', fg='white',
                 font=("Arial", 11)).pack(pady=(6, 0))
        tk.Label(win, text=f"{t('version')} {APP_VERSION}", bg='#2d2d2d', fg='#33ff33',
                 font=("Consolas", 12, "bold")).pack(pady=2)
        tk.Label(win, text=APP_AUTHOR, bg='#2d2d2d', fg='#ffcc00',
                 font=("Arial", 11, "italic")).pack(pady=(0, 10))

        tk.Button(win, text=t('close'), bg='#007acc', fg='white', relief=tk.FLAT,
                  width=12, command=win.destroy).pack(pady=(5, 18))

        win.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (win.winfo_width() // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (win.winfo_height() // 2)
        win.geometry(f"+{x}+{y}")

    # ================= KONFIGURACJA / PERSYSTENCJA =================

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    c = json.load(f)
                if 'lang' in c and c['lang'] in TRANSLATIONS:
                    self.lang = c['lang']
                if 'com' in c: self.com_cb.set(c['com'])
                if 'baud' in c: self.baud_cb.set(c['baud'])
                if 'v_set' in c:
                    self.set_v.delete(0, tk.END)
                    self.set_v.insert(0, c['v_set'])
                if 'i_set' in c:
                    self.set_i.delete(0, tk.END)
                    self.set_i.insert(0, c['i_set'])
                if 'step_v' in c:
                    self.step_v.delete(0, tk.END)
                    self.step_v.insert(0, c['step_v'])
                if 'step_i' in c:
                    self.step_i.delete(0, tk.END)
                    self.step_i.insert(0, c['step_i'])
                if 'peak_i' in c:
                    self.peak_i = float(c['peak_i'])
                    self.lbl_peak.config(text=f"{self.peak_i:06.3f}")
                if 'ovp_value' in c:
                    self.entry_ovp.delete(0, tk.END)
                    self.entry_ovp.insert(0, c['ovp_value'])
                if 'ocp_value' in c:
                    self.entry_ocp.delete(0, tk.END)
                    self.entry_ocp.insert(0, c['ocp_value'])
                self.ovp_active = c.get('ovp_active', False)
                self.ocp_active = c.get('ocp_active', False)
                self.lock_active = c.get('lock_active', False)
                self.compen_active = c.get('compen_active', False)
                self.priority_cv = c.get('priority_cv', True)
                if self.ovp_active: self.btn_ovp.config(bg='#5cb85c')
                if self.ocp_active: self.btn_ocp.config(bg='#5cb85c')
                if self.lock_active: self.btn_lock.config(bg='#5cb85c')
                if self.compen_active: self.btn_compen.config(bg='#5cb85c')
                self.btn_priority.config(text="CV" if self.priority_cv else "CC")
                profiles = c.get('profiles', [])
                for idx, prof in enumerate(profiles):
                    if idx < len(self.fast_call_entries):
                        entry = self.fast_call_entries[idx]
                        entry['v'].delete(0, tk.END); entry['v'].insert(0, prof.get('v', ''))
                        entry['i'].delete(0, tk.END); entry['i'].insert(0, prof.get('i', ''))
            except Exception as e:
                print("load_config error:", repr(e))

    def save_config(self):
        try:
            profiles = [{'v': e['v'].get(), 'i': e['i'].get()} for e in self.fast_call_entries]
            c = {
                'lang': self.lang,
                'com': self.com_cb.get(), 'baud': self.baud_cb.get(),
                'v_set': self.set_v.get(), 'i_set': self.set_i.get(),
                'step_v': self.step_v.get(), 'step_i': self.step_i.get(),
                'peak_i': self.peak_i,
                'profiles': profiles,
                'ovp_value': self.entry_ovp.get(),
                'ocp_value': self.entry_ocp.get(),
                'ovp_active': self.ovp_active,
                'ocp_active': self.ocp_active,
                'lock_active': self.lock_active,
                'compen_active': self.compen_active,
                'priority_cv': self.priority_cv,
            }
            with open(CONFIG_FILE, 'w') as f:
                json.dump(c, f, indent=2)
        except Exception as e:
            print("save_config error:", repr(e))

    def on_closing(self):
        self.running = False
        self.save_config()
        if self.serial_conn:
            try: self.serial_conn.close()
            except Exception: pass
        self.root.destroy()

    def queue_command(self, cmd):
        if self.running:
            self.cmd_queue.put(cmd)

    def adjust_value(self, param, sign):
        try:
            if param == 'v':
                curr = float(self.set_v.get())
                new_val = max(0.0, curr + (sign * float(self.step_v.get())))
                self.set_v.delete(0, tk.END); self.set_v.insert(0, f"{new_val:06.3f}")
            elif param == 'i':
                curr = float(self.set_i.get())
                new_val = max(0.0, curr + (sign * float(self.step_i.get())))
                self.set_i.delete(0, tk.END); self.set_i.insert(0, f"{new_val:06.3f}")
            # Kazde klikniecie +/- wysyla wartosc natychmiast, bez czekania na Enter
            self.apply_settings()
        except Exception as e:
            print("adjust_value error:", repr(e))

    # ================= FAST CALL / PROFILE =================

    def call_profile(self, idx):
        """Wczytuje profil: ustawia pola Setting i od razu wysyla VSET/ISET do zasilacza."""
        entry = self.fast_call_entries[idx - 1]
        try:
            v = float(entry['v'].get())
            i = float(entry['i'].get())
        except Exception as e:
            print("call_profile error:", repr(e))
            return

        self.set_v.delete(0, tk.END); self.set_v.insert(0, f"{v:06.3f}")
        self.set_i.delete(0, tk.END); self.set_i.insert(0, f"{i:06.3f}")
        self.apply_settings()

    def save_step(self, param):
        """Zapisuje wartosc kroku (+/-) na dysk, z krotkim potwierdzeniem."""
        self.save_config()
        btn = self.btn_save_step_v if param == 'v' else self.btn_save_step_i
        original_bg = btn.cget('bg')
        btn.config(text=self.t('saved'), bg='#5cb85c')
        self.root.after(900, lambda: btn.config(text=self.t('save'), bg=original_bg))

    def save_profile(self, idx):
        """Zapisuje aktualna zawartosc pol V/A tego profilu na dysk (przetrwa restart)."""
        self.save_config()
        entry = self.fast_call_entries[idx - 1]
        btn = entry['save_btn']
        original_bg = btn.cget('bg')
        btn.config(text=self.t('saved'), bg='#5cb85c')
        self.root.after(900, lambda: btn.config(text=self.t('save'), bg=original_bg))

    # ================= RESET =================

    def reset_settings(self):
        if not messagebox.askyesno(self.t('reset_confirm_title'), self.t('reset_confirm_msg')):
            return

        self.set_v.delete(0, tk.END); self.set_v.insert(0, "00.000")
        self.set_i.delete(0, tk.END); self.set_i.insert(0, "00.000")
        self.entry_ovp.delete(0, tk.END)
        self.entry_ocp.delete(0, tk.END)

        if self.running:
            self.queue_command("OUT:0")
            self.queue_command("VSET:0.000")
            self.queue_command("ISET:0.000")
            self.queue_command("OVP:OFF")
            self.queue_command("OCP:OFF")
            self.queue_command("LOCK:0")
            self.queue_command("COMP:0")
            self.queue_command("PRIORITY:0")

        self.is_output_on = False
        self.ovp_active = False
        self.ocp_active = False
        self.lock_active = False
        self.compen_active = False
        self.priority_cv = True

        self.btn_output.config(bg='#444444', fg='white')
        self.lbl_mode.config(text="OFF", fg="#ff3333")
        self.btn_ovp.config(text=self.t('enable'), bg='#444444')
        self.btn_ocp.config(text=self.t('enable'), bg='#444444')
        self.btn_lock.config(text=self.t('enable'), bg='#444444')
        self.btn_compen.config(text=self.t('disable'), bg='#444444')
        self.btn_priority.config(text="CV")
        self.save_config()

    def reset_peak(self):
        self.peak_i = 0.0
        self.lbl_peak.config(text="00.000")
        self.save_config()

    # ================= KOMUNIKACJA KORAD KWR102 (format zweryfikowany) =================
    # Zasilacz podlaczony bezposrednio (USB/RS232) NIE uzywa zadnego numeru ID w
    # komendach. Ponizsze formaty pochodza z analizy realnej komunikacji
    # zarejestrowanej z dzialajacym oficjalnym oprogramowaniem KORAD:
    #   VOUT? / IOUT? / VSET? / ISET? / STATUS? / *IDN?   -> odczyty
    #   OUT:1 / OUT:0                                      -> wyjscie ON/OFF
    #   VSET:<x.xxx> / ISET:<x.xxx>                        -> ustawienie (KROPKA)
    #   RCL:<1-5> / SAV:<1-5>                               -> pamiec szybka na zasilaczu
    #   LOCK:1 / LOCK:0                                     -> blokada panelu
    #   PRIORITY:0 (CV) / PRIORITY:1 (CC)                   -> priorytet
    #   OVP:ON / OVP:OFF, OVP:<x,xxx>                       -> OVP (PRZECINEK!)
    #   OCP:ON / OCP:OFF, OCP:<x,xxx>                       -> OCP (PRZECINEK!)

    def apply_settings(self, event=None):
        try:
            v = float(self.set_v.get())
            i = float(self.set_i.get())
            self.queue_command(f"VSET:{v:.3f}")
            self.queue_command(f"ISET:{i:.3f}")
            self.save_config()
        except Exception as e:
            print("apply_settings error:", repr(e))

    def toggle_output(self):
        if not self.running: return
        if not self.is_output_on:
            self.apply_settings()
            self.queue_command("OUT:1")
            self.is_output_on = True
            self.btn_output.config(bg='#5cb85c', fg='white')
            self.lbl_mode.config(text="ON", fg="#33ff33")
        else:
            self.queue_command("OUT:0")
            self.is_output_on = False
            self.btn_output.config(bg='#444444', fg='white')
            self.lbl_mode.config(text="OFF", fg="#ff3333")

    def toggle_ovp(self):
        if not self.running: return
        try:
            if not self.ovp_active:
                val = float(self.entry_ovp.get())
                val_str = f"{val:.3f}".replace('.', ',')  # zasilacz oczekuje przecinka
                self.queue_command(f"OVP:{val_str}")
                self.queue_command("OVP:ON")
                self.ovp_active = True
                self.btn_ovp.config(text=self.t('active'), bg='#5cb85c')
            else:
                self.queue_command("OVP:OFF")
                self.ovp_active = False
                self.btn_ovp.config(text=self.t('enable'), bg='#444444')
            self.save_config()
        except Exception as e:
            print("toggle_ovp error:", repr(e))

    def toggle_ocp(self):
        if not self.running: return
        try:
            if not self.ocp_active:
                val = float(self.entry_ocp.get())
                val_str = f"{val:.3f}".replace('.', ',')  # zasilacz oczekuje przecinka
                self.queue_command(f"OCP:{val_str}")
                self.queue_command("OCP:ON")
                self.ocp_active = True
                self.btn_ocp.config(text=self.t('active'), bg='#5cb85c')
            else:
                self.queue_command("OCP:OFF")
                self.ocp_active = False
                self.btn_ocp.config(text=self.t('enable'), bg='#444444')
            self.save_config()
        except Exception as e:
            print("toggle_ocp error:", repr(e))

    def toggle_lock(self):
        if not self.running: return
        self.lock_active = not self.lock_active
        if self.lock_active:
            self.queue_command("LOCK:1")
            self.btn_lock.config(text=self.t('active'), bg='#5cb85c')
        else:
            self.queue_command("LOCK:0")
            self.btn_lock.config(text=self.t('enable'), bg='#444444')
        self.save_config()

    def toggle_compen(self):
        # UWAGA: format tej komendy nie zostal potwierdzony realnym
        # przechwyceniem komunikacji - do zweryfikowania na urzadzeniu.
        if not self.running: return
        self.compen_active = not self.compen_active
        if self.compen_active:
            self.queue_command("COMP:1")
            self.btn_compen.config(text=self.t('enable'), bg='#5cb85c')
        else:
            self.queue_command("COMP:0")
            self.btn_compen.config(text=self.t('disable'), bg='#444444')
        self.save_config()

    def toggle_priority(self):
        if not self.running: return
        self.priority_cv = not self.priority_cv
        if self.priority_cv:
            self.queue_command("PRIORITY:0")  # 0 = priorytet napieciowy (CV)
            self.btn_priority.config(text="CV")
        else:
            self.queue_command("PRIORITY:1")  # 1 = priorytet pradowy (CC)
            self.btn_priority.config(text="CC")
        self.save_config()

    def toggle_connection(self):
        if self.running:
            self.running = False
            time.sleep(0.1)
            if self.serial_conn:
                try: self.serial_conn.close()
                except Exception: pass
            self.serial_conn = None
            self.device_idn = None
            self.btn_connect.config(text=self.t('connect'), bg='#007acc')
            self.lbl_mode.config(text="OFF", fg="#ff3333")
            self.lbl_status.config(text="")
            return

        port = self.com_cb.get().strip()
        if not port:
            self.btn_connect.config(text=self.t('no_com'), bg='#d9534f')
            return

        try:
            baud = int(self.baud_cb.get())
            self.serial_conn = serial.Serial(
                port=port, baudrate=baud, bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE,
                timeout=0.1, write_timeout=0.2, xonxoff=False, rtscts=False, dsrdtr=False
            )
            time.sleep(0.3)
            self.serial_conn.reset_input_buffer()
            self.serial_conn.reset_output_buffer()

            idn = self.get_parsed_string("*IDN?")
            if not idn:
                raise Exception(self.t('no_response'))
            self.device_idn = idn
            # Na pasku gornym ukrywamy numer seryjny - zostaje sam model
            model_only = idn.split("SN:")[0].strip() if "SN:" in idn else idn
            self.lbl_status.config(text=model_only, fg='#33ff33')

            self.running = True
            self.btn_connect.config(text=self.t('connected'), bg='#5cb85c')
            self.start_time = time.time()
            self.x_data, self.y_data = [], []

            threading.Thread(target=self.serial_worker_thread, daemon=True).start()

            # Przywracamy zapisane ustawienia na zasilaczu (bez wlaczania wyjscia -
            # to musi zrobic uzytkownik recznie, dla bezpieczenstwa)
            self.apply_settings()
            self.queue_command("LOCK:1" if self.lock_active else "LOCK:0")
            self.queue_command("PRIORITY:0" if self.priority_cv else "PRIORITY:1")
            self.queue_command("COMP:1" if self.compen_active else "COMP:0")
            if self.ovp_active and self.entry_ovp.get().strip():
                try:
                    val_str = f"{float(self.entry_ovp.get()):.3f}".replace('.', ',')
                    self.queue_command(f"OVP:{val_str}")
                    self.queue_command("OVP:ON")
                except Exception:
                    pass
            if self.ocp_active and self.entry_ocp.get().strip():
                try:
                    val_str = f"{float(self.entry_ocp.get()):.3f}".replace('.', ',')
                    self.queue_command(f"OCP:{val_str}")
                    self.queue_command("OCP:ON")
                except Exception:
                    pass

            # POPRAWKA: zasilacz potrafi zignorowac pierwsza komende wyslana
            # tuz po nawiazaniu polaczenia (najczesciej wlasnie VSET, przez co
            # napiecie na wyswietlaczu nie zmienialo sie az do recznego
            # klikniecia +/- lub ON/OFF). Powtarzamy nastawy po chwili.
            self.root.after(600, self.apply_settings)

        except Exception as e:
            print("SERIAL ERROR:", repr(e))
            self.running = False
            if self.serial_conn:
                try: self.serial_conn.close()
                except Exception: pass
            self.serial_conn = None
            self.btn_connect.config(text=self.t('com_error'), bg='#d9534f')
            self.lbl_status.config(text=str(e), fg='#ff3333')

    def send_command(self, command):
        if not self.serial_conn: return
        try:
            packet = (command + "\r").encode("ascii")
            print("TX:", repr(packet))
            self.serial_conn.write(packet)
            self.serial_conn.flush()
        except Exception as e:
            print("SEND ERROR:", repr(e))

    def get_parsed_string(self, query, wait=0.3):
        """Wysyla zapytanie i zwraca surowa odpowiedz tekstowa (albo None)."""
        if not self.serial_conn: return None
        try:
            packet = (query + "\r").encode("ascii")
            self.serial_conn.reset_input_buffer()
            self.serial_conn.write(packet)
            self.serial_conn.flush()
            time.sleep(wait)
            if self.serial_conn.in_waiting:
                resp = self.serial_conn.read(self.serial_conn.in_waiting).decode("ascii", errors="ignore").strip()
                return resp if resp else None
        except Exception as e:
            print("QUERY ERROR:", repr(e))
        return None

    def get_parsed_value(self, query):
        resp = self.get_parsed_string(query, wait=0.05)
        if resp:
            match = re.search(r"[-+]?\d+(?:[.,]\d+)?", resp)
            if match:
                return float(match.group().replace(',', '.'))
        return None

    def serial_worker_thread(self):
        while self.running and self.serial_conn and self.serial_conn.is_open:
            try:
                while not self.cmd_queue.empty():
                    cmd = self.cmd_queue.get()
                    self.send_command(cmd)
                    time.sleep(0.05)

                v_out = self.get_parsed_value("VOUT?")
                if v_out is not None: self.last_v = v_out

                i_out = self.get_parsed_value("IOUT?")
                if i_out is not None:
                    self.last_i = i_out
                    if i_out > self.peak_i:
                        self.peak_i = i_out
                        self.root.after(0, lambda: self.lbl_peak.config(text=f"{self.peak_i:06.3f}"))
                        self.save_config()

            except Exception as e:
                print("WORKER THREAD ERROR:", repr(e))
                time.sleep(0.2)
            time.sleep(0.08)

    def update_ui(self):
        if self.running:
            actual_p = self.last_v * self.last_i
            self.lbl_v.config(text=f"{self.last_v:06.3f}")
            self.lbl_i.config(text=f"{self.last_i:06.3f}")
            self.lbl_p.config(text=f"{actual_p:05.2f}")
        self.root.after(250, self.update_ui)

    def animate_plot(self):
        # Odswiezanie wykresu ~12 klatek/s zamiast 60 - matplotlib jest kosztowny
        # przy przerysowaniu, a przy 60 FPS okno przycinalo sie podczas
        # przesuwania mysza. Dla wykresu pradu 12 FPS jest w pelni plynne.
        if self.running:
            current_time = time.time() - self.start_time
            self.x_data.append(current_time)
            self.y_data.append(self.last_i)

            window_size = 20.0
            cutoff = current_time - window_size - 2.0
            while len(self.x_data) > 1 and self.x_data[0] < cutoff:
                self.x_data.pop(0)
                self.y_data.pop(0)

            # Wygladzenie linii metoda sumy prefiksowej - liniowe zamiast
            # przeliczania kazdego okna od nowa. Nie wplywa na odczyty
            # liczbowe (Peak I, U/I/P), ktore licza sie z surowych danych.
            n = len(self.y_data)
            if n >= 5:
                prefix = [0.0] * (n + 1)
                for idx, val in enumerate(self.y_data):
                    prefix[idx + 1] = prefix[idx] + val
                y_plot = []
                for idx in range(n):
                    lo = idx - 2 if idx - 2 > 0 else 0
                    hi = idx + 3 if idx + 3 < n else n
                    y_plot.append((prefix[hi] - prefix[lo]) / (hi - lo))
            else:
                y_plot = list(self.y_data)

            self.line.set_data(self.x_data, y_plot)

            x_max = max(window_size, current_time)
            self.ax.set_xlim(x_max - window_size, x_max)

            # Automatyczne skalowanie osi Y - przeskalowujemy tylko gdy zakres
            # realnie sie zmienil, zeby nie wymuszac zbednych przerysowan.
            if y_plot:
                top = max(max(y_plot) * 1.15, 0.5)
                current_top = self.ax.get_ylim()[1]
                if abs(top - current_top) > current_top * 0.05:
                    self.ax.set_ylim(0, top)

            self.canvas.draw_idle()

        self.root.after(80, self.animate_plot)


if __name__ == "__main__":
    root = tk.Tk()
    app = ModernKoradGUI(root)
    root.mainloop()
