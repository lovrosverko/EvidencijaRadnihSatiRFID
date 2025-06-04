import sys
import tkinter as tk
from tkinter import messagebox
import serial
import serial.tools.list_ports
import threading
import queue
import time
import datetime
import pygsheets # Koristimo pygsheets
from google.oauth2.service_account import Credentials # Potrebno za ServiceAccountCredentials
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- Konfiguracija Aplikacije ---
# Google Sheets konfiguracija
GOOGLE_SHEET_ID = '1lZ8ACfW_8cC9AorqiwdElzTpmLkepkD48FjOadPPpGg'
SERVICE_ACCOUNT_KEY_PATH = "C:\\Users\\lovro\\Documents\\Moj Python\\datoteke\\rfid-evidencija-0185dd21ce8d.json" # Npr. 'service_account.json'
ZAPOSLENICI_SHEET_NAME = 'Zaposlenici' # Naziv lista s podacima o zaposlenicima

# Serijska komunikacija konfiguracija
SERIAL_PORT = 'COM4' # Prilagodite ako je potrebno (na Windowsima npr. 'COM3')
SERIAL_BAUDRATE = 9600
SERIAL_TIMEOUT = 1 # Sekunde

# GUI konfiguracija
TIMEOUT_ACTION_SELECTION_SEC = 15 # Vrijeme u sekundama za odabir akcije
MESSAGE_DISPLAY_DURATION_SEC = 4 # Koliko dugo se poruka prikazuje

# Email konfiguracija za mjesečni izvještaj
EMAIL_SENDER_ADDRESS = 'vaš_email@gmail.com' # Email s kojeg se šalje izvještaj
EMAIL_SENDER_PASSWORD = 'VAŠA_APP_PASSWORD_OVDJE' # Koristite App Password za Gmail!
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
EMAIL_RECIPIENT_ADDRESS = 'lovro.sverko@skole.hr' # Primatelj izvještaja (testna adresa)

# Logiranje konfiguracija
LOG_FILE = 'aplikacija_log.log'
LOG_LEVEL = logging.DEBUG # DEBUG, INFO, WARNING, ERROR, CRITICAL (promijenite na INFO/WARNING za produkciju)

