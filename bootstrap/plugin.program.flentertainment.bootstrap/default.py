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
TMDB_ID = "plugin.video.themoviedb.helper"
SKINVARS_ID = "script.skinvariables"
S4ME_ID = "plugin.video.s4me"
S4ME_STABLE_ZIP = "https://github.com/Stream4me/addon/archive/refs/heads/stable.zip"
BRIDGE_ID = "plugin.video.s4me.bridge"
JURIAL_INDEX = "https://raw.githubusercontent.com/jurialmunkey/repository.jurialmunkey/master/omega/zips/addons.xml"
JURIAL_BASE = "https://raw.githubusercontent.com/jurialmunkey/repository.jurialmunkey/master/omega/zips/"
KODI_INDEX_GZ = "https://mirrors.kodi.tv/addons/omega/addons.xml.gz"
KODI_BASE = "https://mirrors.kodi.tv/addons/omega/"
MIN_PAYLOAD_MAJOR = 2
BOOTSTRAP_VERSION = "2.1.0"
USER_AGENT = "Kodi FL-Entertainment Bootstrap/%s" % BOOTSTRAP_VERSION
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

def addon_known(addon_id):
    if addon_present(addon_id):
        return True
    try:
        xbmcaddon.Addon(addon_id)
        return True
    except Exception:
        pass
    return "result" in rpc("Addons.GetAddonDetails", {"addonid": addon_id, "properties": ["version", "enabled"]})

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
    log("GET %s" % url)
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

def manifest_payload_url(manifest):
    payload = manifest.get("payload_url") or manifest.get("payload")
    if not payload:
        raise RuntimeError("payload_url mancante nel manifest")
    return urllib.parse.urljoin(get_manifest_url(), payload)

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
        return False
    ensure_dir(dst_root)
    for name in os.listdir(src_root):
        src = os.path.join(src_root, name)
        dst = os.path.join(dst_root, name)
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
    return True

def parse_addons_index(xml_bytes, source, base_url):
    root = ET.fromstring(xml_bytes)
    result = {}
    for addon in root.findall("addon"):
        addon_id = addon.get("id")
        version = addon.get("version", "")
        if addon_id:
            result[addon_id] = {"id": addon_id, "version": version, "source": source, "base_url": base_url, "xml": addon}
    return result

def get_indexes():
    global INDEX_CACHE
    if INDEX_CACHE is not None:
        return INDEX_CACHE
    jurial = parse_addons_index(download_bytes(JURIAL_INDEX), "JurialMunkey", JURIAL_BASE)
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
        optional = imp.get("optional", "false").lower() == "true"
        if addon_id and not optional and not addon_id.startswith("xbmc."):
            deps.append(addon_id)
    return deps

def package_url(meta):
    return "%s%s/%s-%s.zip" % (meta["base_url"], meta["id"], meta["id"], meta["version"])

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
    if addon_known(addon_id):
        enable_addon(addon_id)
        return
    if addon_id in INSTALLING:
        raise RuntimeError("Dipendenza circolare: %s" % addon_id)
    meta = get_indexes().get(addon_id)
    if meta is None:
        raise RuntimeError("Addon non trovato nei repository ufficiali: %s" % addon_id)
    INSTALLING.add(addon_id)
    try:
        for dep_id in dependency_list(meta["xml"]):
            install_official_addon(dep_id)
        log("Install %s %s da %s" % (addon_id, meta["version"], meta["source"]))
        install_zip_folder(package_url(meta), addon_id)
        INSTALLED_THIS_RUN.append("%s %s" % (addon_id, meta["version"]))
        xbmc.executebuiltin("UpdateLocalAddons")
        xbmc.sleep(600)
        enable_addon(addon_id)
    finally:
        INSTALLING.discard(addon_id)

def ensure_arctic_stack():
    install_official_addon(TARGET_SKIN)
    required = [SKINVARS_ID, "script.texturemaker", TMDB_ID, "resource.images.weathericons.white", "resource.images.studios.coloured", "resource.font.robotocjksc"]
    for addon_id in required:
        install_official_addon(addon_id)
    xbmc.executebuiltin("UpdateLocalAddons")
    xbmc.sleep(1000)
    missing = [addon_id for addon_id in [TARGET_SKIN] + required if not addon_known(addon_id)]
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
    xbmcaddon.Addon(S4ME_ID).setSetting("channel_language", "ita")

def activate_skin():
    if not addon_known(TARGET_SKIN):
        return False
    xbmc.executebuiltin("UpdateLocalAddons")
    xbmc.sleep(800)
    result = rpc("Settings.SetSettingValue", {"setting": "lookandfeel.skin", "value": TARGET_SKIN})
    if "error" in result:
        return False
    check = rpc("Settings.GetSettingValue", {"setting": "lookandfeel.skin"})
    return ((check.get("result") or {}).get("value") or "").strip() == TARGET_SKIN

