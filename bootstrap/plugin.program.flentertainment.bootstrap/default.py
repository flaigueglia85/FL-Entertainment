# -*- coding: utf-8 -*-
import os, sys, json, shutil, zipfile, tempfile, urllib.request, urllib.parse
import xbmc, xbmcaddon, xbmcgui, xbmcplugin, xbmcvfs

ADDON = xbmcaddon.Addon()
HANDLE = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else -1
HOME = xbmcvfs.translatePath("special://home/")
PROFILE = xbmcvfs.translatePath("special://profile/")
DATA = xbmcvfs.translatePath("special://profile/addon_data/%s/" % ADDON.getAddonInfo("id"))
DEFAULT_MANIFEST = "https://raw.githubusercontent.com/flaigueglia85/FL-Entertainment/main/manifest.json"
VERSION_FILE = os.path.join(DATA, "installed_version.txt")
TARGET_SKIN = "skin.arctic.fuse.3"

PORTABLE_ADDONS = [
    "plugin.video.s4me",
    "plugin.video.s4me.bridge",
    "plugin.video.themoviedb.helper",
    "repository.jurialmunkey",
    "resource.font.robotocjksc",
    "resource.images.studios.coloured",
    "resource.images.weathericons.white",
    "script.module.addon.signals",
    "script.module.certifi",
    "script.module.chardet",
    "script.module.idna",
    "script.module.infotagger",
    "script.module.jurialmunkey",
    "script.module.qrcode",
    "script.module.requests",
    "script.module.six",
    "script.module.urllib3",
    "script.skinvariables",
    "script.texturemaker",
    "skin.arctic.fuse.3"
]


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def dialog(title, message):
    xbmcgui.Dialog().ok(title, message)


def notify(message):
    xbmcgui.Dialog().notification("FL-Entertainment", message, xbmcgui.NOTIFICATION_INFO, 3500)


def rpc(method, params=None):
    req = {"jsonrpc": "2.0", "method": method, "id": 1}
    if params is not None:
        req["params"] = params
    raw = xbmc.executeJSONRPC(json.dumps(req))
    try:
        return json.loads(raw)
    except Exception:
        return {"error": {"message": raw or "Risposta JSON-RPC non valida"}}


def get_manifest_url():
    try:
        value = ADDON.getSetting("manifest_url")
    except Exception:
        value = ""
    return (value or "").strip() or DEFAULT_MANIFEST


def download(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "Kodi FL-Entertainment Bootstrap/1.0.4"})
    with urllib.request.urlopen(req, timeout=45) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)


def current_version():
    try:
        with open(VERSION_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def write_version(version):
    ensure_dir(DATA)
    with open(VERSION_FILE, "w", encoding="utf-8") as f:
        f.write(version or "")


def fetch_manifest():
    tmp = tempfile.mktemp(prefix="fl-manifest-", suffix=".json")
    try:
        download(get_manifest_url(), tmp)
        with open(tmp, "r", encoding="utf-8") as f:
            return json.load(f)
    finally:
        try: os.remove(tmp)
        except Exception: pass


def safe_extract(zip_path, dest_root):
    root = os.path.abspath(dest_root)
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.infolist():
            target = os.path.abspath(os.path.join(dest_root, member.filename))
            if not (target == root or target.startswith(root + os.sep)):
                raise ValueError("Percorso ZIP non sicuro: %s" % member.filename)
        zf.extractall(dest_root)


def copy_tree_contents(src_root, dst_root):
    if not os.path.isdir(src_root):
        return
    ensure_dir(dst_root)
    for name in os.listdir(src_root):
        src = os.path.join(src_root, name)
        dst = os.path.join(dst_root, name)
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)


def apply_payload(payload_zip):
    tmp = tempfile.mkdtemp(prefix="fl-payload-")
    try:
        safe_extract(payload_zip, tmp)
        copy_tree_contents(os.path.join(tmp, "addons"), os.path.join(HOME, "addons"))
        copy_tree_contents(os.path.join(tmp, "userdata"), PROFILE)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def activate_installed_configuration():
    # Copiare le cartelle addon non equivale ad abilitarle in Kodi. Registriamo
    # prima gli addon locali, poi li abilitiamo tramite l'API JSON-RPC nativa.
    xbmc.executebuiltin("UpdateLocalAddons")
    xbmc.executebuiltin("UpdateAddonRepos")
    xbmc.sleep(2500)

    failed = []
    enabled = 0
    for addon_id in PORTABLE_ADDONS:
        if not os.path.isdir(os.path.join(HOME, "addons", addon_id)):
            continue
        result = rpc("Addons.SetAddonEnabled", {"addonid": addon_id, "enabled": True})
        if "error" in result:
            failed.append(addon_id)
        else:
            enabled += 1

    skin_result = rpc("Settings.SetSettingValue", {
        "setting": "lookandfeel.skin",
        "value": TARGET_SKIN
    })
    skin_ok = "error" not in skin_result

    return enabled, failed, skin_ok


