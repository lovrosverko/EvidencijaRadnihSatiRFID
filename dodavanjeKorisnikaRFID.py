import tkinter as tk
from tkinter import messagebox
import serial
import serial.tools.list_ports
import threading
import queue
import time
import datetime # Nije direktno potrebno, ali često korisno
import gspread
#from google.oauth2.service_account import Credentials
import logging
import sys
# --- Klasa za upravljanje Google Sheetsom ---
import pygsheets # Nova biblioteka

# --- Konfiguracija Aplikacije ---

# Google Sheets konfiguracija
GOOGLE_SHEET_ID = '1lZ8ACfW_8cC9AorqiwdElzTpmLkepkD48FjOadPPpGg'
SERVICE_ACCOUNT_KEY_PATH = "C:\\Users\\lovro\\Documents\\Moj Python\\datoteke\\rfid-evidencija-0185dd21ce8d.json" # Npr. 'service_account.json'
ZAPOSLENICI_SHEET_NAME = 'Zaposlenici' # Naziv lista s podacima o zaposlenicima

# Serijska komunikacija konfiguracija
SERIAL_PORT = 'COM4' # Prilagodite ako je potrebno (na Windowsima npr. 'COM3')
SERIAL_BAUDRATE = 9600
SERIAL_TIMEOUT = 1 # Sekunde

# Logiranje konfiguracija
LOG_FILE = 'enrollment_app.log'
LOG_LEVEL = logging.DEBUG # DEBUG, INFO, WARNING, ERROR, CRITICAL

# --- Postavljanje Logiranja ---
logging.basicConfig(filename=LOG_FILE, level=LOG_LEVEL,
                    format='%(asctime)s - %(levelname)s - %(message)s')

class GoogleSheetsManager:
    def __init__(self, sheet_id, key_path, zaposlenici_sheet_name):
        self.sheet_id = sheet_id
        self.key_path = key_path
        self.zaposlenici_sheet_name = zaposlenici_sheet_name
        self.gc = None # gc će sada biti pygsheets klijent
        self._authorize()

    def _authorize(self):
        """Autentifikacija s Google Sheets API-jem koristeći Service Account za pygsheets."""
        try:
            # Autentifikacija za pygsheets koristeći Service Account JSON ključ
            self.gc = pygsheets.authorize(service_file=self.key_path)
            logging.info("GSManager: Uspješna autentifikacija s Google Sheetsom (pygsheets).")
        except Exception as e:
            logging.error(f"GSManager: Greška pri autentifikaciji s Google Sheetsom (pygsheets): {e}")
            self.gc = None
            raise # Ponovno baci iznimku kako bi se prekinuo rad ako autentifikacija ne uspije

    def add_new_zaposlenik(self, ime, prezime, uid_kartice):
        """Dodaje novog zaposlenika u list 'Zaposlenici' u Google Sheetu."""
        if not self.gc: 
            logging.error("GSManager: Google Sheets nije autoriziran. Ne mogu dodati zaposlenika.")
            return False, "Nema veze s Google Sheetsom. Provjerite log."
        try:
            logging.debug(f"DEBUG: Tip self.gc (u add_new_zaposlenik): {type(self.gc)}")
            logging.debug(f"DEBUG: Atributi self.gc: {dir(self.gc)}")
            logging.debug(f"DEBUG: self.gc ima open_by_id? {hasattr(self.gc, 'open_by_id')}")
            # Otvaranje radne knjige po ID-u
            workbook = self.gc.open_by_key(self.sheet_id)
            zaposlenici_sheet = workbook.worksheet_by_title(self.zaposlenici_sheet_name) # pygsheets koristi worksheet_by_title
            
            # Provjeri postoji li već UID u tablici
            # Dohvati sve UID-ove iz prvog stupca (indeks 1)
            # pygsheets.get_col(1, include_tailing_empty=False) vraća list vrijednosti iz stupca
            uids_in_sheet = zaposlenici_sheet.get_col(1, include_tailing_empty=False, returnas='matrix') # returnas='matrix' vraća list listi, pa dohvatimo prve elemente
            uids_in_sheet = [item[0] for item in uids_in_sheet] # Pretvorimo u list stringova
            
            # Preskoči prvo zaglavlje stupca ako postoji
            if len(uids_in_sheet) > 0 and uids_in_sheet[0].lower() == 'uid': # Provjera da li je prvi element "UID"
                uids_in_sheet = uids_in_sheet[1:] # Ukloni zaglavlje


            if uid_kartice in uids_in_sheet:
                logging.warning(f"GSManager: UID {uid_kartice} već postoji u tablici zaposlenika. Nije dodan.")
                return False, f"UID '{uid_kartice}' već postoji. Zaposlenik nije dodan."

            # Dodaj novi redak u list Zaposlenici
            # Redoslijed mora odgovarati stupcima u Google Sheetu: UID, Ime, Prezime
            new_row = [uid_kartice, ime, prezime] 
            zaposlenici_sheet.append_table(values=new_row, start='A1', dimension='ROWS', overwrite=False) # append_table za dodavanje reda
            
            logging.info(f"GSManager: Uspješno dodan zaposlenik: {ime} {prezime} ({uid_kartice}) (pygsheets)")
            return True, "Zaposlenik uspješno dodan!"
        except Exception as e:
            logging.error(f"GSManager: Greška pri dodavanju zaposlenika (pygsheets): {e}")
            return False, f"Greška pri dodavanju zaposlenika: {e}. Provjerite log."

    # Metoda za dohvat statusa korisnika iz glavne aplikacije (nije potrebna za ovu Enrollment app)
    # def get_current_user_status_for_day(self, uid, date_str):
    #     pass 

    # Metoda za ažuriranje dnevnog zapisa iz glavne aplikacije (nije potrebna za ovu Enrollment app)
    # def update_daily_record(self, user_info, current_date_str, action_type, new_status):
    #     pass

    # Metoda za dohvat mjesečnih podataka iz glavne aplikacije (nije potrebna za ovu Enrollment app)
    # def get_monthly_data(self, year, month):
    #     pass

