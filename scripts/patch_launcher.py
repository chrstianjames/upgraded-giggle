#!/usr/bin/env python3
"""Replace the Compose/login launcher and the menu's Java-side lock gates.

Run after `apktool d -r` (disassemble dex, keep binary resources). Fail closed if
we cannot find the exact original methods; don't silently ship an unpatched APK.
Native code is intentionally left untouched; its behavior cannot be assured.
"""
import argparse
from pathlib import Path
import re

ACTIVITY = "com/star/android/MainActivity.smali"
SERVICE = "com/star/android/service/FloatingService.smali"
LOGIN_CLIENT = "com/star/android/utils/KeyLoginClient.smali"

# These two strings are repeated in the initial menu and in its status refresh.
# Even if a different code path is hit, do not insult the user for re-signing.
ERROR_TEXT = {
    # apktool may encode the bullet/emoji with smali \\u escapes, so anchor on
    # the surrounding ASCII rather than depending on the Unicode rendering.
    r"CRACK DETECTED[^\"\n]*ALL FEATURES LOCKED": "Menu ready - open the game to use features",
    r"Look Like You Tryna Crack\?[^\"\n]*": "Game: not running - open RoS Legacy",
}

# c() is "locked" (true means locked): it combines certificate + token checks.
# The previous launcher never creates a login token. Returning false keeps the
# menu/status UI and switch callbacks from treating the new APK as cracked.
UNLOCK_MENU = '''.method public final c()Z
    .locals 1
    const/4 v0, 0x0
    return v0
.end method'''

# b() has an additional direct call to nativeVerifyApp, independently of c().
# Replace only that Java-facing signature check. Keep b()'s root, ELF header,
# deployment, and execution checks intact, and leave the original .so alone.
VERIFY_REBUILT_APP = '''.method public static final nativeVerifyApp(Landroid/content/Context;)Z
    .locals 1
    const/4 v0, 0x1
    return v0
.end method'''

ON_CREATE = r'''.method public final onCreate(Landroid/os/Bundle;)V
    .locals 4

    invoke-super {p0, p1}, Landroidx/activity/ComponentActivity;->onCreate(Landroid/os/Bundle;)V

    invoke-static {p0}, Landroid/provider/Settings;->canDrawOverlays(Landroid/content/Context;)Z
    move-result v0
    if-eqz v0, :request_overlay

    invoke-direct {p0}, Lcom/star/android/MainActivity;->showMenuIcon()V
    return-void

    :request_overlay
    new-instance v0, Landroid/content/Intent;
    const-string v1, "android.settings.action.MANAGE_OVERLAY_PERMISSION"
    new-instance v2, Ljava/lang/StringBuilder;
    const-string v3, "package:"
    invoke-direct {v2, v3}, Ljava/lang/StringBuilder;-><init>(Ljava/lang/String;)V
    invoke-virtual {p0}, Landroid/content/Context;->getPackageName()Ljava/lang/String;
    move-result-object v3
    invoke-virtual {v2, v3}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    invoke-virtual {v2}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;
    move-result-object v2
    invoke-static {v2}, Landroid/net/Uri;->parse(Ljava/lang/String;)Landroid/net/Uri;
    move-result-object v2
    invoke-direct {v0, v1, v2}, Landroid/content/Intent;-><init>(Ljava/lang/String;Landroid/net/Uri;)V
    const/16 v1, 0x7b
    invoke-virtual {p0, v0, v1}, Landroidx/activity/ComponentActivity;->startActivityForResult(Landroid/content/Intent;I)V
    return-void
.end method'''

ON_RESULT = r'''.method public final onActivityResult(IILandroid/content/Intent;)V
    .locals 2

    invoke-super {p0, p1, p2, p3}, Landroidx/activity/ComponentActivity;->onActivityResult(IILandroid/content/Intent;)V
    const/16 v0, 0x7b
    if-ne p1, v0, :done

    invoke-static {p0}, Landroid/provider/Settings;->canDrawOverlays(Landroid/content/Context;)Z
    move-result v0
    if-eqz v0, :denied
    invoke-direct {p0}, Lcom/star/android/MainActivity;->showMenuIcon()V
    return-void

    :denied
    const-string v0, "Allow display over other apps to show the menu icon"
    const/4 v1, 0x0
    invoke-static {p0, v0, v1}, Landroid/widget/Toast;->makeText(Landroid/content/Context;Ljava/lang/CharSequence;I)Landroid/widget/Toast;
    move-result-object v0
    invoke-virtual {v0}, Landroid/widget/Toast;->show()V
    invoke-virtual {p0}, Landroid/app/Activity;->finish()V

    :done
    return-void
.end method'''

