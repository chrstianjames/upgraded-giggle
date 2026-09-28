# PRIMEBIT APK-only launcher repair

The repository contains **only a compiled APK** (package `com.star.android`), not the Android/Kotlin/C++ source. The original APK has a Compose login, a separate `FloatingService` for the overlay, and a native `libPrimeBit.so` injector. The rebuilt APK is signed with a different certificate.

## What this build changes

- On launch, show the original app's **MainScreen with its Open Menu button**. The floating icon does **not** start automatically. Tap Open Menu to request Android's overlay permission if necessary, then start the service. The supplied APK references `MainActivity.i()` for that button but does not define it; the build supplies that method and fixes the overlay permission return path.
- The login screen is not entered. The menu's Java-side certificate/token gate and its hostile warnings are patched, but the arm64 native library and injected `assets/Injector` are unchanged. The root, ELF-header, deployment, and socket checks are not replaced by fake “injected” results.

## Why “Primebit: License Not Activated” is still possible

Tracing the original dex shows that `KeyLoginClient.f()` reads `server_auth_token` from the app's `primebit_login` preferences. After injection, the app tries to send that `AUTH_TOKEN:` value to the game socket. Without one, it reads `license_key` from the same preferences and calls `KeyLoginClient.nativeGenerateAuth()` **only if the key is nonempty**. With login removed and a fresh install, both values are empty, so the native game module receives no valid activation. The reported “License Not Activated” text is not in the Java UI and was not removed by the earlier Java-side changes. **Showing the menu is not equivalent to activating the native module.** Root alone does not supply an auth token.

A genuine login-free native injection fix needs the original C++ library source plus the intended license-server protocol (or an authorized guest/offline-license implementation). APK repacking cannot issue a server-approved license. Do not put signing keys, license secrets or private device identifiers in this repository or in chat. Please provide source through an appropriate private project if you want that part rebuilt; the APK alone is insufficient to verify a working injector. No rooted test device was available here, so this build is statically verified, not device-tested.

## Build

[Actions → Build menu-button APK](../../actions/workflows/build-apk.yml) runs on source changes to this branch. The latest signed output is [`artifacts/primebit-menu-button.apk`](artifacts/primebit-menu-button.apk), and the workflow run also has a download artifact. The workflow verifies apktool 3.0.3, decodes the supplied APK with binary resources preserved, patches smali, rebuilds, zipaligns, signs, verifies, and checks the native library remains byte-for-byte intact.

For local builds use Java 17+, Android SDK build-tools 36.0.0, and apktool 3.0.3:

```bash
java -jar apktool_3.0.3.jar d -f -r 5_6181698127930598959.apk -o decoded
python3 scripts/patch_launcher.py decoded
java -jar apktool_3.0.3.jar b decoded -o unsigned.apk
zipalign -f -p 4 unsigned.apk aligned.apk
# Sign with apksigner and YOUR keystore; apksigner verify --verbose signed.apk
```

### Troubleshooting on a rooted phone

Keep the target game `net.roslegacy.prod` running and verify the app has root access. If injection still fails, capture a log with Android platform tools after pressing **Force Inject**:

```bash
adb shell su -c 'id; pidof net.roslegacy.prod'
adb logcat -c
# On the phone: open the app, tap Open Menu, and tap Force Inject.
adb logcat -d -v time | grep -Ei 'Primebit|StarShell|Anti-Patch|License|Injector|denied|socket' > injection-log.txt
```

**Redact tokens, account details, device IDs, and keys before sharing logs.** Do not run `setenforce 0` yourself; the supplied injector already contains privileged device-level commands, so use it only if you understand those effects. The main native library is arm64-only.

### Signing / installation

The workflow's fallback signing key changes on each build. **Back up app data and uninstall the previous APK before installing a new fallback-signed build.** To keep one signing identity configure GitHub Actions secrets `APK_KEYSTORE_BASE64` (base64 Java keystore), `APK_KEYSTORE_PASSWORD`, `APK_KEY_ALIAS`, `APK_KEY_PASSWORD`. Never commit the keystore. Even with the original signing key, the native module still needs its intended license activation path.