# --- Klasa za serijsku komunikaciju (u zasebnoj niti) ---
class SerialMonitorThread(threading.Thread):
    def __init__(self, port, baudrate, timeout, data_queue):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.data_queue = data_queue # Red za slanje primljenih podataka GUI-ju
        self.ser = None
        self.running = True
        self.reconnect_delay = 3 # Sekunde prije ponovnog pokušaja spajanja

    def run(self):
        logging.info(f"SerialThread: Pokrenuta serijska nit za port {self.port}...")
        while self.running:
            if not self.ser or not self.ser.is_open:
                logging.warning(f"SerialThread: Pokušavam se spojiti na serijski port {self.port}...")
                try:
                    self.ser = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
                    logging.info(f"SerialThread: Uspješno spojen na serijski port {self.port}.")
                except serial.SerialException as e:
                    logging.error(f"SerialThread: Greška pri spajanju na serijski port: {e}. Pokušavam ponovno za {self.reconnect_delay}s.")
                    time.sleep(self.reconnect_delay)
                    continue
            
            try:
                if self.ser.in_waiting > 0:
                    line = self.ser.readline().decode('utf-8').strip()
                    if line.startswith("UID:"):
                        uid = line[4:] # Izdvoji UID nakon "UID:"
                        logging.info(f"SerialThread: Primljen UID: {uid}")
                        self.data_queue.put(uid) # Stavi UID u red za GUI obradu
                    else:
                        logging.debug(f"SerialThread: Primljena nepoznata serijska poruka: '{line}'") # Debug jer nije UID
            except serial.SerialException as e:
                logging.error(f"SerialThread: Greška u serijskoj komunikaciji (veza izgubljena?): {e}. Zatvaram port i pokušavam ponovno.")
                if self.ser and self.ser.is_open:
                    self.ser.close()
                self.ser = None # Označi da je port zatvoren i treba ga ponovno otvoriti
            except Exception as e:
                logging.error(f"SerialThread: Neočekivana greška u serijskoj niti: {e}")
            
            time.sleep(0.05) # Mala pauza kako bi se spriječilo preopterećenje CPU-a

    def stop(self):
        """Metoda za sigurno zaustavljanje serijske niti."""
        logging.info("SerialThread: Zaustavljam serijsku nit.")
        self.running = False
        if self.ser and self.ser.is_open:
            self.ser.close()

