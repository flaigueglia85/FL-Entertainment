# -*- coding: utf-8 -*-
import os
import shutil
import xml.etree.ElementTree as ET

import xbmc

import default as core

# 2.1.2: Arctic Fuse 3 HomeSwitcher settings are Skin.String values.
# Using xbmcaddon.Addon(...).setSetting() writes addon settings but does NOT
# populate Skin.String(...), which is what Arctic Fuse 3 actually reads.
# Apply the preset with Kodi builtins: Skin.SetString / Skin.Reset.
core.BOOTSTRAP_VERSION = "2.1.2"
core.USER_AGENT = "Kodi FL-Entertainment Bootstrap/%s" % core.BOOTSTRAP_VERSION


def _setting_value(node):
    if node.get("value") is not None:
        return node.get("value") or ""
    return node.text or ""


def _builtin_quote(value):
    # Kodi builtin parser accepts quoted parameters. Escape embedded quotes.
    return '"' + str(value or "").replace('\\', '\\\\').replace('"', '\\"') + '"'


def _skin_set(setting_id, value):
    setting_id = str(setting_id or "").strip()
    if not setting_id:
        return
    text = str(value or "")
    if text == "":
        xbmc.executebuiltin("Skin.Reset(%s)" % _builtin_quote(setting_id))
    else:
        xbmc.executebuiltin(
            "Skin.SetString(%s,%s)" % (_builtin_quote(setting_id), _builtin_quote(text))
        )


def apply_ui_payload(payload_zip):
    tmp = core.extract_payload(payload_zip)
    applied = 0
    try:
        # Generated Arctic runtime includes from Windows master.
        skin_runtime_src = os.path.join(tmp, "addons", core.TARGET_SKIN)
        if os.path.isdir(skin_runtime_src):
            core.copy_tree_contents(skin_runtime_src, core.addon_path(core.TARGET_SKIN))

        # SkinVariables nodes/widgets from Windows master.
        skinvars_src = os.path.join(tmp, "userdata", "addon_data", core.SKINVARS_ID)
        if os.path.isdir(skinvars_src):
            core.copy_tree_contents(
                skinvars_src,
                os.path.join(core.PROFILE, "addon_data", core.SKINVARS_ID),
            )

        skin_data_src = os.path.join(tmp, "userdata", "addon_data", core.TARGET_SKIN)
        settings_src = os.path.join(skin_data_src, "settings.xml")
        if not os.path.isfile(settings_src):
            raise RuntimeError("Preset UI senza skin.arctic.fuse.3/settings.xml")

        # Copy auxiliary files only. settings.xml is used as SOURCE OF TRUTH,
        # but live values are applied through Skin.SetString.
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

        root = ET.parse(settings_src).getroot()
        for node in root.findall(".//setting"):
            setting_id = (node.get("id") or "").strip()
            if not setting_id:
                continue
            _skin_set(setting_id, _setting_value(node))
            applied += 1

        # These are required top-level FL hubs.
        _skin_set("HomeSwitcher.Home.Name", "Home")
        _skin_set("HomeSwitcher.1101.Name", "Film")
        _skin_set("HomeSwitcher.1101.Shortcut.Path", "plugin://plugin.video.themoviedb.helper/?info=dir_movie")
        _skin_set("homeswitcher.1101.toggle", "true")
        _skin_set("HomeSwitcher.1102.Name", "Serie TV")
        _skin_set("HomeSwitcher.1102.Shortcut.Path", "plugin://plugin.video.themoviedb.helper/?info=dir_tv")
        _skin_set("homeswitcher.1102.toggle", "true")

        xbmc.sleep(350)
        core.log("UI preset applicato via Skin.SetString: %d setting" % applied)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    return applied


def _skin_value(setting_id):
    return xbmc.getInfoLabel("Skin.String(%s)" % setting_id) or ""


def verify_ui_config():
    settings_path = os.path.join(
        core.PROFILE, "addon_data", core.TARGET_SKIN, "settings.xml"
    )

    live = {
        "home": _skin_value("HomeSwitcher.Home.Name"),
        "film": _skin_value("HomeSwitcher.1101.Name"),
        "film_path": _skin_value("HomeSwitcher.1101.Shortcut.Path"),
        "film_toggle": _skin_value("homeswitcher.1101.toggle"),
        "tv": _skin_value("HomeSwitcher.1102.Name"),
        "tv_path": _skin_value("HomeSwitcher.1102.Shortcut.Path"),
        "tv_toggle": _skin_value("homeswitcher.1102.toggle"),
    }

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
    core.log("UI Skin.String live: %s" % live)
    return len(missing) == 0, missing, settings_path


def configure_ui():
    progress = None
    tmpdir = None
    try:
        if not core.addon_known(core.TARGET_SKIN) or not core.addon_known(core.SKINVARS_ID):
            raise RuntimeError("Prima esegui il Passo 1: installazione componenti FL-Entertainment")

        if not core.activate_skin():
            raise RuntimeError("Impossibile attivare Arctic Fuse 3 prima della configurazione")
        xbmc.sleep(700)

        progress = core.xbmcgui.DialogProgress()
        progress.create("FL-Entertainment - Passo 2/2", "Configurazione interfaccia...")
        progress.update(15, "Download preset UI FL...")
        manifest, remote_version, tmpdir, payload_zip = core.download_current_payload()

        progress.update(40, "Applicazione Home / Film / Serie TV...")
        applied = apply_ui_payload(payload_zip)
        if applied <= 0:
            raise RuntimeError("Nessuna impostazione Arctic applicata")

        progress.update(65, "Verifica Skin.String live...")
        ok, missing, settings_path = verify_ui_config()
        if not ok:
            raise RuntimeError("Preset UI live incompleto: %s" % ", ".join(missing))

        progress.update(80, "Ricaricamento Arctic Fuse 3...")
        xbmc.executebuiltin("UpdateLocalAddons")
        xbmc.sleep(300)
        xbmc.executebuiltin("ReloadSkin()")
        xbmc.sleep(1600)
        xbmc.executebuiltin("ActivateWindow(Home)")
        xbmc.sleep(700)

        ok, missing, settings_path = verify_ui_config()
        if not ok:
            raise RuntimeError("Kodi ha perso il preset dopo ReloadSkin: %s" % ", ".join(missing))

        progress.update(100, "Configurazione UI applicata")
        xbmc.sleep(300)
        progress.close()
        progress = None
        core.dialog(
            "FL-Entertainment",
            "Preset UI applicato e verificato.\n\nHome: OK\nFilm: OK\nSerie TV: OK\nWidget: OK",
        )
    except Exception as exc:
        core.log("ERRORE CONFIGURATORE UI 2.1.2: %s" % exc)
        core.dialog("FL-Entertainment", "Configurazione UI fallita:\n%s" % exc)
    finally:
        if progress:
            try:
                progress.close()
            except Exception:
                pass
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)


core.apply_ui_payload = apply_ui_payload
core.verify_ui_config = verify_ui_config
core.configure_ui = configure_ui

if __name__ == "__main__":
    core.main()
