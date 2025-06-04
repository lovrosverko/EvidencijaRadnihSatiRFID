# Sustav za Evidenciju Radnog Vremena pomoću RFID kartica

Ovaj projekt omogućuje automatiziranu evidenciju dolazaka, odlazaka i pauza za marendu zaposlenika/učenika/korisnika pomoću RFID kartica, s podacima pohranjenim i obrađenim u Google Sheetsu. Sustav se sastoji od glavne aplikacije za evidenciju (s GUI-jem za touchscreen) i pomoćne aplikacije za jednostavno dodavanje novih korisnika.

## Sadržaj

1.  [Ključne značajke](https://www.google.com/search?q=%231-klju%C4%8Dne-zna%C4%8Dajke)
2.  [Tehnologije korištene](https://www.google.com/search?q=%232-tehnologije-kori%C5%A1tene)
3.  [Hardverski zahtjevi](https://www.google.com/search?q=%233-hardverski-zahtjevi)
4.  [Postavljanje projekta](https://www.google.com/search?q=%234-postavljanje-projekta)
      * [4.1. Kloniranje repozitorija](https://www.google.com/search?q=%2341-kloniranje-repozitorija)
      * [4.2. Postavljanje Python virtualnog okruženja](https://www.google.com/search?q=%2342-postavljanje-python-virtualnog-okru%C5%BEenja)
      * [4.3. Konfiguracija Google Cloud projekta i Google Sheets API-ja](https://www.google.com/search?q=%2343-konfiguracija-google-cloud-projekta-i-google-sheets-api-ja)
      * [4.4. Postavljanje Arduino/Dasduino firmwarea](https://www.google.com/search?q=%2344-postavljanje-arduinodasduino-firmwarea)
      * [4.5. Konfiguracija emaila](https://www.google.com/search?q=%2345-konfiguracija-emaila)
5.  [Korištenje aplikacija](https://www.google.com/search?q=%235-kori%C5%A1tenje-aplikacija)
      * [5.1. Aplikacija za dodavanje novih korisnika](https://www.google.com/search?q=%2351-aplikacija-za-dodavanje-novih-korisnika)
      * [5.2. Glavna aplikacija za evidenciju radnog vremena](https://www.google.com/search?q=%2352-glavna-aplikacija-za-evidenciju-radnog-vremena)
6.  [Struktura Google Sheets datoteke](https://www.google.com/search?q=%236-struktura-google-sheets-datoteke)
7.  [Otklanjanje poteškoća](https://www.google.com/search?q=%237-otklanjanje-pote%C5%A1ko%C4%87a)
8.  [Buduća poboljšanja](https://www.google.com/search?q=%238-budu%C4%87a-pobolj%C5%A1anja)
9.  [Licenca](https://www.google.com/search?q=%239-licenca)

-----

### 1\. Ključne značajke

  * **Evidencija prisutnosti:** Bilježi dolaske, odlaske, odlaske na marendu i povratke s marende.
  * **RFID Autentifikacija:** Brzo i sigurno prepoznavanje korisnika pomoću RFID kartica.
  * **Google Sheets Integracija:** Svi podaci o prisutnosti pohranjuju se u realnom vremenu u Google Sheets (u zasebne listove za svaki dan). Podaci o zaposlenicima (UID, Ime, Prezime) također se čitaju iz Google Sheeta.
  * **Intuitivni GUI:** Sučelje prilagođeno za ekrane na dodir s dinamičkim gumbima na temelju statusa korisnika.
  * **Automatska detekcija porta:** Aplikacija automatski pronalazi priključeni RFID čitač.
  * **Rad 0-24:** Dizajnirano za kontinuiran rad s robusnim rukovanjem pogreškama i logiranjem.
  * **Mjesečni izvještaji:** Automatsko slanje mjesečnog izvještaja o prisutnosti na definirani e-mail (kao link na Google Sheet).
  * **Aplikacija za administraciju korisnika:** Zasebna aplikacija za jednostavno dodavanje novih zaposlenika u sustav, s automatskim očitanjem UID-a kartice.

### 2\. Tehnologije korištene

  * **Python 3.x:** Glavni programski jezik.
  * **Tkinter:** Python biblioteka za izradu GUI sučelja.
  * **`pygsheets`:** Python biblioteka za interakciju s Google Sheets API-jem.
  * **`pyserial`:** Python biblioteka za serijsku komunikaciju s mikrokontrolerom.
  * **`threading`:** Python modul za obradu serijske komunikacije u pozadini.
  * **`smtplib` / `email`:** Python moduli za slanje e-mailova.
  * **Dasduino Lite / Arduino:** Mikrokontroler za čitanje RFID kartica.
  * **Velleman VMA405 (MFRC522):** RFID čitač/pisač.
  * **Google Sheets API:** Za pohranu i upravljanje podacima.
  * **Raspberry Pi:** Preporučena platforma za pokretanje glavne aplikacije 0-24.

### 3\. Hardverski zahtjevi

  * **Raspberry Pi** (preporučeno, npr., Raspberry Pi 3B+, 4 ili noviji) s instaliranim Raspberry Pi OS-om.
  * **Ekran na dodir** za Raspberry Pi (opcionalno, ali preporučeno za GUI).
  * **Dasduino Lite / Arduino-kompatibilna ploča** (npr., ESP32, ESP8266, Arduino Uno/Nano).
  * **Velleman VMA405 RFID senzor** (MFRC522 čip).
  * **RFID kartice/privjesci.**
  * **USB kabel** za spajanje Dasduino Lite na Raspberry Pi/računalo.
  * **Žice za spajanje** (jumper wires).
  * **Napajanje** za Raspberry Pi i Dasduino Lite.

### 4\. Postavljanje projekta

Slijedite ove korake kako biste postavili i pokrenuli projekt.

#### 4.1. Kloniranje repozitorija

Otvorite terminal (na računalu ili Raspberry Pi-ju) i klonirajte repozitorij:

```bash
git clone https://github.com/VašKorisnik/VašRepoNaziv.git
cd VašRepoNaziv # Idite u direktorij projekta
```

Zamijenite `VašKorisnik` i `VašRepoNaziv` s vašim stvarnim podacima.

#### 4.2. Postavljanje Python virtualnog okruženja

Preporučuje se korištenje virtualnog okruženja za izolaciju ovisnosti projekta.

```bash
# Kreirajte virtualno okruženje (nazvano 'rfid_env')
python -m venv rfid_env

# Aktivirajte virtualno okruženje
# Na Windowsima:
.\rfid_env\Scripts\activate
# Na Linuxu (Raspberry Pi):
source rfid_env/bin/activate

# Instalirajte potrebne Python biblioteke
pip install pygsheets pyserial
```

#### 4.3. Konfiguracija Google Cloud projekta i Google Sheets API-ja

Ovo je ključni korak za komunikaciju s Google Sheetsom.

1.  **Stvorite Google Cloud projekt:** Posjetite [Google Cloud Console](https://console.cloud.google.com/) i kreirajte novi projekt.
2.  **Omogućite API-je:** Unutar vašeg projekta, idite na "APIs & Services" -\> "Enabled APIs & services". Potražite i omogućite:
      * **Google Sheets API**
      * **Google Drive API**
3.  **Kreirajte Service Account:**
      * U Google Cloud Console, idite na "IAM & Admin" -\> "Service accounts".
      * Kreirajte novi Service Account.
      * Prilikom kreiranja, **odaberite "JSON" kao tip ključa** i preuzmite JSON datoteku. **Ovu datoteku čuvajte na sigurnom mjestu\!** To je vaša vjerodajnica za pristup Google Sheetsu.
4.  **Podijelite Google Sheet s Service Accountom:**
      * Kreirajte novu Google Sheets datoteku (npr., "Evidencija Radnog Vremena") u svom Google Driveu.
      * **Važno:** Otvorite JSON datoteku Service Accounta koju ste preuzeli i pronađite e-mail adresu Service Accounta (izgleda kao `neko-ime@projekt-id.iam.gserviceaccount.com`).
      * U Google Sheets datoteci "Evidencija Radnog Vremena", kliknite "Share" (Podijeli) i **podijelite je s e-mail adresom vašeg Service Accounta**, dajući mu dozvolu **"Editor"** (Uređivač).
5.  **Dohvatite ID Google Sheets datoteke:**
      * ID datoteke se nalazi u URL-u vaše Google Sheets datoteke, između `/d/` i `/edit`. Npr.: `https://docs.google.com/spreadsheets/d/VAŠ_ID_OVDJE/edit`.
6.  **Ažurirajte konfiguraciju u kodu:**
      * Otvorite datoteku `glavna_aplikacija_rfid.py` (i `upis_korisnika.py`).
      * Pronđite sekciju `--- Konfiguracija Aplikacije ---`.
      * **`GOOGLE_SHEET_ID`:** Zalijepite ID svoje Google Sheets datoteke.
      * **`SERVICE_ACCOUNT_KEY_PATH`:** Ažurirajte putanju do preuzete JSON datoteke Service Account ključa (npr., `'service_account.json'` ako je u istom direktoriju kao i skripta, ili cijela apsolutna putanja).
7.  **Pripremite list "Zaposlenici":**
      * U vašoj Google Sheets datoteci "Evidencija Radnog Vremena", preimenujte prvi list u **`Zaposlenici`**.
      * U prvi redak (A1, B1, C1...) upišite točno ova zaglavlja (slova su bitna\!): **`UID`**, **`Ime`**, **`Prezime`**.
      * Unesite barem jednog testnog zaposlenika ispod zaglavlja (npr., UID vaše kartice, Ime, Prezime).

#### 4.4. Postavljanje Arduino/Dasduino firmwarea

1.  **Povezivanje VMA405 na Dasduino Lite:**

      * VMA405 VCC -\> Dasduino Lite 3.3V
      * VMA405 GND -\> Dasduino Lite GND
      * VMA405 SDA (SS) -\> Dasduino Lite PA4
      * VMA405 SCK -\> Dasduino Lite PA3
      * VMA405 MOSI -\> Dasduino Lite PA1
      * VMA405 MISO -\> Dasduino Lite PA2
      * VMA405 RST -\> Dasduino Lite PA5
      * VMA405 IRQ -\> Ne spaja se

2.  **Učitavanje Arduino koda:**

      * Instalirajte [Arduino IDE](https://www.arduino.cc/en/software).
      * Instalirajte biblioteku `MFRC522` (Miguel Balboa) kroz Arduino Library Manager.
      * Učitajte jednostavan testni kod koji čita UID kartice i šalje ga serijski. Primjer:

    <!-- end list -->

    ```cpp
    #include <SPI.h>
    #include <MFRC522.h>

    #define SS_PIN 10 // Prilagodite prema vašem spajanju (npr. PB2 na Dasduino Lite)
    #define RST_PIN 9  // Prilagodite prema vašem spajanju (npr. PB3 na Dasduino Lite)

    MFRC522 mfrc522(SS_PIN, RST_PIN);

    void setup() {
      Serial.begin(9600);
      SPI.begin();
      mfrc522.PCD_Init();
      Serial.println("RFID_READER_READY"); // Poruka da je čitač spreman
    }

    void loop() {
      if (mfrc522.PICC_IsNewCardPresent()) {
        if (mfrc522.PICC_ReadCardSerial()) {
          Serial.print("UID:");
          for (byte i = 0; i < mfrc522.uid.size; i++) {
            Serial.print(mfrc522.uid.uidByte[i] < 0x10 ? "0" : "");
            Serial.print(mfrc522.uid.uidByte[i], HEX);
          }
          Serial.println();
          mfrc522.PICC_HaltA();
        }
      }
      delay(50); // Kratka pauza
    }
    ```

    *Prilagodite `SS_PIN` i `RST_PIN` prema pinovima na Dasduino Liteu koje ste odabrali za SPI komunikaciju (PA3, PA0, PA1, PA2 za SPI i PB3 za RST). Potražite ispravno mapiranje Dasduino Lite pinova za Arduino IDE.*

#### 4.5. Konfiguracija emaila

  * Otvorite `glavna_aplikacija_rfid.py`.
  * Ažurirajte `EMAIL_SENDER_ADDRESS`, `EMAIL_SENDER_PASSWORD`, `SMTP_SERVER`, `SMTP_PORT` i `EMAIL_RECIPIENT_ADDRESS` u sekciji `--- Konfiguracija Aplikacije ---`.
  * **Važno za Gmail:** Ako koristite Gmail i imate uključenu dvostruku autentifikaciju (2FA), ne možete koristiti svoju uobičajenu lozinku. Morate generirati **"App password"** specifično za aplikacije. U Google računu idite na "Security" -\> "App passwords" i slijedite upute. Koristite tu generiranu lozinku u `EMAIL_SENDER_PASSWORD`.

### 5\. Korištenje aplikacija

Provjerite jeste li aktivirali virtualno okruženje (`.\rfid_env\Scripts\activate` ili `source rfid_env/bin/activate`) prije pokretanja bilo koje aplikacije.

#### 5.1. Aplikacija za dodavanje novih korisnika (`upis_korisnika.py`)

Ova aplikacija služi za brzo upisivanje novih zaposlenika u list `Zaposlenici`.

```bash
python upis_korisnika.py
```

  * Unesite Ime i Prezime.
  * Prinesite RFID karticu RFID čitaču da se UID automatski popuni.
  * Kliknite "DODAJ ZAPOSLENIKA".

#### 5.2. Glavna aplikacija za evidenciju radnog vremena (`glavna_aplikacija_rfid.py`)

Ovo je glavna aplikacija koja radi 0-24.

```bash
python glavna_aplikacija_rfid.py
```

  * Aplikacija će se pokrenuti u punom ekranu i prikazati "Prinesite karticu...".
  * Prinesite karticu RFID čitaču.
  * Aplikacija će prepoznati korisnika i prikazati gumbe za odabir akcije (Dolazak, Odlazak na Marenda, Povratak s Marende, Odlazak).
  * Gumbi će se dinamički omogućavati/onemogućavati ovisno o statusu korisnika.
  * Odaberite željenu akciju.
  * Aplikacija će zabilježiti akciju u Google Sheets i prikazati poruku potvrde.
  * Aplikacija automatski šalje mjesečni izvještaj e-mailom prvog dana u mjesecu.

### 6\. Struktura Google Sheets datoteke

Vaša Google Sheets datoteka mora imati sljedeću strukturu:

  * **List: `Zaposlenici`**

      * Služi kao baza podataka korisnika.
      * Zaglavlje (prvi redak): `UID`, `Ime`, `Prezime`
      * Primjer podataka:
        ```
        UID        | Ime  | Prezime
        -----------|------|--------
        123A4B5C   | Pero | Perić
        ABCDEF12   | Ana  | Anić
        ```

  * **Dnevni listovi:** (Npr. `2025-06-03`, `2025-06-04`)

      * Aplikacija ih automatski kreira po potrebi (jedan list po danu).
      * Zaglavlje (prvi redak): `IME`, `PREZIME`, `UIDkartice`, `DATUM`, `VRIJEME_DOLASKA`, `VRIJEME_IZLASKA`, `VRIJEME_POVRATKA`, `VRIJEME_ODLASKA`, `STATUS`
      * `STATUS` stupac bilježi trenutni status korisnika (`OTISAO`, `NA_POSLU`, `NA_MARENDI`).
      * Primjer podataka (za `2025-06-03`):
        ```
        IME   | PREZIME | UIDkartice | DATUM      | VRIJEME_DOLASKA | VRIJEME_IZLASKA | VRIJEME_POVRATKA | VRIJEME_ODLASKA | STATUS
        ------|---------|------------|------------|-----------------|-----------------|------------------|-----------------|--------
        Pero  | Perić   | 123A4B5C   | 2025-06-03 | 08:00:00        | 12:00:00        | 12:30:00         | 16:00:00        | OTISAO
        Ana   | Anić    | ABCDEF12   | 2025-06-03 | 08:30:00        |                 |                  |                 | NA_POSLU
        ```

### 7\. Otklanjanje poteškoća

  * **`AttributeError: 'Client' object has no attribute 'open_by_id'`:**
      * Provjerite koristite li `pygsheets` (ne `gspread`). U kodu je `pygsheets`, pa je to vjerojatno riješeno. Ako se pojavi, provjerite da je poziv `open_by_id` zamijenjen s `open_by_key` (u `GoogleSheetsManager` klasi).
  * **`GSManager: Učitani podaci o 0 zaposlenika.`:**
      * Provjerite list `Zaposlenici` u Google Sheetsu. Ime lista mora biti točno "Zaposlenici". Zaglavlja u prvom retku moraju biti točno `UID`, `Ime`, `Prezime` (uključujući velika/mala slova i bez dodatnih razmaka). Morate imati barem jednog zaposlenika unesenog ispod zaglavlja.
  * **Greške s upisom (npr. `HttpError 400`, `Invalid requests[...]`):**
      * Ovo je bio najizazovniji dio. Kod u `update_daily_record` je prilagođen za `pygsheets.insert_rows` i `worksheet.add_rows`. Obavezno je da imate najnoviji kod.
      * Ako i dalje imate probleme s upisom, provjerite `aplikacija_log.log` za detalje. Moguće su privremene mrežne smetnje ili API limiti.
  * **Serijska komunikacija (npr. `PortNotFound`, `AccessDenied`):**
      * Provjerite je li Dasduino Lite spojen na ispravan USB port i da je driver instaliran.
      * Provjerite da drugi programi (npr. Arduino Serial Monitor) ne koriste isti COM port.
      * Pokušajte promijeniti `SERIAL_PORT` u konfiguraciji (npr., s `''` na `'COM4'` ili obrnuto).
  * **Aplikacija se zamrzava/ne reagira:**
      * Provjerite da su `pyserial` i `pygsheets` instalirani unutar **aktivnog virtualnog okruženja**.
      * Osigurajte da su sve blokirajuće operacije (poput serijske komunikacije i Google Sheets poziva) unutar zasebnih niti kao što je implementirano u kodu.
  * **Problemi s e-mail izvještajem:**
      * Provjerite postavke emaila (adresa, lozinka, SMTP server/port).
      * Ako koristite Gmail, provjerite da ste postavili "App password" ako imate 2FA.
      * Provjerite log datoteku za greške SMTP servera.

### 8\. Buduća poboljšanja

  * **Administratorski panel:** Dodatni ekran za upravljanje korisnicima, pregled dnevnih/mjesečnih izvještaja direktno u aplikaciji.
  * **Vizualna poboljšanja:** Moderniji GUI dizajn koristeći biblioteke poput Kivy ili PyQt/PySide.
  * **Offline funkcionalnost:** Privremeno spremanje podataka lokalno i sinkronizacija s Google Sheetsom kada je mreža dostupna.
  * **Zvučni signali:** Dodavanje zvučnih efekata za potvrde/greške.
  * **Automatsko pokretanje na Raspberry Pi-ju:** Konfiguriranje `systemd` servisa.
  * **API limiti:** Robusnije rukovanje Google Sheets API limitima.

### 9\. Licenca

Ovaj projekt je otvorenog koda.
