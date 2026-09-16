# -*- coding: utf-8 -*-
import os
import shutil
import xml.etree.ElementTree as ET

import xbmc
import xbmcaddon

import default as core

# 2.1.1: UI configurator fix.
# Kodi keeps addon/skin settings in memory. Copying settings.xml while Kodi is
# running can therefore look correct on disk but have zero visible effect.
# This wrapper applies the master preset through Kodi's own settings API.
core.BOOTSTRAP_VERSION = "2.1.1"
core.USER_AGENT = "Kodi FL-Entertainment Bootstrap/%s" % core.BOOTSTRAP_VERSION


def _setting_value(node):
    if node.get("value") is not None:
        return node.get("value") or ""
    return node.text or ""


def _set_skin_setting(addon, setting_id, setting_type, value):
    setting_type = (setting_type or "string").lower()
    text = str(value or "")

    try:
        if setting_type == "bool" and hasattr(addon, "setSettingBool"):
            addon.setSettingBool(setting_id, text.strip().lower() == "true")
            return
        if setting_type in ("integer", "int") and hasattr(addon, "setSettingInt"):
            addon.setSettingInt(setting_id, int(text or "0"))
            return
        if setting_type in ("number", "float") and hasattr(addon, "setSettingNumber"):
            addon.setSettingNumber(setting_id, float(text or "0"))
            return
    except Exception:
        # Fallback universally supported by Kodi Python API.
        pass

    addon.setSetting(setting_id, text)


def apply_ui_payload(payload_zip):
    tmp = core.extract_payload(payload_zip)
    applied = 0
    try:
        # Generated Arctic runtime includes from the Windows master.
        skin_runtime_src = os.path.join(tmp, "addons", core.TARGET_SKIN)
        if os.path.isdir(skin_runtime_src):
            core.copy_tree_contents(skin_runtime_src, core.addon_path(core.TARGET_SKIN))

        # SkinVariables nodes/widgets from the Windows master.
        skinvars_src = os.path.join(tmp, "userdata", "addon_data", core.SKINVARS_ID)
        if os.path.isdir(skinvars_src):
            core.copy_tree_contents(
                skinvars_src,
                os.path.join(core.PROFILE, "addon_data", core.SKINVARS_ID),
            )

        # Arctic addon_data: copy any auxiliary files, but DO NOT overwrite
        # settings.xml directly. Apply its values through xbmcaddon instead.
        skin_data_src = os.path.join(tmp, "userdata", "addon_data", core.TARGET_SKIN)
        settings_src = os.path.join(skin_data_src, "settings.xml")
        if not os.path.isfile(settings_src):
            raise RuntimeError("Preset UI senza skin.arctic.fuse.3/settings.xml")

        skin_data_dst = os.path.join(core.PROFILE, "addon_data", core.TARGET_SKIN)
        core.ensure_dir(skin_data_dst)
        for name in os.listdir(skin_data_src):
            if name.lower() == "settings.xml":
                continue
            src = os.path.join(skin_data_src, name)
            dst = os.path.join(skin_data_dst, name)
            if os.path.isdir(src):
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)

        skin = xbmcaddon.Addon(core.TARGET_SKIN)
        root = ET.parse(settings_src).getroot()
        for node in root.findall(".//setting"):
            setting_id = (node.get("id") or "").strip()
            if not setting_id:
                continue
            _set_skin_setting(skin, setting_id, node.get("type"), _setting_value(node))
            applied += 1

        # Explicitly guarantee the two custom top-level hubs are enabled.
        skin.setSetting("homeswitcher.1101.toggle", "true")
        skin.setSetting("homeswitcher.1102.toggle", "true")

        core.log("UI preset applicato via Kodi API: %d setting" % applied)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    return applied


