# -*- coding: utf-8 -*-
import os
import shutil
import tempfile
import urllib.parse
import xml.etree.ElementTree as ET

import xbmc
import xbmcgui

import default as core
import default_212 as ui

# 2.1.3: first bootstrap that can update BOTH itself and the FL payload
# directly from the GitHub manifest. After this version is installed once,
# normal releases no longer require ADB/ZIP manual installation.
core.BOOTSTRAP_VERSION = "2.1.3"
core.USER_AGENT = "Kodi FL-Entertainment Bootstrap/%s" % core.BOOTSTRAP_VERSION


def _version_tuple(value):
    parts = []
    for item in str(value or "0").strip().split("."):
        try:
            parts.append(int(item))
        except Exception:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:4])


def _is_newer(remote, local):
    return _version_tuple(remote) > _version_tuple(local)


def _manifest_bootstrap_version(manifest):
    return str(
        manifest.get("bootstrap_version")
        or manifest.get("bootstrap_min_version")
        or manifest.get("version")
        or ""
    ).strip()


def _manifest_bootstrap_url(manifest):
    value = (manifest.get("bootstrap_url") or "").strip()
    if not value:
        raise RuntimeError("bootstrap_url mancante nel manifest")
    return urllib.parse.urljoin(core.get_manifest_url(), value)


def _install_bootstrap_zip(zip_path, expected_version):
    tmp = tempfile.mkdtemp(prefix="fl-bootstrap-update-")
    try:
        core.safe_extract(zip_path, tmp)
        addon_id = core.ADDON.getAddonInfo("id")
        source = os.path.join(tmp, addon_id)
        addon_xml = os.path.join(source, "addon.xml")
        if not os.path.isfile(addon_xml):
            raise RuntimeError("Bootstrap ZIP non valido: addon.xml mancante")

        node = ET.parse(addon_xml).getroot()
        if node.get("id") != addon_id:
            raise RuntimeError("Bootstrap ZIP con addon id errato")
        zip_version = str(node.get("version") or "").strip()
        if expected_version and zip_version != expected_version:
            raise RuntimeError(
                "Versione bootstrap ZIP inattesa: %s (attesa %s)"
                % (zip_version or "?", expected_version)
            )

        # Merge in place. The currently running Python code is already loaded,
        # so the new entrypoint becomes active on the next Kodi restart/reload.
        core.copy_tree_contents(source, core.addon_path(addon_id))
        xbmc.executebuiltin("UpdateLocalAddons")
        xbmc.sleep(600)
        core.log("Bootstrap aggiornato su disco a %s" % zip_version)
        return zip_version
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _apply_payload_from_manifest(manifest, remote_version, progress=None):
    tmpdir = tempfile.mkdtemp(prefix="fl-payload-update-")
    try:
        payload_zip = os.path.join(tmpdir, "payload.zip")
        payload_url = core.manifest_payload_url(manifest)
        core.download(payload_url, payload_zip)

        if progress:
            progress.update(55, "Bridge + integrazione FL...")
        core.apply_integration_payload(payload_zip)

        if progress:
            progress.update(70, "Preset UI FL...")
        if not core.activate_skin():
            raise RuntimeError("Impossibile attivare Arctic Fuse 3")
        xbmc.sleep(500)
        ui.apply_ui_payload(payload_zip)

        ok, missing, _ = ui.verify_ui_config()
        if not ok:
            raise RuntimeError("Preset UI incompleto: %s" % ", ".join(missing))

        xbmc.executebuiltin("UpdateLocalAddons")
        xbmc.sleep(250)
        xbmc.executebuiltin("ReloadSkin()")
        xbmc.sleep(1400)

        ok, missing, _ = ui.verify_ui_config()
        if not ok:
            raise RuntimeError("Preset UI perso dopo ReloadSkin: %s" % ", ".join(missing))

        # IMPORTANT: payload marker is written only after integration + UI
        # have both been applied and verified successfully.
        core.write_version(remote_version)
        core.log("Payload aggiornato e marker scritto: %s" % remote_version)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def update_everything():
    progress = None
    bootstrap_tmp = None
    try:
        manifest = core.fetch_manifest()
        remote_payload = str(manifest.get("version") or "").strip()
        remote_bootstrap = _manifest_bootstrap_version(manifest)
        local_payload = core.current_version()
        local_bootstrap = core.ADDON.getAddonInfo("version") or core.BOOTSTRAP_VERSION

        need_bootstrap = bool(remote_bootstrap) and _is_newer(remote_bootstrap, local_bootstrap)
        need_payload = bool(remote_payload) and (
            not local_payload or _is_newer(remote_payload, local_payload)
        )

        if not need_bootstrap and not need_payload:
            core.dialog(
                "FL-Entertainment",
                "Tutto aggiornato.\n\nBootstrap: %s\nPayload: %s"
                % (local_bootstrap, local_payload or "nessuno"),
            )
            return

        progress = xbmcgui.DialogProgress()
        progress.create("FL-Entertainment", "Aggiornamento da GitHub...")

        if need_bootstrap:
            progress.update(10, "Download bootstrap %s..." % remote_bootstrap)
            bootstrap_tmp = tempfile.mkdtemp(prefix="fl-bootstrap-download-")
            bootstrap_zip = os.path.join(bootstrap_tmp, "bootstrap.zip")
            core.download(_manifest_bootstrap_url(manifest), bootstrap_zip)
            progress.update(30, "Aggiornamento bootstrap...")
            _install_bootstrap_zip(bootstrap_zip, remote_bootstrap)

        if need_payload:
            progress.update(40, "Download payload %s..." % remote_payload)
            _apply_payload_from_manifest(manifest, remote_payload, progress)

        progress.update(100, "Aggiornamento completato")
        xbmc.sleep(350)
        progress.close()
        progress = None

        final_bootstrap = remote_bootstrap if need_bootstrap else local_bootstrap
        final_payload = remote_payload if need_payload else (local_payload or "nessuno")
        if need_bootstrap:
            if xbmcgui.Dialog().yesno(
                "FL-Entertainment",
                "Aggiornamento completato.\n\nBootstrap: %s\nPayload: %s\n\nRiavviare Kodi ora?"
                % (final_bootstrap, final_payload),
            ):
                xbmc.executebuiltin("RestartApp")
        else:
            core.dialog(
                "FL-Entertainment",
                "Aggiornamento completato.\n\nBootstrap: %s\nPayload: %s"
                % (final_bootstrap, final_payload),
            )
    except Exception as exc:
        core.log("ERRORE AUTO-UPDATE 2.1.3: %s" % exc)
        core.dialog("FL-Entertainment", "Aggiornamento fallito:\n%s" % exc)
    finally:
        if progress:
            try:
                progress.close()
            except Exception:
                pass
        if bootstrap_tmp:
            shutil.rmtree(bootstrap_tmp, ignore_errors=True)


