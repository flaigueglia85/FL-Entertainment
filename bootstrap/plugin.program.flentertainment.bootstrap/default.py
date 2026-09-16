# -*- coding: utf-8 -*-
import os, sys, json, shutil, zipfile, tempfile, urllib.request, urllib.parse, gzip
import xml.etree.ElementTree as ET

import xbmc, xbmcaddon, xbmcgui, xbmcplugin, xbmcvfs

ADDON = xbmcaddon.Addon()
HANDLE = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else -1

HOME = xbmcvfs.translatePath("special://home/")
PROFILE = xbmcvfs.translatePath("special://profile/")
DATA = xbmcvfs.translatePath("special://profile/addon_data/%s/" % ADDON.getAddonInfo("id"))

DEFAULT_MANIFEST = "https://raw.githubusercontent.com/flaigueglia85/FL-Entertainment/main/manifest.json"
VERSION_FILE = os.path.join(DATA, "installed_version.txt")

TARGET_SKIN = "skin.arctic.fuse.3"
S4ME_ID = "plugin.video.s4me"
S4ME_STABLE_ZIP = "https://github.com/Stream4me/addon/archive/refs/heads/stable.zip"
BRIDGE_ID = "plugin.video.s4me.bridge"

JURIAL_INDEX = "https://raw.githubusercontent.com/jurialmunkey/repository.jurialmunkey/master/omega/zips/addons.xml"
JURIAL_BASE = "https://raw.githubusercontent.com/jurialmunkey/repository.jurialmunkey/master/omega/zips/"

KODI_INDEX_GZ = "https://mirrors.kodi.tv/addons/omega/addons.xml.gz"
KODI_BASE = "https://mirrors.kodi.tv/addons/omega/"

MIN_PAYLOAD_MAJOR = 2
USER_AGENT = "Kodi FL-Entertainment Bootstrap/2.0.2"

INDEX_CACHE = None
INSTALLING = set()
INSTALLED_THIS_RUN = []


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def dialog(title, message):
    xbmcgui.Dialog().ok(title, message)


def notify(message):
    xbmcgui.Dialog().notification("FL-Entertainment", message, xbmcgui.NOTIFICATION_INFO, 3500)


def log(message):
    xbmc.log("[FL-Entertainment] %s" % message, xbmc.LOGINFO)


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


def addon_xml_path(addon_id):
    return os.path.join(addon_path(addon_id), "addon.xml")


def addon_present(addon_id):
    return os.path.isfile(addon_xml_path(addon_id))


def enable_addon(addon_id):
    return "error" not in rpc("Addons.SetAddonEnabled", {"addonid": addon_id, "enabled": True})


def get_manifest_url():
    try:
        value = ADDON.getSetting("manifest_url")
    except Exception:
        value = ""
    return (value or "").strip() or DEFAULT_MANIFEST


def download_bytes(url, timeout=120):
    log("GET %s" % url)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()


def download(url, dest, timeout=120):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as response, open(dest, "wb") as f:
        shutil.copyfileobj(response, f)


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
    data = download_bytes(get_manifest_url())
    return json.loads(data.decode("utf-8-sig"))


def safe_extract(zip_path, dest_root):
    root = os.path.abspath(dest_root)
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.infolist():
            name = member.filename.replace("\\", "/")
            if name.startswith("/") or ".." in name.split("/"):
                raise RuntimeError("Percorso ZIP non sicuro: %s" % member.filename)
            target = os.path.abspath(os.path.join(dest_root, *name.split("/")))
            if not (target == root or target.startswith(root + os.sep)):
                raise RuntimeError("Percorso ZIP non sicuro: %s" % member.filename)
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


def parse_addons_index(xml_bytes, source, base_url):
    root = ET.fromstring(xml_bytes)
    result = {}
    for addon in root.findall("addon"):
        addon_id = addon.get("id")
        version = addon.get("version", "")
        if not addon_id:
            continue
        result[addon_id] = {
            "id": addon_id,
            "version": version,
            "source": source,
            "base_url": base_url,
            "xml": addon,
        }
    return result


