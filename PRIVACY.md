# Informativa privacy – fitbit_reader

*Ultimo aggiornamento: 15 novembre 2026*

fitbit_reader è un programma per uso di ricerca che scarica i dati di un
dispositivo Fitbit tramite la Google Health API e li salva **solo sul computer di
chi lo usa**.

## Quali dati vengono letti
Solo con il consenso esplicito dell'utente, dato tramite la schermata di
autorizzazione Google, e **in sola lettura**:
- metriche sanitarie: battito cardiaco, variabilità della frequenza cardiaca,
  saturazione di ossigeno, temperatura cutanea, battito a riposo;
- attività fisica: passi, minuti attivi, distanza, periodi sedentari, esercizi;
- sonno: sessioni e fasi del sonno;
- elettrocardiogrammi (ECG) registrati dall'utente.

Il programma non modifica né cancella alcun dato sull'account Google.

## Dove sono conservati
- I dati sono salvati in file locali sul computer di chi esegue il programma.
- Non sono inviati a server dello sviluppatore né a terzi.
- Non sono venduti, né usati per pubblicità o profilazione commerciale.
- Il token di autorizzazione è conservato localmente e serve solo a scaricare
  i dati dell'utente che lo ha autorizzato.

## Uso dei dati
I dati sono usati esclusivamente per analisi di ricerca sull'andamento dei
parametri fisiologici dell'utente.

## Revoca del consenso
L'utente può revocare l'accesso in qualsiasi momento da
https://myaccount.google.com/permissions (voce "fitbit_reader"). Dopo la
revoca il programma non può più leggere alcun dato.

L'uso dei dati ricevuti dalle API Google rispetta le
[Google API Services User Data Policy](https://developers.google.com/terms/api-services-user-data-policy),
inclusi i requisiti di uso limitato (*Limited Use*).

## Contatti
Per domande aprire una segnalazione (issue) su
https://github.com/hicsuntleones/fitbit_reader/issues

---

## Privacy policy (English summary)

fitbit_reader is a research tool that reads, **read-only and with the user's
explicit consent**, Fitbit data (heart metrics, activity, sleep, ECG) through the
Google Health API and stores it **only on the user's own computer**. No data is
sent to the developer or to third parties, sold, or used for advertising. Access
can be revoked at any time at https://myaccount.google.com/permissions. Use of
data received from Google APIs adheres to the Google API Services User Data
Policy, including the Limited Use requirements. Contact: GitHub issues of this
repository.