def extract_payload(payload_zip):
    tmp = tempfile.mkdtemp(prefix="fl-payload-")
    safe_extract(payload_zip, tmp)
    return tmp

def apply_integration_payload(payload_zip):
    tmp = extract_payload(payload_zip)
    try:
        bridge_src = os.path.join(tmp, "addons", BRIDGE_ID)
        if not os.path.isfile(os.path.join(bridge_src, "addon.xml")):
            raise RuntimeError("Payload FL senza bridge")
        copy_tree_contents(bridge_src, addon_path(BRIDGE_ID))
        tmdb_src = os.path.join(tmp, "userdata", "addon_data", TMDB_ID)
        if os.path.isdir(tmdb_src):
            copy_tree_contents(tmdb_src, os.path.join(PROFILE, "addon_data", TMDB_ID))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    xbmc.executebuiltin("UpdateLocalAddons")
    xbmc.sleep(700)
    enable_addon(BRIDGE_ID)

def apply_ui_payload(payload_zip):
    tmp = extract_payload(payload_zip)
    try:
        skin_runtime_src = os.path.join(tmp, "addons", TARGET_SKIN)
        if os.path.isdir(skin_runtime_src):
            copy_tree_contents(skin_runtime_src, addon_path(TARGET_SKIN))
        for addon_id in (TARGET_SKIN, SKINVARS_ID):
            src = os.path.join(tmp, "userdata", "addon_data", addon_id)
            if os.path.isdir(src):
                copy_tree_contents(src, os.path.join(PROFILE, "addon_data", addon_id))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def skin_setting_map():
    path = os.path.join(PROFILE, "addon_data", TARGET_SKIN, "settings.xml")
    if not os.path.isfile(path):
        return {}, path
    root = ET.parse(path).getroot()
    values = {}
    for node in root.findall(".//setting"):
        key = (node.get("id") or "").strip().lower()
        value = node.get("value") if node.get("value") is not None else (node.text or "")
        values[key] = value.strip()
    return values, path

def verify_ui_config():
    values, settings_path = skin_setting_map()
    checks = [
        ("Home", values.get("homeswitcher.home.name") == "Home"),
        ("Film", values.get("homeswitcher.1101.name") == "Film"),
        ("Film path", "info=dir_movie" in values.get("homeswitcher.1101.shortcut.path", "")),
        ("Serie TV", values.get("homeswitcher.1102.name") == "Serie TV"),
        ("Serie TV path", "info=dir_tv" in values.get("homeswitcher.1102.shortcut.path", "")),
    ]
    nodes = os.path.join(PROFILE, "addon_data", SKINVARS_ID, "nodes", TARGET_SKIN)
    for filename in ("skinvariables-shortcut-homewidgets.json", "skinvariables-shortcut-1101widgets.json", "skinvariables-shortcut-1102widgets.json"):
        checks.append((filename, os.path.isfile(os.path.join(nodes, filename))))
    missing = [label for label, ok in checks if not ok]
    return len(missing) == 0, missing, settings_path

def download_current_payload():
    manifest = fetch_manifest()
    remote_version = str(manifest.get("version", "")).strip()
    if version_major(remote_version) < MIN_PAYLOAD_MAJOR:
        raise RuntimeError("Manifest ancora legacy (%s)." % (remote_version or "senza versione"))
    tmpdir = tempfile.mkdtemp(prefix="fl-download-")
    payload_zip = os.path.join(tmpdir, "payload.zip")
    download(manifest_payload_url(manifest), payload_zip)
    return manifest, remote_version, tmpdir, payload_zip

def install_or_update(force=False):
    progress = None
    tmpdir = None
    run_configurator = False
    try:
        manifest = fetch_manifest()
        remote_version = str(manifest.get("version", "")).strip()
        if version_major(remote_version) < MIN_PAYLOAD_MAJOR:
            raise RuntimeError("Manifest ancora legacy (%s)." % (remote_version or "senza versione"))
        installed = current_version()
        if remote_version and installed == remote_version and not force:
            notify("Componenti FL gia' aggiornati: %s" % remote_version)
            return
        progress = xbmcgui.DialogProgress()
        progress.create("FL-Entertainment - Passo 1/2", "Installazione componenti...")
        progress.update(10, "Caricamento repository...")
        get_indexes()
        progress.update(20, "Arctic Fuse 3 + dipendenze...")
        ensure_arctic_stack()
        progress.update(65, "Stream4Me stable...")
        ensure_stream4me(reset_defaults=(version_major(installed) < 2))
        progress.update(76, "Download integrazione FL...")
        tmpdir = tempfile.mkdtemp(prefix="fl-download-")
        payload_zip = os.path.join(tmpdir, "payload.zip")
        download(manifest_payload_url(manifest), payload_zip)
        progress.update(86, "Bridge + TMDb Helper player...")
        apply_integration_payload(payload_zip)
        progress.update(96, "Attivazione Arctic Fuse 3...")
        if not activate_skin():
            raise RuntimeError("Arctic Fuse 3 installata ma Kodi non l'ha attivata")
        if remote_version:
            write_version(remote_version)
        progress.update(100, "Passo 1 completato")
        xbmc.sleep(400)
        progress.close()
        progress = None
        run_configurator = xbmcgui.Dialog().yesno(
            "FL-Entertainment - Passo 1 completato",
            "Componenti installati correttamente.\n\nArctic Fuse 3: OK\nTMDb Helper: OK\nStream4Me + Bridge: OK\n\nVuoi applicare ora la configurazione UI FL-Entertainment (Passo 2/2)?"
        )
    except Exception as exc:
        log("ERRORE INSTALLAZIONE: %s" % exc)
        dialog("FL-Entertainment", "Installazione componenti fallita:\n%s" % exc)
    finally:
        if progress:
            try:
                progress.close()
            except Exception:
                pass
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)
    if run_configurator:
        configure_ui()

