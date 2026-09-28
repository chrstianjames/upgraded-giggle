# PRIMEBIT menu launcher (APK-only reconstruction)

This repository was provided **only as a compiled APK**, not an Android Studio/Gradle source project. The APK package is `com.star.android` (min SDK 24, target SDK 36); its launcher shows a Compose login, while `FloatingService` creates the floating icon/menu. The original APK includes a native `libPrimeBit.so` and a repack/signature check.

## Changes

- Replaces the launcher activity's `onCreate` and overlay-permission result handler at APK build time. Opening the app requests **Display over other apps** permission if needed, then starts the original floating-menu foreground service and closes the launcher. **No login UI or key entry is opened.** Tap the floating icon to open the original panel.
- The game injection/native library is *not* altered and its signature/token checks are *not* disabled. A re-signed APK may show its original anti-tamper warning or refuse to inject. **A successful APK build does not prove the native features work.** To properly remove licensing and retain native functionality, obtain the original Android/Kotlin/C++ source and signing key and change/rebuild them together.
- No new permissions are added. Android overlay permission must be approved by the user. Some devices restrict foreground services or overlays; this has not been tested on a physical device.

## Build

[Actions → Build login-free APK](../../actions/workflows/build-apk.yml) runs automatically on pushes to this workspace branch, or can be run manually when available. Download the `primebit-menu-no-login` artifact (APK) from the workflow run. The workflow pins and verifies apktool 3.0.3, decodes the supplied APK with binary resources preserved, applies `scripts/patch_launcher.py`, rebuilds, aligns, signs, and verifies the APK. It checks the native library was not modified.

You can also build locally with Java 17+, Android SDK build-tools 36.0.0, and apktool 3.0.3:

```bash
java -jar apktool_3.0.3.jar d -f -r 5_6181698127930598959.apk -o decoded
python3 scripts/patch_launcher.py decoded
java -jar apktool_3.0.3.jar b decoded -o unsigned.apk
zipalign -f -p 4 unsigned.apk aligned.apk
# Sign with apksigner and YOUR keystore; apksigner verify --verbose signed.apk
```

### Signing / installation

The fallback CI key is generated anew for each build: **uninstall prior APKs before installing a fallback-signed build** (back up app data first). Re-signing cannot update the supplied APK in place unless you own its original signing key. For a stable signing identity configure these repository Actions secrets: `APK_KEYSTORE_BASE64` (base64 of your Java keystore), `APK_KEYSTORE_PASSWORD`, `APK_KEY_ALIAS`, `APK_KEY_PASSWORD`. Never commit a keystore or passwords. Even with a stable key, the native check may still reject the rebuild if it expects the original certificate.

The supplied APK is arm64-only for its main native library. No rooted device, overlay runtime test, or original source/keystore was available in this workspace.