# --- Glavna GUI aplikacija za upis korisnika (Tkinter) ---
class UserEnrollmentApp(tk.Tk):
    def __init__(self, serial_port, baudrate, gs_manager):
        super().__init__()
        self.gs_manager = gs_manager
        self.title("Dodavanje Novog Zaposlenika - RFID")
        self.geometry("600x400") # Možete prilagoditi veličinu prozora

        # UI elementi
        self.create_widgets()
        self.display_message("Unesite ime i prezime, pa prinesite karticu...", "blue")

        # Red za komunikaciju iz serijske niti
        self.rfid_queue = queue.Queue()
        self.serial_thread = SerialMonitorThread(serial_port, baudrate, SERIAL_TIMEOUT, self.rfid_queue)
        self.serial_thread.start()

        # Periodično provjerava red za nove UID-ove (Tkinter after metoda ne blokira GUI)
        self.after(100, self.check_rfid_queue)

    def create_widgets(self):
        # Frame za unose
        input_frame = tk.Frame(self, padx=10, pady=10)
        input_frame.pack(pady=20)

        # Ime
        tk.Label(input_frame, text="Ime:", font=("Helvetica", 14)).grid(row=0, column=0, sticky="w", pady=5)
        self.ime_entry = tk.Entry(input_frame, font=("Helvetica", 14), width=30)
        self.ime_entry.grid(row=0, column=1, padx=10, pady=5)

        # Prezime
        tk.Label(input_frame, text="Prezime:", font=("Helvetica", 14)).grid(row=1, column=0, sticky="w", pady=5)
        self.prezime_entry = tk.Entry(input_frame, font=("Helvetica", 14), width=30)
        self.prezime_entry.grid(row=1, column=1, padx=10, pady=5)

        # UID Kartice
        tk.Label(input_frame, text="UID Kartice:", font=("Helvetica", 14)).grid(row=2, column=0, sticky="w", pady=5)
        # uid_entry se inicijalizira kao read-only
        self.uid_entry = tk.Entry(input_frame, font=("Helvetica", 14), width=30, state=tk.DISABLED) 
        self.uid_entry.grid(row=2, column=1, padx=10, pady=5)
        # Mala uputa za korisnika
        tk.Label(input_frame, text="(Prinesite karticu RFID čitaču da se UID automatski popuni)", font=("Helvetica", 10), fg="gray", wraplength=350).grid(row=3, column=1, sticky="w", padx=10)

        # Gumbi
        button_frame = tk.Frame(self, pady=10)
        button_frame.pack()

        self.add_button = tk.Button(button_frame, text="DODAJ ZAPOSLENIKA", font=("Helvetica", 16),
                                    command=self.add_user, width=25, height=2, bg="#4CAF50", fg="white") # Zeleni gumb
        self.add_button.pack(side=tk.LEFT, padx=10)

        self.clear_button = tk.Button(button_frame, text="NOVI UNOS", font=("Helvetica", 16),
                                     command=self.clear_fields, width=25, height=2, bg="#2196F3", fg="white") # Plavi gumb
        self.clear_button.pack(side=tk.LEFT, padx=10)
        
        # Područje za poruke
        self.message_label = tk.Label(self, text="", font=("Helvetica", 14), wraplength=550)
        self.message_label.pack(pady=10)

    def display_message(self, msg, color="black"):
        """Prikazuje poruku korisniku u UI-ju."""
        self.message_label.config(text=msg, fg=color)
        logging.info(f"GUI poruka: {msg}")

    def check_rfid_queue(self):
        """Periodično provjerava red za nove UID-ove s RFID čitača."""
        try:
            uid = self.rfid_queue.get_nowait() # Pokušaj dobiti UID bez čekanja
            self.populate_uid_field(uid)
        except queue.Empty:
            pass # Nema novih podataka, samo nastavi
        self.after(100, self.check_rfid_queue) # Zakazivanje ponovne provjere za 100ms

    def populate_uid_field(self, uid):
        """Popunjava UID polje u UI-ju s očitanim UID-om."""
        # Omogući polje privremeno za upis, pa ga vrati na read-only
        self.uid_entry.config(state=tk.NORMAL)
        self.uid_entry.delete(0, tk.END)
        self.uid_entry.insert(0, uid)
        self.uid_entry.config(state=tk.DISABLED)
        self.display_message(f"UID {uid} očitan! Sada popunite ime i prezime i kliknite 'DODAJ ZAPOSLENIKA'.", "green")
        logging.info(f"UID polje popunjeno s: {uid}")

    def add_user(self):
        """Dohvaća podatke iz polja i pokušava dodati zaposlenika u Google Sheets."""
        ime = self.ime_entry.get().strip()
        prezime = self.prezime_entry.get().strip()
        uid_kartice = self.uid_entry.get().strip()

        if not ime or not prezime or not uid_kartice:
            self.display_message("Greška: Ime, prezime i UID kartice moraju biti popunjeni!", "red")
            return

        logging.info(f"Pokušavam dodati zaposlenika: {ime} {prezime} ({uid_kartice})")
        
        # Poziv funkcije Google Sheets Managera
        success, msg = self.gs_manager.add_new_zaposlenik(ime, prezime, uid_kartice)

        if success:
            self.display_message(f"Zaposlenik '{ime} {prezime}' uspješno dodan!", "green")
            self.clear_fields() # Očisti polja za novi unos
        else:
            self.display_message(f"Greška pri dodavanju zaposlenika: {msg}", "red")

    def clear_fields(self):
        """Briše sadržaj svih tekstualnih polja."""
        self.ime_entry.delete(0, tk.END)
        self.prezime_entry.delete(0, tk.END)
        # UID polje treba privremeno omogućiti za brisanje
        self.uid_entry.config(state=tk.NORMAL)
        self.uid_entry.delete(0, tk.END)
        self.uid_entry.config(state=tk.DISABLED) # Vrati na read-only
        self.display_message("Polja očišćena. Unesite novog zaposlenika...", "blue")
        logging.info("Polja aplikacije očišćena za novi unos.")

    def on_closing(self):
        """Rukuje gašenjem aplikacije i zaustavlja serijsku nit."""
        logging.info("Aplikacija za upis korisnika se gasi. Zaustavljam serijsku nit.")
        self.serial_thread.stop()
        self.destroy()