# --- Postavljanje Logiranja ---
logging.basicConfig(filename=LOG_FILE, level=LOG_LEVEL,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# --- Klasa za upravljanje Google Sheetsom ---
class GoogleSheetsManager:
    def __init__(self, sheet_id, key_path, zaposlenici_sheet_name):
        self.sheet_id = sheet_id
        self.key_path = key_path
        self.zaposlenici_sheet_name = zaposlenici_sheet_name
        self.gc = None # gc će biti pygsheets klijent
        self.zaposlenici_data = {} # Keširani podaci o zaposlenicima {UID: {'Ime': '...', 'Prezime': '...'}}
        self._authorize()
        self._load_zaposlenici() # Učitaj zaposlenike odmah nakon autentifikacije

    def _authorize(self):
        """Autentifikacija s Google Sheets API-jem koristeći Service Account za pygsheets."""
        try:
            self.gc = pygsheets.authorize(service_file=self.key_path)
            logging.info("GSManager: Uspješna autentifikacija s Google Sheetsom (pygsheets).")
        except Exception as e:
            logging.error(f"GSManager: Greška pri autentifikaciji s Google Sheetsom (pygsheets): {e}", exc_info=True)
            self.gc = None
            raise # Ponovno baci iznimku kako bi se prekinuo rad ako autentifikacija ne uspije

    def _load_zaposlenici(self):
        """Učitava podatke o zaposlenicima iz lista 'Zaposlenici'."""
        if not self.gc: 
            logging.warning("GSManager: Nema Google Sheets konekcije za učitavanje zaposlenika.")
            return
        try:
            workbook = self.gc.open_by_key(self.sheet_id) # open_by_key za pygsheets
            zaposlenici_sheet = workbook.worksheet_by_title(self.zaposlenici_sheet_name) # worksheet_by_title za pygsheets
            
            records = zaposlenici_sheet.get_all_records() # pygsheets podržava get_all_records()
            
            for record in records:
                if 'UID' in record and 'Ime' in record and 'Prezime' in record:
                    self.zaposlenici_data[record['UID']] = {
                        'Ime': record['Ime'],
                        'Prezime': record['Prezime']
                    }
            logging.info(f"GSManager: Učitani podaci o {len(self.zaposlenici_data)} zaposlenika.")
        except Exception as e:
            logging.error(f"GSManager: Greška pri učitavanju podataka o zaposlenicima: {e}", exc_info=True)
            raise # Prekinuti rad ako se zaposlenici ne mogu učitati

    def get_zaposlenik_info(self, uid):
        """Dohvaća informacije o zaposleniku na temelju UID-a."""
        return self.zaposlenici_data.get(uid)

    def _get_or_create_daily_sheet(self, date_str):
        """Dohvaća dnevni radni list; ako ne postoji, stvara ga."""
        if not self.gc: raise Exception("GSManager: Google Sheets nije autoriziran.")
        try:
            workbook = self.gc.open_by_key(self.sheet_id) # open_by_key za pygsheets
            try:
                worksheet = workbook.worksheet_by_title(date_str) # worksheet_by_title za pygsheets
                logging.info(f"GSManager: Pronađen list za {date_str}.")
                return worksheet
            except pygsheets.exceptions.WorksheetNotFound: # pygsheets iznimka
                logging.info(f"GSManager: Kreiram novi list za {date_str}.")
                worksheet = workbook.add_worksheet(title=date_str, rows="100", cols="10")
                headers = ["IME", "PREZIME", "UIDkartice", "DATUM", "VRIJEME_DOLASKA",
                           "VRIJEME_IZLASKA", "VRIJEME_POVRATKA", "VRIJEME_ODLASKA", "STATUS"]
                # ISPRAVAK: Koristi update_row za postavljanje zaglavlja u prvi redak
                worksheet.update_row(1, values=headers) # Postavi zaglavlja u prvi redak
                return worksheet
        except Exception as e:
            logging.error(f"GSManager: Greška pri dobivanju/kreiranju dnevnog lista: {e}", exc_info=True)
            raise

    def update_daily_record(self, user_info, current_date_str, action_type, new_status):
        """Ažurira dnevni zapis o prisutnosti zaposlenika u Google Sheetu."""
        if not self.gc: raise Exception("GSManager: Google Sheets nije autoriziran.")
        try:
            worksheet = self._get_or_create_daily_sheet(current_date_str)
            records = worksheet.get_all_records() # pygsheets podržava get_all_records()
            found_row_idx = -1
            
            # Tražimo redak po UID-u
            for i, record in enumerate(records):
                if record.get('UIDkartice') == user_info['UID']:
                    found_row_idx = i + 2 # +2 jer records počinje od 0, a sheet je 1-baziran, i preskače zaglavlje
                    break

            current_time = datetime.datetime.now().strftime("%H:%M:%S")
            
            # Dohvati zaglavlja iz prvog retka da se pronađe točan indeks stupca
            header_row = worksheet.get_row(1) # pygsheets koristi get_row()

            if found_row_idx != -1:
                # Ažuriraj postojeći redak
                col_name_map = {
                    "DOLAZAK": "VRIJEME_DOLASKA",
                    "ODLAZAK NA MARENDU": "VRIJEME_IZLASKA",
                    "POVRATAK S MARENDE": "VRIJEME_POVRATKA",
                    "ODLAZAK": "VRIJEME_ODLASKA"
                }
                target_col_name = col_name_map.get(action_type)
                
                if target_col_name and target_col_name in header_row:
                    col_index = header_row.index(target_col_name) + 1 # +1 za 1-bazirani indeks stupca
                    worksheet.update_value(found_row_idx, col_index, current_time) # pygsheets.update_value s row, col

                # Ažuriraj status
                status_col_index = header_row.index("STATUS") + 1
                worksheet.update_value(found_row_idx, status_col_index, new_status) # pygsheets.update_value s row, col
                
                logging.info(f"GSManager: Ažuriran redak za {user_info['Ime']} {user_info['Prezime']} na {current_date_str} s akcijom {action_type}. Novi status: {new_status}")
                return True
            else:
                # Dodaj novi redak
                new_row_values = [
                    user_info['Ime'],
                    user_info['Prezime'],
                    user_info['UID'],
                    current_date_str,
                    "" if action_type != "DOLAZAK" else current_time, # VRIJEME_DOLASKA
                    "" if action_type != "ODLAZAK NA MARENDU" else current_time, # VRIJEME_IZLASKA
                    "" if action_type != "POVRATAK S MARENDE" else current_time, # VRIJEME_POVRATKA
                    "" if action_type != "ODLAZAK" else current_time, # VRIJEME_ODLASKA
                    new_status
                ]
                # Koristimo insert_rows za dodavanje cijelog retka
                next_available_row = len(worksheet.get_all_values(include_tailing_empty_rows=False)) # <-- ISPRAVAK!
                
                # Osiguraj da list ima dovoljno redaka prije umetanja (ako je list mali)
                if next_available_row > worksheet.rows:
                    rows_to_add = next_available_row - worksheet.rows + 10 # Dodajemo malo više za buduće potrebe
                    logging.info(f"GSManager: Proširujem list '{worksheet.title}' za {rows_to_add} redaka prije umetanja.")
                    worksheet.add_rows(rows_to_add)

                worksheet.insert_rows(next_available_row, values=new_row_values, inherit=False)
                logging.info(f"GSManager: Dodana novi redak za {user_info['Ime']} {user_info['Prezime']} na {current_date_str} s akcijom {action_type}. Novi status: {new_status} (koristeći insert_rows).")
                return True
        except Exception as e:
            logging.error(f"GSManager: Greška pri ažuriranju dnevnog zapisa za {user_info['UID']}: {e}", exc_info=True)
            raise

    def get_current_user_status_for_day(self, uid, date_str):
        """Dohvaća trenutni status korisnika i njegov zadnji zapis za tekući dan."""
        if not self.gc: raise Exception("GSManager: Google Sheets nije autoriziran.")
        try:
            worksheet = self._get_or_create_daily_sheet(date_str)
            records = worksheet.get_all_records() # pygsheets podržava get_all_records()
            for record in records:
                if record.get('UIDkartice') == uid:
                    # Vraca zadnji zabilježeni status za tog korisnika tog dana i cijeli zapis
                    return record.get('STATUS', 'OTISAO'), record
            return 'OTISAO', {} # Ako nema zapisa za taj UID za taj dan, status je OTISAO
        except pygsheets.exceptions.WorksheetNotFound: # pygsheets iznimka
            # Ako sheet za taj dan ne postoji, onda je status OTISAO
            return 'OTISAO', {}
        except Exception as e:
            logging.error(f"GSManager: Greška pri dohvatu statusa za {uid} na {date_str}: {e}", exc_info=True)
            return 'OTISAO', {} # U slučaju greške, pretpostavi 'OTISAO' da ne blokira app

    def get_monthly_data(self, year, month):
        """Prikuplja sve zapise za određeni mjesec."""
        if not self.gc: raise Exception("GSManager: Google Sheets nije autoriziran.")
        all_monthly_records = []
        try:
            workbook = self.gc.open_by_key(self.sheet_id) # open_by_key za pygsheets
            for worksheet in workbook.worksheets(): # pygsheets.worksheets() vraća list worksheet objekata
                try:
                    # Pokušaj parsirati datum iz naziva lista
                    sheet_date = datetime.datetime.strptime(worksheet.title, "%Y-%m-%d")
                    if sheet_date.year == year and sheet_date.month == month:
                        logging.info(f"GSManager: Prikupim podatke s lista: {worksheet.title}")
                        records = worksheet.get_all_records() # pygsheets podržava get_all_records()
                        all_monthly_records.extend(records)
                except ValueError:
                    # Preskoči listove čiji naziv nije datum (npr. 'Zaposlenici')
                    continue
            logging.info(f"GSManager: Prikupljeno {len(all_monthly_records)} zapisa za {month}/{year}.")
            return all_monthly_records
        except Exception as e:
            logging.error(f"GSManager: Greška pri prikupljanju mjesečnih podataka za {month}/{year}: {e}", exc_info=True)
            return []

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
        self.reconnect_delay = 5 # Sekunde prije ponovnog pokušaja spajanja

    def run(self):
        logging.info(f"SerialThread: Pokrenuta serijska nit za port {self.port}...")
        while self.running:
            if not self.ser or not self.ser.is_open:
                logging.warning(f"SerialThread: Pokušavam se spojiti na serijski port {self.port}...")
                try:
                    self.ser = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
                    logging.info(f"SerialThread: Uspješno spojen na serijski port {self.port}.")
                except serial.SerialException as e:
                    logging.error(f"SerialThread: Greška pri spajanju na serijski port: {e}. Pokušavam ponovno za {self.reconnect_delay}s.", exc_info=True)
                    time.sleep(self.reconnect_delay)
                    continue
            
            try:
                if self.ser.in_waiting > 0:
                    line = self.ser.readline().decode('utf-8').strip()
                    if line.startswith("UID:"):
                        uid = line[4:]
                        logging.info(f"SerialThread: Primljen UID: {uid}")
                        self.data_queue.put(uid) # Stavi UID u red za GUI
                    else:
                        logging.debug(f"SerialThread: Primljena nepoznata serijska poruka: {line}")
            except serial.SerialException as e:
                logging.error(f"SerialThread: Greška u serijskoj komunikaciji (veza izgubljena?): {e}. Zatvaram port i pokušavam ponovno.", exc_info=True)
                if self.ser and self.ser.is_open:
                    self.ser.close()
                self.ser = None # Označi da je port zatvoren i treba ga ponovno otvoriti
            except Exception as e:
                logging.error(f"SerialThread: Neočekivana greška u serijskoj niti: {e}", exc_info=True)
            
            time.sleep(0.1) # Mala pauza kako bi se spriječilo preopterećenje CPU-a

    def stop(self):
        """Metoda za sigurno zaustavljanje serijske niti."""
        logging.info("SerialThread: Zaustavljam serijsku nit.")
        self.running = False
        if self.ser and self.ser.is_open:
            self.ser.close()

# --- Klasa za slanje mjesečnih izvještaja ---
class MonthlyReportScheduler:
    def __init__(self, google_sheets_manager, recipient_email, sender_email, sender_password, smtp_server, smtp_port):
        self.gs_manager = google_sheets_manager
        self.recipient_email = recipient_email
        self.sender_email = sender_email
        self.sender_password = sender_password
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.last_checked_day = datetime.datetime.now().day # Da ne šalje više puta isti dan u istom mjesecu
        logging.info(f"ReportScheduler: Inicijaliziran. Zadnja provjera datuma: {self.last_checked_day}")


    def check_and_send_report(self):
        """Provjerava je li vrijeme za slanje mjesečnog izvještaja i pokreće ga."""
        current_date = datetime.datetime.now()
        # Provjerava je li prvi dan u mjesecu i da li je provjera već obavljena taj dan
        # Također, ako je aplikacija ugašena i pokrenuta isti prvi dan u mjesecu, ponovno će provjeriti.
        if current_date.day == 1 and current_date.day != self.last_checked_day:
            logging.info("ReportScheduler: Prvi dan u mjesecu, provjeravam za slanje mjesečnog izvještaja...")
            
            # Odredite prethodni mjesec
            first_day_of_current_month = current_date.replace(day=1)
            last_day_of_prev_month = first_day_of_current_month - datetime.timedelta(days=1)
            
            report_year = last_day_of_prev_month.year
            report_month = last_day_of_prev_month.month

            logging.info(f"ReportScheduler: Pripremam izvještaj za {report_month}/{report_year}...")
            
            # Podaci se prikupljaju u gs_manager.get_monthly_data()
            # Možete ih iskoristiti za kreiranje Excel datoteke ako ne želite link
            
            self._send_monthly_email_report(report_year, report_month)
            self.last_checked_day = current_date.day # Ažuriraj zadnji provjereni dan
        else:
            logging.debug(f"ReportScheduler: Nije prvi dan u mjesecu ili je već provjereno ({current_date.day} vs {self.last_checked_day}).")


    def _send_monthly_email_report(self, year, month):
        """Šalje mjesečni izvještaj putem e-maila (kao link na Google Sheet)."""
        subject = f"Mjesečni izvještaj evidencije radnog vremena - {month}/{year}"
        
        # Dohvati URL Google Sheeta
        google_sheet_url = ""
        try:
            workbook = self.gs_manager.gc.open_by_key(self.gs_manager.sheet_id)
            google_sheet_url = workbook.url
            logging.info(f"ReportScheduler: Dohvaćen Google Sheet URL: {google_sheet_url}")
        except Exception as e:
            logging.error(f"ReportScheduler: Greška pri dohvatu Google Sheet URL-a: {e}", exc_info=True)
            google_sheet_url = "Nije moguće dohvatiti link na Google Sheet."

        body = f"""Poštovani,

U prilogu je mjesečni izvještaj evidencije radnog vremena za {month}/{year}.
Podatke možete vidjeti i direktno u Google Sheetu na sljedećem linku:
{google_sheet_url}

S poštovanjem,
Vaš Sustav za Evidenciju Radnog Vremena
"""
        msg = MIMEMultipart()
        msg['From'] = self.sender_email
        msg['To'] = self.recipient_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        try:
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls() # Enable TLS encryption
            server.login(self.sender_email, self.sender_password)
            text = msg.as_string()
            server.sendmail(self.sender_email, self.recipient_email, text)
            server.quit()
            logging.info(f"ReportScheduler: Mjesečni izvještaj za {month}/{year} uspješno poslan na {self.recipient_email}.")
        except Exception as e:
            logging.error(f"ReportScheduler: Greška pri slanju mjesečnog izvještaja za {month}/{year}: {e}", exc_info=True)

# --- Glavna GUI aplikacija (Tkinter) ---
class RFIDApp(tk.Tk):
    def __init__(self, serial_port, baudrate, gs_manager):
        super().__init__()
        self.gs_manager = gs_manager
        self.title("Evidencija Radnog Vremena - RFID")
        self.geometry("800x480") # Prilagodite rezoluciji ekrana na dodir
        self.attributes('-fullscreen', False) # NE Pokreni u punom ekranu

        # UI elementi
        self.main_label = tk.Label(self, text="Prinesite karticu...", font=("Helvetica", 36), wraplength=700)
        self.main_label.pack(expand=True, pady=20)

        self.time_label = tk.Label(self, text="", font=("Helvetica", 18))
        self.time_label.pack(side=tk.TOP, anchor=tk.NE, padx=10, pady=10)
        self.update_time() # Pokreni osvježavanje vremena

        self.buttons_frame = tk.Frame(self)
        self.buttons = {}
        # Raspored gumba u 2x2 grid (primjer rasporeda)
        self.buttons_frame.columnconfigure(0, weight=1)
        self.buttons_frame.columnconfigure(1, weight=1)
        self.buttons_frame.rowconfigure(0, weight=1)
        self.buttons_frame.rowconfigure(1, weight=1)

        button_configs = [
            ("DOLAZAK", 0, 0, "#4CAF50"), # Green
            ("ODLAZAK NA MARENDU", 0, 1, "#FFC107"), # Amber
            ("POVRATAK S MARENDE", 1, 0, "#03A9F4"), # Light Blue
            ("ODLAZAK", 1, 1, "#F44336") # Red
        ]

        for text, row, col, bg_color in button_configs:
            btn = tk.Button(self.buttons_frame, text=text, font=("Helvetica", 24, "bold"),
                            command=lambda t=text: self.handle_action_selection(t),
                            state=tk.DISABLED, bg=bg_color, fg="white",
                            activebackground=bg_color, activeforeground="white",
                            bd=0, highlightthickness=0) # Make buttons look flat
            self.buttons[text] = btn
            btn.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
        
        self.buttons_frame.pack_forget() # Sakrij frame dok nije potrebno

        self.user_info = None # Trenutno prepoznati korisnik
        self.current_user_status = 'OTISAO' # Trenutni status korisnika za danas
        self.current_user_daily_record = {} # Trenutni zapis korisnika za danas (iz GSheets)
        self.timeout_id = None # ID za timer povratka na idle ekran

        # Red za komunikaciju iz serijske niti
        self.rfid_queue = queue.Queue()
        self.serial_thread = SerialMonitorThread(serial_port, baudrate, SERIAL_TIMEOUT, self.rfid_queue)
        self.serial_thread.start()

        # Provjerava red za nove UID-ove
        self.after(100, self.check_rfid_queue)
        
        # Pokreni scheduler za mjesečni izvještaj
        self.report_scheduler = MonthlyReportScheduler(
            self.gs_manager,
            EMAIL_RECIPIENT_ADDRESS,
            EMAIL_SENDER_ADDRESS,
            EMAIL_SENDER_PASSWORD,
            SMTP_SERVER,
            SMTP_PORT
        )
        self.after(5 * 60 * 1000, self.check_monthly_report) # Provjeravaj svakih 5 minuta za izvještaj (može se podesiti)

    def update_time(self):
        """Ažurira prikaz datuma i vremena na ekranu."""
        now = datetime.datetime.now()
        date_str = now.strftime("%d. %B %Y.")
        time_str = now.strftime("%H:%M:%S")
        self.time_label.config(text=f"{date_str}\n{time_str}")
        self.after(1000, self.update_time) # Ažuriraj svake sekunde

    def check_rfid_queue(self):
        """Periodično provjerava red za nove UID-ove s RFID čitača."""
        try:
            uid = self.rfid_queue.get_nowait() # Pokušaj dobiti UID bez čekanja
            self.handle_rfid_read(uid)
        except queue.Empty:
            pass # Nema novih podataka, samo nastavi
        self.after(100, self.check_rfid_queue) # Zakazivanje ponovne provjere za 100ms

    def handle_rfid_read(self, uid):
        """Rukuje očitanim UID-om kartice."""
        logging.info(f"GUI: Primljen UID: {uid}")
        if self.timeout_id:
            self.after_cancel(self.timeout_id) # Poništi prethodni timer za timeout akcije

        self.user_info = self.gs_manager.get_zaposlenik_info(uid)
        
        if self.user_info:
            self.user_info['UID'] = uid # Dodaj UID info za daljnju obradu
            current_date_str = datetime.datetime.now().strftime("%Y-%m-%d")
            
            try:
                # Dohvati trenutni status korisnika iz GSheets
                self.current_user_status, self.current_user_daily_record = self.gs_manager.get_current_user_status_for_day(uid, current_date_str)
                logging.info(f"GUI: Korisnik {self.user_info['Ime']} status: {self.current_user_status}")
                self.display_action_selection_screen()
            except Exception as e:
                logging.error(f"GUI: Greška pri dohvatu statusa korisnika: {e}", exc_info=True)
                self.display_message("Greška sustava! Pokušajte ponovno.", "red")
                self.reset_to_idle_after_delay()
        else:
            self.display_message("Nepoznata kartica! Molimo kontaktirajte administraciju.", "red")
            self.reset_to_idle_after_delay()

    def display_action_selection_screen(self):
        """Prikazuje ekran za odabir akcije s dinamički omogućenim gumbima."""
        self.main_label.config(text=f"Zdravo, {self.user_info['Ime']} {self.user_info['Prezime']}!")
        self.buttons_frame.pack(expand=True, pady=20, fill="both") # Prikaži gumbe frame

        # Dinamičko omogućavanje/onemogućavanje gumba
        # Postavi sve na DISABLED pa onda omogući samo relevantne
        for btn in self.buttons.values():
            btn.config(state=tk.DISABLED)

        if self.current_user_status == 'OTISAO':
            self.buttons["DOLAZAK"].config(state=tk.NORMAL)
        elif self.current_user_status == 'NA_POSLU':
            self.buttons["ODLAZAK NA MARENDU"].config(state=tk.NORMAL)
            self.buttons["ODLAZAK"].config(state=tk.NORMAL)
        elif self.current_user_status == 'NA_MARENDI':
            self.buttons["POVRATAK S MARENDE"].config(state=tk.NORMAL)

        # Postavi tajmer za povratak na idle ekran
        self.timeout_id = self.after(TIMEOUT_ACTION_SELECTION_SEC * 1000, self.reset_to_idle_screen) # Direktno resetiranje

    def handle_action_selection(self, action):
        """Rukuje odabirom akcije od strane korisnika."""
        if self.timeout_id:
            self.after_cancel(self.timeout_id) # Poništi tajmer za odabir akcije

        logging.info(f"GUI: Korisnik {self.user_info['Ime']} odabrao: {action}")
        self.buttons_frame.pack_forget() # Sakrij gumbe odmah

        current_date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        new_status = self.current_user_status # Pretpostavi da se status ne mijenja ako akcija nije validna
        message = ""
        color = "black"
        action_valid = False

        try:
            # Logika prijelaza stanja (u skladu s dogovorenim algoritmom)
            if self.current_user_status == 'OTISAO' and action == 'DOLAZAK':
                new_status = 'NA_POSLU'
                message = f"Akcija 'Dolazak' uspješno zabilježena! Hvala!"
                color = "green"
                action_valid = True
            elif self.current_user_status == 'NA_POSLU' and action == 'ODLAZAK NA MARENDU':
                # Provjera za jednu marendu dnevno
                if self.current_user_daily_record.get('VRIJEME_IZLASKA') and self.current_user_daily_record.get('VRIJEME_IZLASKA') != "":
                    message = "Greška: Marenda je već zabilježena za danas."
                    color = "red"
                else:
                    new_status = 'NA_MARENDI'
                    message = f"Ugodnu marendu, {self.user_info['Ime']}! Zabilježen odlazak na marendu."
                    color = "green"
                    action_valid = True
            elif self.current_user_status == 'NA_MARENDI' and action == 'POVRATAK S MARENDE':
                new_status = 'NA_POSLU'
                message = f"Dobrodošli natrag, {self.user_info['Ime']}! Zabilježen povratak s marende."
                color = "green"
                action_valid = True
            elif self.current_user_status == 'NA_POSLU' and action == 'ODLAZAK':
                new_status = 'OTISAO'
                message = f"Doviđenja, {self.user_info['Ime']}! Zabilježen odlazak s posla."
                color = "green"
                action_valid = True
            else:
                message = "Greška: Nelogična akcija za trenutni status. Molimo pokušajte ponovno."
                color = "red"
            
            if action_valid: # Samo ako je akcija validna za upis
                self.gs_manager.update_daily_record(self.user_info, current_date_str, action, new_status)
            
            self.display_message(message, color)
            self.reset_to_idle_after_delay()

        except Exception as e:
            logging.error(f"GUI: Greška pri obradi akcije {action} za korisnika {self.user_info['UID']}: {e}", exc_info=True)
            self.display_message("Greška pri spremanju podataka! Pokušajte ponovno.", "red")
            self.reset_to_idle_after_delay()

    def display_message(self, msg, color="black"):
        """Prikazuje poruku korisniku u UI-ju."""
        self.main_label.config(text=msg, fg=color)
        # Nema after poziva ovdje, jer ga zove reset_to_idle_after_delay

    def reset_to_idle_after_delay(self):
        """Zakazuje povratak na idle ekran nakon kratkog kašnjenja."""
        self.after(MESSAGE_DISPLAY_DURATION_SEC * 1000, self.reset_to_idle_screen)

    def reset_to_idle_screen(self):
        """Vraća GUI na početni (idle) ekran."""
        self.main_label.config(text="Prinesite karticu...", fg="black")
        self.buttons_frame.pack_forget() # Sakrij gumbe
        self.user_info = None
        self.current_user_status = 'OTISAO'
        self.current_user_daily_record = {}
        logging.info("GUI: Resetiran na početni ekran.")

    def check_monthly_report(self):
        """Provjerava i pokreće slanje mjesečnog izvještaja."""
        self.report_scheduler.check_and_send_report()
        # Ponovno zakazivanje za sljedeću provjeru
        self.after(5 * 60 * 1000, self.check_monthly_report) # Svakih 5 minuta

    def on_closing(self):
        """Rukuje gašenjem aplikacije i zaustavlja pozadinske niti."""
        logging.info("Aplikacija se gasi. Zaustavljam serijsku nit.")
        self.serial_thread.stop()
        self.destroy()

# --- Glavna izvršna logika ---
if __name__ == "__main__":
    logging.info("Aplikacija se pokreće...")
    logging.debug(f"DEBUG: Python izvršna datoteka: {sys.executable}")
    logging.debug(f"DEBUG: Python staza: {sys.path}")
    
    # Automatska detekcija serijskog porta
    actual_serial_port = SERIAL_PORT
    if not actual_serial_port: # Ako SERIAL_PORT u konfiguraciji nije specificiran (prazan)
        logging.info("Automatska detekcija serijskog porta...")
        ports = serial.tools.list_ports.comports()
        found_port = None
        for p in ports:
            # Heuristička pretraga za Arduino/Dasduino
            if 'ACM' in p.device or 'USB' in p.device: 
                found_port = p.device
                break
        
        if found_port:
            actual_serial_port = found_port
            logging.info(f"Automatski detektiran serijski port: {actual_serial_port}")
        else:
            logging.error("Nije pronađen kompatibilan serijski port. Aplikacija se neće moći spojiti na RFID čitač.")
            messagebox.showerror("Greška porta", "Nije pronađen serijski port za Dasduino/RFID čitač. Provjerite da je spojen i da je driver instaliran.")
            sys.exit(1) # Izađite iz aplikacije ako port nije pronađen

    elif actual_serial_port: # Ako je port eksplicitno definiran u konfiguraciji
        logging.info(f"Koristim konfigurirani serijski port: {actual_serial_port}")

    try:
        # Inicijaliziraj Google Sheets Manager
        gs_manager = GoogleSheetsManager(GOOGLE_SHEET_ID, SERVICE_ACCOUNT_KEY_PATH, ZAPOSLENICI_SHEET_NAME)
        
        # Kreiraj i pokreni GUI aplikaciju
        app = RFIDApp(actual_serial_port, SERIAL_BAUDRATE, gs_manager)
        app.protocol("WM_DELETE_WINDOW", app.on_closing) # Osiguraj čisto gašenje
        app.mainloop()

    except Exception as e:
        # Hvata sve kritične greške koje se mogu dogoditi prije ili tijekom pokretanja aplikacije
        logging.critical(f"Kritična greška pri pokretanju aplikacije: {e}", exc_info=True) # exc_info=True za potpuni traceback
        messagebox.showerror("Kritična greška", f"Aplikacija se nije mogla pokrenuti. Provjerite log datoteku ({LOG_FILE}). Greška: {e}")
        sys.exit(1) # Izađite iz aplikacije