def configure_ui():
    # Same proven 2.1.2 UI flow, but fix the stale payload marker on success.
    progress = None
    tmpdir = None
    try:
        if not core.addon_known(core.TARGET_SKIN) or not core.addon_known(core.SKINVARS_ID):
            raise RuntimeError("Prima esegui il Passo 1: installazione componenti FL-Entertainment")
        if not core.activate_skin():
            raise RuntimeError("Impossibile attivare Arctic Fuse 3 prima della configurazione")
        xbmc.sleep(600)

        progress = xbmcgui.DialogProgress()
        progress.create("FL-Entertainment - Passo 2/2", "Configurazione interfaccia...")
        progress.update(15, "Download preset UI FL...")
        manifest, remote_version, tmpdir, payload_zip = core.download_current_payload()
        progress.update(40, "Applicazione Home / Film / Serie TV...")
        ui.apply_ui_payload(payload_zip)
        progress.update(65, "Verifica Skin.String live...")
        ok, missing, _ = ui.verify_ui_config()
        if not ok:
            raise RuntimeError("Preset UI live incompleto: %s" % ", ".join(missing))

        progress.update(80, "Ricaricamento Arctic Fuse 3...")
        xbmc.executebuiltin("UpdateLocalAddons")
        xbmc.sleep(250)
        xbmc.executebuiltin("ReloadSkin()")
        xbmc.sleep(1500)
        xbmc.executebuiltin("ActivateWindow(Home)")
        xbmc.sleep(500)
        ok, missing, _ = ui.verify_ui_config()
        if not ok:
            raise RuntimeError("Kodi ha perso il preset dopo ReloadSkin: %s" % ", ".join(missing))

        core.write_version(remote_version)
        progress.update(100, "Configurazione UI applicata")
        xbmc.sleep(250)
        progress.close()
        progress = None
        core.dialog(
            "FL-Entertainment",
            "Preset UI applicato e verificato.\n\nHome: OK\nFilm: OK\nSerie TV: OK\nWidget: OK\nPayload: %s"
            % remote_version,
        )
    except Exception as exc:
        core.log("ERRORE CONFIGURATORE UI 2.1.3: %s" % exc)
        core.dialog("FL-Entertainment", "Configurazione UI fallita:\n%s" % exc)
    finally:
        if progress:
            try:
                progress.close()
            except Exception:
                pass
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)


# Patch the core menu actions while preserving the proven installer/bridge code.
core.configure_ui = configure_ui

_original_install_or_update = core.install_or_update


def install_or_update(force=False):
    if force:
        return _original_install_or_update(True)
    return update_everything()


core.install_or_update = install_or_update

if __name__ == "__main__":
    core.main()