def repair_activation():
    try:
        progress = xbmcgui.DialogProgress()
        progress.create("FL-Entertainment", "Attivazione configurazione...")
        try:
            progress.update(20, "Registrazione addon locali...")
            xbmc.executebuiltin("UpdateLocalAddons")
            xbmc.sleep(1500)
            progress.update(55, "Abilitazione addon...")
            enabled, failed, skin_ok = activate_installed_configuration()
            progress.update(100, "Completato")
            xbmc.sleep(300)
        finally:
            progress.close()

        message = "Addon abilitati: %d\nArctic Fuse 3: %s" % (enabled, "attivata" if skin_ok else "NON attivata")
        if failed:
            message += "\n\nNon abilitati: " + ", ".join(failed[:5])
        message += "\n\nRiavviare Kodi ora?"
        if xbmcgui.Dialog().yesno("FL-Entertainment", message):
            xbmc.executebuiltin("RestartApp")
    except Exception as exc:
        dialog("FL-Entertainment", "Riparazione fallita:\n%s" % exc)


def install_or_update(force=False):
    try:
        manifest = fetch_manifest()
        remote_version = str(manifest.get("version", "")).strip()
        installed = current_version()
        if remote_version and installed == remote_version and not force:
            notify("Configurazione già aggiornata: %s" % remote_version)
            return

        payload = manifest.get("payload_url") or manifest.get("payload")
        if not payload:
            raise ValueError("payload_url mancante nel manifest")
        payload_url = urllib.parse.urljoin(get_manifest_url(), payload)

        progress = xbmcgui.DialogProgress()
        progress.create("FL-Entertainment", "Download configurazione...")
        tmpdir = tempfile.mkdtemp(prefix="fl-download-")
        payload_zip = os.path.join(tmpdir, "payload.zip")
        try:
            progress.update(10, "Download payload...")
            download(payload_url, payload_zip)
            progress.update(50, "Installazione configurazione...")
            apply_payload(payload_zip)
            progress.update(75, "Registrazione e abilitazione addon...")
            enabled, failed, skin_ok = activate_installed_configuration()
            if remote_version:
                write_version(remote_version)
            progress.update(100, "Completato")
            xbmc.sleep(400)
        finally:
            progress.close()
            shutil.rmtree(tmpdir, ignore_errors=True)

        msg = "Installazione completata%s.\nAddon abilitati: %d\nArctic Fuse 3: %s" % (
            (" (" + remote_version + ")") if remote_version else "",
            enabled,
            "attivata" if skin_ok else "NON attivata"
        )
        if failed:
            msg += "\nAlcuni addon richiedono verifica dopo il riavvio."
        msg += "\n\nRiavviare Kodi ora?"
        if xbmcgui.Dialog().yesno("FL-Entertainment", msg):
            xbmc.executebuiltin("RestartApp")
    except Exception as exc:
        dialog("FL-Entertainment", "Installazione fallita:\n%s" % exc)


def add_item(label, action):
    url = sys.argv[0] + "?" + urllib.parse.urlencode({"action": action})
    xbmcplugin.addDirectoryItem(HANDLE, url, xbmcgui.ListItem(label=label), isFolder=True)


def main():
    if HANDLE < 0:
        return
    params = urllib.parse.parse_qs(sys.argv[2][1:] if len(sys.argv) > 2 else "")
    action = params.get("action", [""])[0]

    if action == "install":
        install_or_update(True)
    elif action == "update":
        install_or_update(False)
    elif action == "repair":
        repair_activation()
    elif action == "settings":
        ADDON.openSettings()
    elif action == "test":
        dialog("FL-Entertainment", "Bootstrap attivo e manifest configurato.")
    else:
        add_item("Installa / reinstalla FL-Entertainment", "install")
        add_item("Ripara / attiva UI già installata", "repair")
        add_item("Controlla aggiornamenti", "update")
        add_item("Impostazioni", "settings")
        add_item("Test bootstrap", "test")
        xbmcplugin.addDirectoryItem(HANDLE, "", xbmcgui.ListItem(label="Versione installata: %s" % (current_version() or "nessuna")), isFolder=False)

    xbmcplugin.endOfDirectory(HANDLE)


if __name__ == "__main__":
    main()