def get_indexes():
    global INDEX_CACHE
    if INDEX_CACHE is not None:
        return INDEX_CACHE

    jurial_raw = download_bytes(JURIAL_INDEX)
    jurial = parse_addons_index(jurial_raw, "JurialMunkey", JURIAL_BASE)

    kodi_raw = download_bytes(KODI_INDEX_GZ)
    try:
        kodi_raw = gzip.decompress(kodi_raw)
    except OSError:
        pass
    kodi = parse_addons_index(kodi_raw, "Kodi", KODI_BASE)

    merged = {}
    merged.update(kodi)
    merged.update(jurial)
    INDEX_CACHE = merged
    log("Indici caricati: Jurial=%d Kodi=%d" % (len(jurial), len(kodi)))
    return INDEX_CACHE


def dependency_list(addon_node):
    deps = []
    requires = addon_node.find("requires")
    if requires is None:
        return deps
    for imp in requires.findall("import"):
        addon_id = imp.get("addon", "").strip()
        optional = (imp.get("optional", "false").lower() == "true")
        if not addon_id or optional or addon_id.startswith("xbmc."):
            continue
        deps.append(addon_id)
    return deps


def package_url(meta):
    addon_id = meta["id"]
    version = meta["version"]
    return "%s%s/%s-%s.zip" % (meta["base_url"], addon_id, addon_id, version)


def install_zip_folder(url, target_addon_id):
    tmp = tempfile.mkdtemp(prefix="fl-addon-")
    try:
        zpath = os.path.join(tmp, "addon.zip")
        extracted = os.path.join(tmp, "extracted")
        download(url, zpath)
        safe_extract(zpath, extracted)

        candidates = []
        for root, dirs, files in os.walk(extracted):
            if "addon.xml" not in files:
                continue
            try:
                node = ET.parse(os.path.join(root, "addon.xml")).getroot()
                if node.get("id") == target_addon_id:
                    candidates.append(root)
            except Exception:
                pass

        if not candidates:
            raise RuntimeError("ZIP %s non contiene addon %s" % (url, target_addon_id))

        source = sorted(candidates, key=lambda p: len(p))[0]
        target = addon_path(target_addon_id)

        if os.path.isdir(target):
            shutil.rmtree(target, ignore_errors=True)
        shutil.copytree(source, target)

        if not addon_present(target_addon_id):
            raise RuntimeError("Installazione incompleta: %s" % target_addon_id)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def install_official_addon(addon_id):
    if addon_id.startswith("xbmc."):
        return

    if addon_present(addon_id):
        enable_addon(addon_id)
        return

    if addon_id in INSTALLING:
        raise RuntimeError("Dipendenza circolare: %s" % addon_id)

    indexes = get_indexes()
    meta = indexes.get(addon_id)
    if meta is None:
        raise RuntimeError("Addon non trovato nei repository ufficiali: %s" % addon_id)

    INSTALLING.add(addon_id)
    try:
        for dep_id in dependency_list(meta["xml"]):
            install_official_addon(dep_id)

        url = package_url(meta)
        log("Install %s %s da %s" % (addon_id, meta["version"], meta["source"]))
        install_zip_folder(url, addon_id)
        INSTALLED_THIS_RUN.append("%s %s" % (addon_id, meta["version"]))

        xbmc.executebuiltin("UpdateLocalAddons")
        xbmc.sleep(600)
        enable_addon(addon_id)
    finally:
        INSTALLING.discard(addon_id)


def ensure_arctic_stack():
    install_official_addon(TARGET_SKIN)

    required = [
        "script.skinvariables",
        "script.texturemaker",
        "plugin.video.themoviedb.helper",
        "resource.images.weathericons.white",
        "resource.images.studios.coloured",
        "resource.font.robotocjksc",
    ]
    for addon_id in required:
        install_official_addon(addon_id)

    xbmc.executebuiltin("UpdateLocalAddons")
    xbmc.sleep(1000)

    missing = [addon_id for addon_id in [TARGET_SKIN] + required if not addon_present(addon_id)]
    if missing:
        raise RuntimeError("Stack Arctic incompleto: " + ", ".join(missing))