def configure_ui():
    progress = None
    tmpdir = None
    try:
        if not addon_known(TARGET_SKIN) or not addon_known(SKINVARS_ID):
            raise RuntimeError("Prima esegui il Passo 1: installazione componenti FL-Entertainment")
        progress = xbmcgui.DialogProgress()
        progress.create("FL-Entertainment - Passo 2/2", "Configurazione interfaccia...")
        progress.update(15, "Download preset UI FL...")
        manifest, remote_version, tmpdir, payload_zip = download_current_payload()
        progress.update(45, "Home / Film / Serie TV...")
        apply_ui_payload(payload_zip)
        progress.update(70, "Verifica configurazione...")
        ok, missing, settings_path = verify_ui_config()
        if not ok:
            raise RuntimeError("Preset UI incompleto: %s" % ", ".join(missing))
        progress.update(85, "Rigenerazione Arctic Fuse 3...")
        xbmc.executebuiltin("UpdateLocalAddons")
        xbmc.sleep(500)
        xbmc.executebuiltin("ReloadSkin()")
        xbmc.sleep(1200)
        xbmc.executebuiltin("ActivateWindow(Home)")
        progress.update(100, "Configurazione applicata")
        xbmc.sleep(400)
        progress.close()
        progress = None
        dialog("FL-Entertainment", "Configurazione UI applicata e verificata.\n\nHome: OK\nFilm: OK\nSerie TV: OK\nWidget SkinVariables: OK\n\nSe la home non si aggiorna immediatamente, riavvia Kodi una volta.")
    except Exception as exc:
        log("ERRORE CONFIGURATORE UI: %s" % exc)
        dialog("FL-Entertainment", "Configurazione UI fallita:\n%s" % exc)
    finally:
        if progress:
            try:
                progress.close()
            except Exception:
                pass
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)

def diagnostics():
    ok_ui, missing_ui, settings_path = verify_ui_config()
    lines = [
        "Arctic Fuse 3: %s" % ("OK" if addon_known(TARGET_SKIN) else "MANCANTE"),
        "TMDb Helper: %s" % ("OK" if addon_known(TMDB_ID) else "MANCANTE"),
        "SkinVariables: %s" % ("OK" if addon_known(SKINVARS_ID) else "MANCANTE"),
        "Stream4Me: %s" % ("OK" if addon_known(S4ME_ID) else "MANCANTE"),
        "Bridge FL: %s" % ("OK" if addon_known(BRIDGE_ID) else "MANCANTE"),
        "Preset UI: %s" % ("OK" if ok_ui else "INCOMPLETO"),
    ]
    if missing_ui:
        lines.append("UI mancante: " + ", ".join(missing_ui))
    dialog("Diagnostica FL-Entertainment", "\n".join(lines))

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
    elif action == "configure_ui":
        configure_ui()
    elif action == "diagnostics":
        diagnostics()
    elif action == "update":
        install_or_update(False)
    elif action == "settings":
        ADDON.openSettings()
    elif action == "test":
        dialog("FL-Entertainment", "Bootstrap %s attivo.\nManifest: %s" % (BOOTSTRAP_VERSION, get_manifest_url()))
    else:
        add_item("1. Installa / ripara componenti FL-Entertainment", "install")
        add_item("2. Applica configurazione UI FL-Entertainment", "configure_ui")
        add_item("3. Diagnostica FL-Entertainment", "diagnostics")
        add_item("Controlla aggiornamenti componenti", "update")
        add_item("Impostazioni", "settings")
        add_item("Test bootstrap", "test")
        xbmcplugin.addDirectoryItem(HANDLE, "", xbmcgui.ListItem(label="Versione payload FL installata: %s" % (current_version() or "nessuna")), isFolder=False)
    xbmcplugin.endOfDirectory(HANDLE)

if __name__ == "__main__":
    main()