def verify_ui_config():
    settings_path = os.path.join(
        core.PROFILE, "addon_data", core.TARGET_SKIN, "settings.xml"
    )
    try:
        skin = xbmcaddon.Addon(core.TARGET_SKIN)
        live = {
            "home": skin.getSetting("HomeSwitcher.Home.Name"),
            "film": skin.getSetting("HomeSwitcher.1101.Name"),
            "film_path": skin.getSetting("HomeSwitcher.1101.Shortcut.Path"),
            "film_toggle": skin.getSetting("homeswitcher.1101.toggle"),
            "tv": skin.getSetting("HomeSwitcher.1102.Name"),
            "tv_path": skin.getSetting("HomeSwitcher.1102.Shortcut.Path"),
            "tv_toggle": skin.getSetting("homeswitcher.1102.toggle"),
        }
    except Exception as exc:
        return False, ["lettura setting live Arctic: %s" % exc], settings_path

    checks = [
        ("Home", live["home"] == "Home"),
        ("Film", live["film"] == "Film"),
        ("Film path", "info=dir_movie" in live["film_path"]),
        ("Film enabled", live["film_toggle"].lower() == "true"),
        ("Serie TV", live["tv"] == "Serie TV"),
        ("Serie TV path", "info=dir_tv" in live["tv_path"]),
        ("Serie TV enabled", live["tv_toggle"].lower() == "true"),
    ]

    nodes = os.path.join(
        core.PROFILE,
        "addon_data",
        core.SKINVARS_ID,
        "nodes",
        core.TARGET_SKIN,
    )
    for filename in (
        "skinvariables-shortcut-homewidgets.json",
        "skinvariables-shortcut-1101widgets.json",
        "skinvariables-shortcut-1102widgets.json",
    ):
        checks.append((filename, os.path.isfile(os.path.join(nodes, filename))))

    missing = [label for label, ok in checks if not ok]
    core.log("UI live: %s" % live)
    return len(missing) == 0, missing, settings_path


def configure_ui():
    progress = None
    tmpdir = None
    try:
        if not core.addon_known(core.TARGET_SKIN) or not core.addon_known(core.SKINVARS_ID):
            raise RuntimeError("Prima esegui il Passo 1: installazione componenti FL-Entertainment")

        progress = core.xbmcgui.DialogProgress()
        progress.create("FL-Entertainment - Passo 2/2", "Configurazione interfaccia...")
        progress.update(15, "Download preset UI FL...")
        manifest, remote_version, tmpdir, payload_zip = core.download_current_payload()

        progress.update(40, "Applicazione setting Arctic tramite Kodi...")
        applied = apply_ui_payload(payload_zip)
        if applied <= 0:
            raise RuntimeError("Nessuna impostazione Arctic applicata")

        progress.update(65, "Verifica live Home / Film / Serie TV...")
        ok, missing, settings_path = verify_ui_config()
        if not ok:
            raise RuntimeError("Preset UI live incompleto: %s" % ", ".join(missing))

        progress.update(80, "Ricaricamento Arctic Fuse 3...")
        xbmc.executebuiltin("UpdateLocalAddons")
        xbmc.sleep(300)
        xbmc.executebuiltin("ReloadSkin()")
        xbmc.sleep(1500)
        xbmc.executebuiltin("ActivateWindow(Home)")
        xbmc.sleep(600)

        # Verify again AFTER ReloadSkin: this catches Kodi reverting settings.
        ok, missing, settings_path = verify_ui_config()
        if not ok:
            raise RuntimeError("Kodi ha ripristinato il preset dopo ReloadSkin: %s" % ", ".join(missing))

        progress.update(100, "Configurazione UI applicata")
        xbmc.sleep(300)
        progress.close()
        progress = None
        core.dialog(
            "FL-Entertainment",
            "Preset UI applicato tramite Kodi e verificato dopo ReloadSkin.\n\n"
            "Home: OK\nFilm: OK\nSerie TV: OK\nWidget: OK",
        )
    except Exception as exc:
        core.log("ERRORE CONFIGURATORE UI 2.1.1: %s" % exc)
        core.dialog("FL-Entertainment", "Configurazione UI fallita:\n%s" % exc)
    finally:
        if progress:
            try:
                progress.close()
            except Exception:
                pass
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)


# Replace only the broken UI layer; leave the working installer/bridge untouched.
core.apply_ui_payload = apply_ui_payload
core.verify_ui_config = verify_ui_config
core.configure_ui = configure_ui

if __name__ == "__main__":
    core.main()