def ensure_stream4me(reset_defaults=False):
    valid = addon_present(S4ME_ID) and os.path.isfile(os.path.join(addon_path(S4ME_ID), "service.py"))
    if not valid:
        install_zip_folder(S4ME_STABLE_ZIP, S4ME_ID)

    xbmc.executebuiltin("UpdateLocalAddons")
    xbmc.sleep(700)
    enable_addon(S4ME_ID)

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
    xbmc.sleep(800)
    if addon_present(BRIDGE_ID):
        enable_addon(BRIDGE_ID)


def activate_skin():
    if not addon_present(TARGET_SKIN):
        return False
    xbmc.executebuiltin("UpdateLocalAddons")
    xbmc.sleep(1000)
    result = rpc("Settings.SetSettingValue", {"setting": "lookandfeel.skin", "value": TARGET_SKIN})
    return "error" not in result


def install_or_update(force=False):
    progress = None
    tmpdir = None
    try:
        manifest = fetch_manifest()
        remote_version = str(manifest.get("version", "")).strip()
        if version_major(remote_version) < MIN_PAYLOAD_MAJOR:
            raise RuntimeError("Manifest ancora legacy (%s)." % (remote_version or "senza versione"))

        installed = current_version()
        if remote_version and installed == remote_version and not force:
            notify("FL-Entertainment gia' aggiornato: %s" % remote_version)
            return

        payload = manifest.get("payload_url") or manifest.get("payload")
        if not payload:
            raise RuntimeError("payload_url mancante nel manifest")
        payload_url = urllib.parse.urljoin(get_manifest_url(), payload)

        progress = xbmcgui.DialogProgress()
        progress.create("FL-Entertainment", "Installazione 2.0.2...")

        progress.update(10, "Caricamento repository ufficiali...")
        get_indexes()

        progress.update(20, "Arctic Fuse 3 + dipendenze...")
        ensure_arctic_stack()

        progress.update(65, "Stream4Me stable...")
        ensure_stream4me(reset_defaults=(version_major(installed) < 2))

        progress.update(76, "Download configurazione FL-Entertainment...")
        tmpdir = tempfile.mkdtemp(prefix="fl-download-")
        payload_zip = os.path.join(tmpdir, "payload.zip")
        download(payload_url, payload_zip)

        progress.update(86, "Widget, impostazioni e bridge...")
        apply_custom_payload(payload_zip)

        progress.update(96, "Attivazione Arctic Fuse 3...")
        if not activate_skin():
            raise RuntimeError("Arctic Fuse 3 installata ma Kodi non l'ha attivata")

        if remote_version:
            write_version(remote_version)

        progress.update(100, "Completato")
        xbmc.sleep(500)

        if xbmcgui.Dialog().yesno(
            "FL-Entertainment",
            "Installazione completata (%s).\n\nArctic Fuse 3 + dipendenze: OK\nStream4Me stable: OK\nLingua S4Me: ITA\nConfig FL + bridge: OK\n\nRiavviare Kodi ora?" % remote_version
        ):
            xbmc.executebuiltin("RestartApp")

    except Exception as exc:
        log("ERRORE: %s" % exc)
        dialog("FL-Entertainment", "Installazione fallita:\n%s" % exc)
    finally:
        if progress:
            try:
                progress.close()
            except Exception:
                pass
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
        dialog("FL-Entertainment", "Bootstrap 2.0.2 attivo.\nManifest: %s" % get_manifest_url())
    else:
        add_item("Installa / reinstalla FL-Entertainment", "install")
        add_item("Controlla aggiornamenti", "update")
        add_item("Impostazioni", "settings")
        add_item("Test bootstrap", "test")
        xbmcplugin.addDirectoryItem(
            HANDLE,
            "",
            xbmcgui.ListItem(label="Versione FL installata: %s" % (current_version() or "nessuna")),
            isFolder=False
        )

    xbmcplugin.endOfDirectory(HANDLE)


if __name__ == "__main__":
    main()