# --- Glavna izvršna logika ---
if __name__ == "__main__":
    logging.info("Aplikacija za upis korisnika se pokreće...")
    
    # Automatska detekcija serijskog porta
    actual_serial_port = SERIAL_PORT
    if not actual_serial_port: # Ako SERIAL_PORT u konfiguraciji nije specificiran (prazan)
        logging.info("Pokušavam automatski detektirati serijski port...")
        ports = serial.tools.list_ports.comports()
        found_port = None
        for p in ports:
            # Heuristička pretraga za Arduino/Dasduino
            # Možete dodati 'Arduino' in p.description za precizniju pretragu na nekim OS-ima
            # npr. if 'Arduino' in p.description or ('ACM' in p.device or 'USB' in p.device):
            if 'ACM' in p.device or 'USB' in p.device or 'COM' in p.device: 
                found_port = p.device
                break
        
        if found_port:
            actual_serial_port = found_port
            logging.info(f"Automatski detektiran serijski port: {actual_serial_port}")
        else:
            logging.error("AUTOMATSKA DETEKCIJA: Nije pronađen kompatibilan serijski port. Aplikacija se neće moći spojiti na RFID čitač.")
            messagebox.showerror("Greška porta", "Nije pronađen serijski port za Dasduino/RFID čitač. Provjerite da je spojen i da je driver instaliran.")
            sys.exit(1) # Izađite iz aplikacije ako port nije pronađen

    elif actual_serial_port: # Ako je port eksplicitno definiran u konfiguraciji
        logging.info(f"Koristim konfigurirani serijski port: {actual_serial_port}")
        # Ovdje možete dodati provjeru da li taj port uopće postoji (npr. provjerom u serial.tools.list_ports.comports())
        # To trenutno nije implementirano za eksplicitno definirane portove, ali je dobra praksa.

    try:
        # Inicijaliziraj Google Sheets Manager
        # Ovo će pokušati autentifikaciju; ako ne uspije, izbacit će iznimku i zaustaviti aplikaciju
        gs_manager = GoogleSheetsManager(GOOGLE_SHEET_ID, SERVICE_ACCOUNT_KEY_PATH, ZAPOSLENICI_SHEET_NAME)
        
        # Kreiraj i pokreni GUI aplikaciju
        app = UserEnrollmentApp(actual_serial_port, SERIAL_BAUDRATE, gs_manager)
        app.protocol("WM_DELETE_WINDOW", app.on_closing) # Osiguraj čisto gašenje niti pri zatvaranju prozora
        app.mainloop()

    except Exception as e:
        # Hvata sve kritične greške koje se mogu dogoditi prije ili tijekom pokretanja aplikacije
        logging.critical(f"Kritična greška pri pokretanju aplikacije za upis korisnika: {e}", exc_info=True) # exc_info=True za potpuni traceback
        messagebox.showerror("Kritična greška", f"Aplikacija se nije mogla pokrenuti. Provjerite log datoteku ({LOG_FILE}). Greška: {e}")
        sys.exit(1) # Izađite iz aplikacije