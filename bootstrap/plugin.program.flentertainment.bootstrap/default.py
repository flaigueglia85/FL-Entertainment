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


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def dialog(title, message):
    xbmcgui.Dialog().ok(title, message)


def notify(message):
    xbmcgui.Dialog().notification("FL-Entertainment", message, xbmcgui.NOTIFICATION_INFO, 3500)


def get_manifest_url():
    # Kodi builds can reject getSettingString() for settings represented by the
    # generic settings backend. getSetting() is compatible across Kodi 19-21
    # and always returns the string value we need here.
    try:
        value = ADDON.getSetting("manifest_url")
    except Exception:
        value = ""
    return (value or "").strip() or DEFAULT_MANIFEST


def download(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "Kodi FL-Entertainment Bootstrap/1.0.3"})
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
            progress.update(15, "Download payload...")
            download(payload_url, payload_zip)
            progress.update(55, "Installazione configurazione...")
            apply_payload(payload_zip)
            progress.update(85, "Aggiornamento addon Kodi...")
            xbmc.executebuiltin("UpdateLocalAddons")
            xbmc.executebuiltin("UpdateAddonRepos")
            if remote_version:
                write_version(remote_version)
            progress.update(100, "Completato")
            xbmc.sleep(400)
        finally:
            progress.close()
            shutil.rmtree(tmpdir, ignore_errors=True)

        if xbmcgui.Dialog().yesno("FL-Entertainment", "Installazione completata%s.\n\nRiavviare Kodi ora?" % ((" (" + remote_version + ")") if remote_version else "")):
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
    elif action == "settings":
        ADDON.openSettings()
    elif action == "test":
        dialog("FL-Entertainment", "Bootstrap attivo e manifest configurato.")
    else:
        add_item("Installa / reinstalla FL-Entertainment", "install")
        add_item("Controlla aggiornamenti", "update")
        add_item("Impostazioni", "settings")
        add_item("Test bootstrap", "test")
        xbmcplugin.addDirectoryItem(HANDLE, "", xbmcgui.ListItem(label="Versione installata: %s" % (current_version() or "nessuna")), isFolder=False)

    xbmcplugin.endOfDirectory(HANDLE)


if __name__ == "__main__":
    main()
