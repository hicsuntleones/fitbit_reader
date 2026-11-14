# fitbit_reader

Scarico giornaliero dei dati di un Fitbit Charge 5 tramite la **Google Health API**
in un archivio locale, per analisi con algoritmi propri.

## Cosa scarica

| Tipo | Contenuto |
|---|---|
| `heart-rate` | battito ogni pochi secondi, con contesto di movimento |
| `heart-rate-variability`, `daily-heart-rate-variability` | HRV (RMSSD) |
| `oxygen-saturation`, `daily-oxygen-saturation` | SpO2 |
| `daily-resting-heart-rate` | battito a riposo |
| `daily-sleep-temperature-derivations` | temperatura notturna della pelle |
| `steps`, `active-minutes`, `active-zone-minutes`, `distance`, `sedentary-period`, `exercise` | attività |
| `sleep` | sessioni di sonno con fasi |
| `electrocardiogram` | registrazioni ECG con forma d'onda (lead I) |

Elenco completo: `fitbit.bat types`.

## Installazione (una volta)

1. Metti il file delle credenziali OAuth (client "App desktop") in
   `client_secret.json` nella cartella del progetto. È escluso da git.
2. `setup_env.bat` crea `.venv` e installa il pacchetto.
3. `fitbit.bat auth` apre il browser per il consenso e salva il token in
   `.secrets\token.json`, anche questo escluso da git.
4. `fitbit.bat check` verifica il collegamento a Google Health e mostra i dispositivi.

## Uso

```bat
fitbit.bat sync                        :: giorni mancanti (al primo avvio: ultimi 30 giorni)
fitbit.bat sync --since 2024-01-01     :: scarica lo storico da una data
fitbit.bat sync --types heart-rate sleep
```

Ogni sync riscarica anche gli ultimi 3 giorni, per raccogliere i dati che il
braccialetto ha sincronizzato in ritardo. Il giorno corrente è sempre parziale.

### Scarico automatico giornaliero

```bat
schtasks /Create /SC DAILY /ST 09:00 /TN fitbit_reader_sync /TR "\"C:\Users\gricc\dev\fitbit_reader\sync_daily.bat\""
```

Il log viene scritto in `logs\sync.log`.

## Dashboard

`dashboard.bat` apre nel browser un'interfaccia locale (Streamlit) per confrontare
i dati tra le fasi dello studio: baseline, terapia, follow-up.

| Scheda | Contenuto |
|---|---|
| Andamento | marcatori giornalieri con media mobile e fasi colorate sullo sfondo |
| Confronto fasi | distribuzione per fase, Δ rispetto alla baseline, Hedges g, panoramica di tutti i marcatori |
| Giornata | battito, fasi del sonno e passi di un giorno, eventualmente sovrapposto a un altro |
| ECG | forma d'onda in mV con la griglia, classificazione Fitbit |
| Fasi ed esclusioni | date delle fasi, fase di riferimento, giorni da escludere, soglia di utilizzo |

I marcatori sono calcolati in `src/fitbit_reader/markers.py` e salvati nella cache
`data/derived/markers.json`. Ogni riga corrisponde alla **data di risveglio**. Fasi ed
esclusioni sono in `data/study.json`.

L'**indice di stress composito** è sperimentale: è la media degli z-score di HRV
notturna (invertita), battito a riposo e battito nel sonno, calcolati rispetto alla
baseline. Positivo = più stress del solito.

## Installazione su un nuovo PC

Git porta solo il codice. Credenziali, token, ambiente Python, dati e
pianificazione vanno ricreati o copiati a mano.

1. Installa **Python 3.10 o più recente** da python.org. L'installer include il
   comando `py`, usato da `setup_env.bat`.
2. Clona il repo e lancia `setup_env.bat`. Ricrea `.venv`, che non si copia
   perché contiene percorsi validi solo sul PC dove è stato creato.
3. Copia `client_secret.json` nella cartella del progetto.
4. Lancia `fitbit.bat auth`. Il token (`.secrets\token.json`) non è nel repo e
   va rifatto su ogni PC.
5. **Dati:** l'archivio `data\` (con `state.json`) non è nel repo. Puoi:
   - copiare `data\` dal vecchio PC, così il sync riprende da dove era rimasto;
   - oppure riscaricare lo storico, che resta su Google:
     `fitbit.bat sync --since <data>`. Senza `--since` il primo sync prende
     solo gli ultimi 30 giorni.
6. **Scarico automatico:** la pianificazione è un'impostazione di Windows e va
   ricreata. Dal prompt dei comandi (cmd), nella cartella del progetto:

   ```bat
   schtasks /Create /SC DAILY /ST 09:00 /TN fitbit_reader_sync /TR "\"%CD%\sync_daily.bat\""
   ```

Se usi più PC in parallelo, ognuno tiene un archivio separato. Conviene sceglierne
uno principale, oppure mettere `data\` in una cartella sincronizzata (per esempio
OneDrive) e usare `--data-dir`.

## Archivio (`data\`)

```
data\state.json                            ultimo giorno completo per ogni tipo
data\raw\<tipo>\<anno>\<YYYY-MM-DD>.json   risposta API integrale (fonte di verità)
data\csv\<tipo>\<anno>\<YYYY-MM-DD>.csv    stessi dati appiattiti
data\ecg\<anno>\<timestamp>_<id>.json      registrazione ECG integrale
data\ecg\<anno>\<timestamp>_<id>.csv       forma d'onda: t_s, mV, raw
```

## Note

- Finché l'app OAuth è in stato **Test**, Google fa scadere il token dopo 7 giorni.
  Pubblicala (Google Auth Platform → Pubblico → Pubblica app) per evitarlo.
- L'ECG va avviato a mano sul braccialetto: l'API serve solo a leggere.
- I dati EDA non sono esposti dalla Google Health API.
