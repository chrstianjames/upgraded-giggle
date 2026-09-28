import tempfile
import unittest
from pathlib import Path

from patch_launcher import patch, replace_method


class LauncherPatchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        app = self.root / 'smali/com/star/android'
        service = self.root / 'smali/com/star/android/service'
        app.mkdir(parents=True)
        service.mkdir()
        self.service = service / 'FloatingService.smali'
        self.service.write_text('''.class public Lcom/star/android/service/FloatingService;
.method public final c()Z
    .locals 1
    invoke-static {p0}, Lcom/star/android/utils/KeyLoginClient;->nativeVerifyApp(Landroid/content/Context;)Z
    const-string v0, "AUTH_TOKEN:"
    return v0
.end method
const-string v0, "CRACK DETECTED • ALL FEATURES LOCKED"
const-string v0, "Look Like You Tryna Crack? Little Skill Like You Forget it 😂"
''')
        login = self.root / 'smali/com/star/android/utils'
        login.mkdir()
        self.login = login / 'KeyLoginClient.smali'
        self.login.write_text('''.class public Lcom/star/android/utils/KeyLoginClient;
.method public static final native nativeVerifyApp(Landroid/content/Context;)Z
.end method
''')
        self.status = self.root / 'smali/b8.smali'
        self.status.write_text('''const-string v0, "CRACK DETECTED • ALL FEATURES LOCKED"
const-string v1, "Look Like You Tryna Crack? Little Skill Like You Forget it 😂"
''')
        self.callbacks = self.root / 'smali/xy.smali'
        self.callbacks.write_text('const-string v0, "Look Like You Tryna Crack? Little Skill Like You Forget it 😂"\n')
        self.launcher = app / 'MainActivity.smali'
        self.launcher.write_text('''.class public Lcom/star/android/MainActivity;
.super Landroidx/activity/ComponentActivity;
.method public final onCreate(Landroid/os/Bundle;)V
    .locals 1
    invoke-static {v0}, Ljg0;->LoginScreen()V
    invoke-static {v0}, Ljg0;->MainScreen()V
    return-void
.end method
.method public final onActivityResult(IILandroid/content/Intent;)V
    .locals 0
    return-void
.end method
''')

    def tearDown(self):
        self.tmp.cleanup()

    def test_direct_menu_launch(self):
        patch(self.root)
        output = self.launcher.read_text()
        create = output.split('.method public final onCreate(', 1)[1].split('.end method', 1)[0]
        self.assertNotIn('LoginScreen', create)
        self.assertIn('canDrawOverlays', create)
        self.assertIn('showMenuIcon()', create)
        self.assertIn('startForegroundService', output)
        self.assertIn('startActivityForResult', output)
        self.assertIn('const/4 v0, 0x0', self.service.read_text())
        self.assertIn('const/4 v0, 0x1', self.login.read_text())
        self.assertNotIn('native nativeVerifyApp', self.login.read_text())
        for path in (self.service, self.status, self.callbacks):
            self.assertNotIn('CRACK DETECTED', path.read_text())
            self.assertNotIn('Tryna Crack', path.read_text())
        with self.assertRaisesRegex(ValueError, 'Already patched'):
            patch(self.root)

    def test_unicode_escaped_smali_strings(self):
        # apktool sometimes prints escaped Unicode rather than literal glyphs.
        for path in (self.service, self.status, self.callbacks):
            path.write_text(path.read_text().replace('•', r'\u2022').replace('😂', r'\ud83d\ude02'))
        patch(self.root)
        for path in (self.service, self.status, self.callbacks):
            self.assertNotIn('CRACK DETECTED', path.read_text())
            self.assertNotIn('Tryna Crack', path.read_text())

    def test_fail_closed_for_unknown_apk(self):
        self.launcher.write_text('.class public Lcom/star/android/MainActivity;\n')
        with self.assertRaisesRegex(ValueError, 'Unexpected original launcher'):
            patch(self.root)

    def test_fail_closed_for_duplicate_method(self):
        with self.assertRaisesRegex(ValueError, 'Expected exactly one'):
            replace_method('.method public final onCreate()V\n.end method\n' * 2, 'onCreate', '')

    def test_no_partial_patch_if_signature_unknown(self):
        before = self.launcher.read_text()
        self.login.write_text('.class public Lcom/star/android/utils/KeyLoginClient;\n')
        with self.assertRaisesRegex(ValueError, 'native signature gate'):
            patch(self.root)
        self.assertEqual(before, self.launcher.read_text())


if __name__ == '__main__':
    unittest.main()
