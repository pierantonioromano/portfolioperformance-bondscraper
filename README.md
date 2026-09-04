# Bond Scraper per Portfolio Performance 📈

Uno scraper automatico in Python per scaricare quotazioni giornaliere di obbligazioni (Borsa Italiana ed altre fonti) e generare file JSON storici pronti per **Portfolio Performance**.

Il progetto gira in automatico 1-2 volte al giorno tramite **GitHub Actions**, aggiornando i dati nel repository e su **GitHub Pages**.

---

## 🚀 Caratteristiche

- **Scraper Borsa Italiana integrato**: Risoluzione automatica degli URL MOT/EuroTLX semplicemente inserendo il codice ISIN.
- **Supporto Scraper Personalizzati**: Possibilità di definire selettori regex/CSS per qualsiasi altro sito finanziario.
- **Configurazione semplice**: Tutti i bond sono gestiti in `bonds.json`.
- **Integrazione Portfolio Performance**: Output JSON standard in formato `[{"date": "YYYY-MM-DDT00:00:00Z", "close": 102.34}]`.
- **Dashboard Web Integrata**: Interfaccia web moderna (`index.html`) per visualizzare grafici dei prezzi e copiare al volo gli URL di configurazione.
- **Automazione GitHub Actions**: Workflow schedulato che esegue lo scraper e committa i dati aggiornati senza interventi manuali.

---

## 🛠️ Come aggiungere nuovi Bond (`bonds.json`)

Tutte le obbligazioni da monitorare si trovano nel file [`bonds.json`](file:///Users/pierantonio/Sites/bondscraper/bonds.json).

### 1. Obbligazioni Borsa Italiana (Standard)
Per i titoli quotati su Borsa Italiana (MOT, EuroMOT, EuroTLX) basta indicare `isin`, `name` e `provider: "borsa_italiana"`:

```json
{
	"bonds": [
		{
			"isin": "AT0000A2VB47",
			"name": "Austria Tf 0% Ot28 Eur",
			"provider": "borsa_italiana"
		},
		{
			"isin": "IT0005565400",
			"name": "BTP Valore Oct 28",
			"provider": "borsa_italiana"
		}
	]
}
```

*Nota: Lo scraper cercherà e individuerà automaticamente l'URL corretto su Borsa Italiana.*

### 2. Fonti Personalizzate / Altri Siti
Se il titolo si trova su un altro sito o richiede un selettore specifico, puoi configurarlo così:

```json
{
	"isin": "DE0001102390",
	"name": "German Bund 2031",
	"url": "https://www.example.com/bond/DE0001102390",
	"provider": "custom",
	"selectors": {
		"price_regex": "Prezzo:\\s*([\\d,\\.]+)",
		"date_regex": "Data:\\s*(\\d{2}/\\d{2}/\\d{2})"
	}
}
```

---

## 📊 Configurazione su Portfolio Performance

In Portfolio Performance, configura la quotazione storica per il tuo titolo come segue:

1. Fai clic destro sul titolo &rarr; **Modifica** (Edit).
2. Vai nella scheda **Quotazioni storiche** (Historical Quotes).
3. Seleziona **Fornitore**: `JSON`.
4. Inserisci i parametri:
	- **URL del Feed**: 
	  `https://raw.githubusercontent.com/<TUO-UTENTE>/<TUO-REPO>/main/out/{ISIN}.json`
	  *(oppure l'URL di GitHub Pages: `https://<TUO-UTENTE>.github.io/<TUO-REPO>/out/{ISIN}.json`)*
	- **Path per la Data**: `$.[*].date`
	- **Path per l'Ultimo Prezzo**: `$.[*].close`

---

## 💻 Esecuzione Locale

Puoi eseguire lo scraper anche in locale:

```bash
# Installa le dipendenze
pip install -r requirements.txt

# Esegui lo scraper
python scraper.py
```

I risultati aggiornati verranno salvati nella cartella `out/`.

---

## ⚙️ Workflow GitHub Actions

Il workflow `.github/workflows/scrape.yml` viene eseguito:
- **In automatico**: Ogni giorno dal lunedì al venerdì alle 18:00 UTC (dopo la chiusura dei mercati).
- **Manualmente**: Dalla scheda *Actions* di GitHub premendo **Run workflow**.

---

## 📂 Struttura del Progetto

```
.
├── .github/workflows/scrape.yml # Workflow di automazione GitHub Actions
├── bonds.json                   # File di configurazione delle obbligazioni
├── scraper.py                   # Script principale di scraping in Python
├── requirements.txt             # Dipendenze Python
├── index.html                   # Dashboard web interattiva
├── out/                         # Cartella contenente i file JSON estratti
│   ├── index.json               # Sommario di tutte le obbligazioni e stato
│   ├── AT0000A2VB47.json        # Dati storici quotazioni per ISIN
│   └── IT0005565400.json
└── README.md
```