SHOW_ICON = r'''.method private showMenuIcon()V
    .locals 3

    new-instance v0, Landroid/content/Intent;
    const-class v1, Lcom/star/android/service/FloatingService;
    invoke-direct {v0, p0, v1}, Landroid/content/Intent;-><init>(Landroid/content/Context;Ljava/lang/Class;)V
    sget v1, Landroid/os/Build$VERSION;->SDK_INT:I
    const/16 v2, 0x1a
    if-lt v1, v2, :legacy
    invoke-virtual {p0, v0}, Landroid/content/Context;->startForegroundService(Landroid/content/Intent;)Landroid/content/ComponentName;
    goto :finished

    :legacy
    invoke-virtual {p0, v0}, Landroid/content/Context;->startService(Landroid/content/Intent;)Landroid/content/ComponentName;

    :finished
    invoke-virtual {p0}, Landroid/app/Activity;->finish()V
    return-void
.end method'''


def replace_method(source: str, name: str, replacement: str) -> str:
    pattern = re.compile(
        rf"(?m)^\.method public final {re.escape(name)}\([^\n]*\)V\n.*?^\.end method$",
        re.DOTALL,
    )
    result, count = pattern.subn(lambda _: replacement, source)
    if count != 1:
        raise ValueError(f"Expected exactly one {name} in {ACTIVITY}, found {count}")
    return result


def unique_smali(root: Path, name: str) -> Path:
    matches = list(root.glob(f"smali*/{name}"))
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one {name}, found {len(matches)}")
    return matches[0]


def replace_string_instruction(text: str, old: str, new: str, count: int, path: Path) -> str:
    # Match only the body of a const-string instruction, never arbitrary code.
    pattern = re.compile(r'(?m)^(\s*const-string(?:/jumbo)?\s+[vp]\d+,\s*)"' + old + r'"$')
    result, found = pattern.subn(lambda match: match.group(1) + '"' + new + '"', text)
    if found != count:
        raise ValueError(f"Expected {count} occurrences of {old!r} in {path}, found {found}")
    return result


def patch(root: Path) -> None:
    path = unique_smali(root, ACTIVITY)
    service = unique_smali(root, SERVICE)
    login = unique_smali(root, LOGIN_CLIENT)
    status = unique_smali(root, "b8.smali")
    callbacks = unique_smali(root, "xy.smali")
    original = path.read_text(encoding="utf-8")
    service_text = service.read_text(encoding="utf-8")
    login_text = login.read_text(encoding="utf-8")
    status_text = status.read_text(encoding="utf-8")
    callbacks_text = callbacks.read_text(encoding="utf-8")
    if "Lcom/star/android/service/FloatingService;" not in service_text:
        raise ValueError("FloatingService class does not match expected APK")
    if ".method private showMenuIcon()V" in original:
        raise ValueError("Already patched")
    if "Ljg0;->LoginScreen" not in original or "Ljg0;->MainScreen" not in original:
        raise ValueError("Unexpected original launcher: login/main-screen signature missing")
    result = replace_method(original, "onCreate", ON_CREATE)
    result = replace_method(result, "onActivityResult", ON_RESULT)
    result += "\n" + SHOW_ICON + "\n"

    # Anchor the edits to the actual gate methods, rather than just painting over
    # the two error labels. The JVM-side native check otherwise blocks injection.
    locked = re.compile(r"(?ms)^\.method public final c\(\)Z\n.*?^\.end method$")
    if "nativeVerifyApp" not in service_text or "AUTH_TOKEN:" not in service_text:
        raise ValueError("Expected token/signature gate not found")
    service_text, count = locked.subn(lambda _: UNLOCK_MENU, service_text)
    if count != 1:
        raise ValueError(f"Expected one locked() method in {service}, found {count}")
    native = re.compile(
        r"(?ms)^\.method public static final native nativeVerifyApp\(Landroid/content/Context;\)Z\n.*?^\.end method$"
    )
    login_text, count = native.subn(lambda _: VERIFY_REBUILT_APP, login_text)
    if count != 1:
        raise ValueError(f"Expected one native signature gate in {login}, found {count}")
    for old, new in ERROR_TEXT.items():
        service_text = replace_string_instruction(service_text, old, new, 1, service)
        status_text = replace_string_instruction(status_text, old, new, 1, status)
    old = r"Look Like You Tryna Crack\?[^\"\n]*"
    callbacks_text = replace_string_instruction(callbacks_text, old, "Menu unavailable", 1, callbacks)

    # Write only after every check succeeds; do not leave partial patches.
    for dest, contents in [(path, result), (service, service_text),
                           (login, login_text), (status, status_text),
                           (callbacks, callbacks_text)]:
        dest.write_text(contents, encoding="utf-8")
    print("Patched launcher and Java-side menu/integrity gates; native library unchanged")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("decoded", type=Path, help="directory made by apktool d -r")
    patch(parser.parse_args().decoded)
