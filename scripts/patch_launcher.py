#!/usr/bin/env python3
"""Replace the original Compose/login launcher with a minimal overlay launcher.

Run after `apktool d -r` (disassemble dex, keep binary resources). Fail closed if
we cannot find the exact original methods; don't silently ship an unpatched APK.
"""
import argparse
from pathlib import Path
import re

ACTIVITY = "com/star/android/MainActivity.smali"
SERVICE = "com/star/android/service/FloatingService.smali"

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


def patch(root: Path) -> None:
    matches = list(root.glob(f"smali*/{ACTIVITY}"))
    service = list(root.glob(f"smali*/{SERVICE}"))
    if len(matches) != 1 or len(service) != 1:
        raise ValueError(f"Expected one launcher and service; found {len(matches)} and {len(service)}")
    path = matches[0]
    original = path.read_text(encoding="utf-8")
    if "Lcom/star/android/service/FloatingService;" not in service[0].read_text(encoding="utf-8"):
        raise ValueError("FloatingService class does not match expected APK")
    if ".method private showMenuIcon()V" in original:
        raise ValueError("Already patched")
    if "Ljg0;->LoginScreen" not in original or "Ljg0;->MainScreen" not in original:
        raise ValueError("Unexpected original launcher: login/main-screen signature missing")
    result = replace_method(original, "onCreate", ON_CREATE)
    result = replace_method(result, "onActivityResult", ON_RESULT)
    result += "\n" + SHOW_ICON + "\n"
    path.write_text(result, encoding="utf-8")
    print(f"Patched {path}: direct menu launch after overlay permission; no login UI")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("decoded", type=Path, help="directory made by apktool d -r")
    patch(parser.parse_args().decoded)
