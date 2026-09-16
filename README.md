# FL-Entertainment

Distribuzione Kodi centralizzata per Android / Fire TV.

## Architettura

- **Windows Kodi master**: configurazione sorgente.
- **Bootstrap Kodi**: installato una sola volta sul device.
- **manifest.json**: indica la versione corrente e il payload da scaricare.
- **GitHub Release**: ospita il payload ZIP completo.
- **Kodi client**: scarica e applica il payload usando i propri permessi, senza scrivere in `Android/data` via ADB.

## Prima installazione client

Build bootstrap:

```powershell
.\scripts\build-bootstrap.ps1
```

Copia sul device:

```bat
adb push "dist\plugin.program.flentertainment.bootstrap-1.0.2.zip" "/sdcard/Download/"
```

Poi in Kodi:

```text
Add-on -> Installa da file ZIP -> Download -> plugin.program.flentertainment.bootstrap-1.0.2.zip
```

Apri **FL-Entertainment Bootstrap** e scegli **Installa / reinstalla FL-Entertainment**.

Il bootstrap usa già:

```text
https://raw.githubusercontent.com/flaigueglia85/FL-Entertainment/main/manifest.json
```

## Pubblicazione dal master Windows — one click

Clona la repo una volta:

```bat
cd C:\work
git clone https://github.com/flaigueglia85/FL-Entertainment.git
cd FL-Entertainment
```

Poi per pubblicare il master Kodi corrente:

```bat
PUBLISH_FROM_MASTER.bat 1.0.0
```

Lo script:

1. legge `%APPDATA%\Kodi`;
2. risolve gli addon portabili richiesti;
3. crea `dist\FL-Entertainment-payload-<version>.zip`;
4. esclude componenti binari Windows, cache e DB locali;
5. non pubblica cookies/sessioni e azzera credenziali/token/API key nei settings distribuiti;
6. installa GitHub CLI tramite `winget` se manca;
7. richiede il login GitHub CLI solo la prima volta;
8. crea/aggiorna la GitHub Release;
9. carica il payload come release asset;
10. aggiorna e pubblica `manifest.json`.

Per una nuova configurazione:

```bat
PUBLISH_FROM_MASTER.bat 1.0.1
```

## Build manuale del payload

```powershell
.\scripts\build-payload.ps1 -Version 1.0.0
```

Output:

```text
dist\FL-Entertainment-payload-1.0.0.zip
```

## Aggiornamenti client

Nel bootstrap Kodi:

```text
Controlla aggiornamenti
```

Se `manifest.json` contiene una versione nuova, il client scarica il payload della relativa GitHub Release e lo applica con i permessi di Kodi.

## Dati locali e account

- Trakt resta autenticato per-device.
- Cookies, sessioni, token e API key del master non vengono distribuiti nel payload pubblico.
- ADB serve solo per portare il bootstrap iniziale in `Download`.
- Gli aggiornamenti successivi arrivano da GitHub tramite il bootstrap.
