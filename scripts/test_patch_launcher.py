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
        (service / 'FloatingService.smali').write_text(
            '.class public Lcom/star/android/service/FloatingService;\n'
        )
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
        with self.assertRaisesRegex(ValueError, 'Already patched'):
            patch(self.root)

    def test_fail_closed_for_unknown_apk(self):
        self.launcher.write_text('.class public Lcom/star/android/MainActivity;\n')
        with self.assertRaisesRegex(ValueError, 'Unexpected original launcher'):
            patch(self.root)

    def test_fail_closed_for_duplicate_method(self):
        with self.assertRaisesRegex(ValueError, 'Expected exactly one'):
            replace_method('.method public final onCreate()V\n.end method\n' * 2, 'onCreate', '')


if __name__ == '__main__':
    unittest.main()
