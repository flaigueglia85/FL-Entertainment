# FL-Entertainment

Distribuzione Kodi centralizzata per Android / Fire TV.

## Architettura

- **Windows Kodi master**: configurazione sorgente.
- **Bootstrap Kodi**: installato una sola volta sul device.
- **manifest.json**: indica la versione corrente e il payload da scaricare.
- **GitHub Release**: ospita il payload ZIP completo.
- **Kodi client**: scarica e applica il payload usando i propri permessi, senza scrivere in `Android/data` via ADB.

## Prima installazione

1. Build bootstrap:

```powershell
.\scripts\build-bootstrap.ps1
```

2. Copia sul device:

```bat
adb push "dist\plugin.program.flentertainment.bootstrap-1.0.2.zip" "/sdcard/Download/"
```

3. In Kodi:

```text
Add-on -> Installa da file ZIP -> Download -> plugin.program.flentertainment.bootstrap-1.0.2.zip
```

4. Apri **FL-Entertainment Bootstrap** e scegli **Installa / reinstalla FL-Entertainment**.

Il manifest è già configurato su:

```text
https://raw.githubusercontent.com/flaigueglia85/FL-Entertainment/main/manifest.json
```

## Creare un payload dal master Windows

```powershell
.\scripts\build-payload.ps1 -Version 1.0.0
```

Output:

```text
dist\FL-Entertainment-payload-1.0.0.zip
```

Il builder include Arctic Fuse 3, Skin Variables, TMDb Helper, Stream4Me, bridge e dipendenze portabili, evitando componenti binari platform-specific, cache e database Kodi locali.

## Pubblicare una nuova versione

Prerequisiti:

```text
GitHub CLI (gh)
gh auth login
```

Poi:

```powershell
.\scripts\build-payload.ps1 -Version 1.0.1
.\scripts\publish-release.ps1 -Version 1.0.1
```

Lo script crea/aggiorna la GitHub Release e aggiorna `manifest.json`.

## Aggiornamenti client

Nel bootstrap Kodi:

```text
Controlla aggiornamenti
```

Se il manifest contiene una versione nuova, il client scarica il payload e lo applica.

## Note

- Trakt può restare autenticato per-device.
- ADB serve solo per portare il bootstrap iniziale in `Download`.
- Gli aggiornamenti successivi arrivano dal manifest pubblico.
