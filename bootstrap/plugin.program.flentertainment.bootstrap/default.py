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
JURIAL_REPO_ID = "repository.jurialmunkey"
JURIAL_REPO_ZIP = "https://jurialmunkey.github.io/repository.jurialmunkey/repository.jurialmunkey-3.4.zip"
S4ME_ID = "plugin.video.s4me"
S4ME_STABLE_ZIP = "https://github.com/Stream4me/addon/archive/refs/heads/stable.zip"
BRIDGE_ID = "plugin.video.s4me.bridge"
MIN_PAYLOAD_MAJOR = 2


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


def addon_path(addon_id):
    return os.path.join(HOME, "addons", addon_id)


def addon_present(addon_id):
    return os.path.isfile(os.path.join(addon_path(addon_id), "addon.xml"))


def enable_addon(addon_id):
    result = rpc("Addons.SetAddonEnabled", {"addonid": addon_id, "enabled": True})
    return "error" not in result


def get_manifest_url():
    try:
        value = ADDON.getSetting("manifest_url")
    except Exception:
        value = ""
    return (value or "").strip() or DEFAULT_MANIFEST


def download(url, dest, timeout=90):
    req = urllib.request.Request(url, headers={"User-Agent": "Kodi FL-Entertainment Bootstrap/2.0.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r, open(dest, "wb") as f:
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


def version_major(value):
    try:
        return int(str(value).split(".")[0])
    except Exception:
        return 0


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


def install_zip_folder(url, target_addon_id):
    tmp = tempfile.mkdtemp(prefix="fl-addon-")
    try:
        zpath = os.path.join(tmp, "addon.zip")
        extracted = os.path.join(tmp, "extracted")
        download(url, zpath)
        safe_extract(zpath, extracted)

        candidates = []
        for root, dirs, files in os.walk(extracted):
            if "addon.xml" in files:
                candidates.append(root)
        if not candidates:
            raise RuntimeError("ZIP senza addon.xml: %s" % url)

        # Prefer exact folder/addon id if present; otherwise first addon root.
        source = None
        for candidate in candidates:
            if os.path.basename(candidate) == target_addon_id:
                source = candidate
                break
        if source is None:
            source = candidates[0]

        target = addon_path(target_addon_id)
        if os.path.isdir(target):
            shutil.rmtree(target, ignore_errors=True)
        shutil.copytree(source, target)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    xbmc.executebuiltin("UpdateLocalAddons")
    xbmc.sleep(1200)
    enable_addon(target_addon_id)


def ensure_jurial_repo():
    if not addon_present(JURIAL_REPO_ID):
        install_zip_folder(JURIAL_REPO_ZIP, JURIAL_REPO_ID)
    enable_addon(JURIAL_REPO_ID)
    xbmc.executebuiltin("UpdateAddonRepos")
    xbmc.sleep(3000)


def ensure_kodi_addon(addon_id, timeout=180):
    if addon_present(addon_id):
        enable_addon(addon_id)
        return True

    xbmc.executebuiltin("InstallAddon(%s)" % addon_id)
    elapsed = 0
    while elapsed < timeout:
        if addon_present(addon_id):
            xbmc.sleep(1000)
            enable_addon(addon_id)
            return True
        xbmc.sleep(1000)
        elapsed += 1
    return False


def ensure_arctic_stack():
    ensure_jurial_repo()
    if not ensure_kodi_addon(TARGET_SKIN):
        raise RuntimeError("Kodi non ha completato l'installazione di Arctic Fuse 3")

    # Sono dipendenze dichiarate dalla skin. Normalmente Kodi le installa da solo;
    # questi check servono solo a non proseguire se una dipendenza non e' ancora pronta.
    required = [
        "script.skinvariables",
        "script.texturemaker",
        "plugin.video.themoviedb.helper",
        "resource.images.weathericons.white",
        "resource.images.studios.coloured",
        "resource.font.robotocjksc"
    ]
    missing = []
    for addon_id in required:
        if not ensure_kodi_addon(addon_id, timeout=90):
            missing.append(addon_id)
    if missing:
        raise RuntimeError("Dipendenze Arctic mancanti: " + ", ".join(missing))


def ensure_stream4me(reset_defaults=False):
    # L'installer ufficiale S4Me scarica a sua volta il branch stable da GitHub.
    # Qui facciamo direttamente lo stesso passaggio, senza schermate iniziali.
    valid = addon_present(S4ME_ID) and os.path.isfile(os.path.join(addon_path(S4ME_ID), "service.py"))
    if not valid:
        install_zip_folder(S4ME_STABLE_ZIP, S4ME_ID)

    xbmc.executebuiltin("UpdateLocalAddons")
    xbmc.sleep(1200)
    enable_addon(S4ME_ID)

    # Prima installazione / migrazione dal vecchio bootstrap: tutte le preferenze
    # restano ai default S4Me; imponiamo solo i canali italiani.
    if reset_defaults:
        settings_file = os.path.join(PROFILE, "addon_data", S4ME_ID, "settings.xml")
        try:
            if os.path.isfile(settings_file):
                os.remove(settings_file)
        except Exception:
            pass
        xbmc.sleep(250)

    s4me = xbmcaddon.Addon(S4ME_ID)
    s4me.setSetting("channel_language", "ita")


def apply_custom_payload(payload_zip):
    tmp = tempfile.mkdtemp(prefix="fl-config-")
    try:
        safe_extract(payload_zip, tmp)
        copy_tree_contents(os.path.join(tmp, "addons"), os.path.join(HOME, "addons"))
        copy_tree_contents(os.path.join(tmp, "userdata"), PROFILE)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    xbmc.executebuiltin("UpdateLocalAddons")
    xbmc.sleep(1200)
    if addon_present(BRIDGE_ID):
        enable_addon(BRIDGE_ID)


def activate_skin():
    if not addon_present(TARGET_SKIN):
        return False
    result = rpc("Settings.SetSettingValue", {"setting": "lookandfeel.skin", "value": TARGET_SKIN})
    return "error" not in result


def install_or_update(force=False):
    progress = None
    tmpdir = None
    try:
        manifest = fetch_manifest()
        remote_version = str(manifest.get("version", "")).strip()
        if version_major(remote_version) < MIN_PAYLOAD_MAJOR:
            raise RuntimeError("Manifest ancora legacy (%s). Pubblica prima FL-Entertainment 2.x." % (remote_version or "senza versione"))

        installed = current_version()
        if remote_version and installed == remote_version and not force:
            notify("FL-Entertainment gia' aggiornato: %s" % remote_version)
            return

        payload = manifest.get("payload_url") or manifest.get("payload")
        if not payload:
            raise RuntimeError("payload_url mancante nel manifest")
        payload_url = urllib.parse.urljoin(get_manifest_url(), payload)

        progress = xbmcgui.DialogProgress()
        progress.create("FL-Entertainment", "Preparazione installazione pulita...")

        progress.update(8, "Repository JurialMunkey...")
        ensure_jurial_repo()

        progress.update(20, "Installazione Arctic Fuse 3 e dipendenze...")
        ensure_arctic_stack()

        progress.update(58, "Stream4Me stable...")
        # Reset solo su prima installazione o migrazione dalla vecchia architettura 1.x.
        ensure_stream4me(reset_defaults=(version_major(installed) < 2))

        progress.update(72, "Download configurazione FL-Entertainment...")
        tmpdir = tempfile.mkdtemp(prefix="fl-download-")
        payload_zip = os.path.join(tmpdir, "payload.zip")
        download(payload_url, payload_zip)

        progress.update(82, "Applicazione widget, skin settings e bridge...")
        apply_custom_payload(payload_zip)

        progress.update(94, "Attivazione Arctic Fuse 3...")
        if not activate_skin():
            raise RuntimeError("Arctic Fuse 3 installata ma Kodi non l'ha attivata")

        if remote_version:
            write_version(remote_version)
        progress.update(100, "Completato")
        xbmc.sleep(500)

        if xbmcgui.Dialog().yesno(
            "FL-Entertainment",
            "Installazione completata (%s).\n\nArctic Fuse 3 + dipendenze: OK\nStream4Me stable: OK\nLingua canali S4Me: ITA\nConfig FL + bridge: OK\n\nRiavviare Kodi ora?" % remote_version
        ):
            xbmc.executebuiltin("RestartApp")
    except Exception as exc:
        dialog("FL-Entertainment", "Installazione fallita:\n%s" % exc)
    finally:
        if progress:
            try: progress.close()
            except Exception: pass
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)


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
        dialog("FL-Entertainment", "Bootstrap 2.0 attivo.\nManifest: %s" % get_manifest_url())
    else:
        add_item("Installa / reinstalla FL-Entertainment", "install")
        add_item("Controlla aggiornamenti", "update")
        add_item("Impostazioni", "settings")
        add_item("Test bootstrap", "test")
        xbmcplugin.addDirectoryItem(HANDLE, "", xbmcgui.ListItem(label="Versione FL installata: %s" % (current_version() or "nessuna")), isFolder=False)

    xbmcplugin.endOfDirectory(HANDLE)


if __name__ == "__main__":
    main()
