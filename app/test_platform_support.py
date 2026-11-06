import unittest,sys,os
from pathlib import Path
from unittest.mock import MagicMock,patch
import platform_support as p

class PlatformTests(unittest.TestCase):
    def test_mac_bundle_resources(self):
        with patch.object(sys,'platform','darwin'),patch.object(sys,'frozen',True,create=True),patch.object(sys,'executable','/Applications/BailongPet.app/Contents/MacOS/BailongPet'):
            self.assertEqual(p.resource_root(),Path(sys.executable).resolve().parents[1]/'Resources')
    def test_mac_user_data_outside_bundle(self):
        with patch.object(sys,'platform','darwin'),patch.dict(os.environ,{'BAILONG_DATA_DIR':''}):
            self.assertEqual(p.user_data(),Path.home()/'Library/Application Support/BailongPet')
    def test_mac_launch_does_not_use_windows_flags(self):
        import autostart
        with patch.object(sys,'platform','darwin'),patch('autostart.subprocess.Popen') as launch:
            autostart.launch_pet();self.assertNotIn('creationflags',launch.call_args.kwargs)

    @unittest.skipUnless(sys.platform=='darwin','需要AppKit常量')
    def test_mac_window_never_combines_exclusive_spaces(self):
        import objc
        from AppKit import NSWindowCollectionBehaviorMoveToActiveSpace as move,NSWindowCollectionBehaviorCanJoinAllSpaces as join
        class Window:
            behavior=move|256
            def collectionBehavior(self):return self.behavior
            def setCollectionBehavior_(self,value):
                # AppKit raises the same way for this pair.
                if value&move and value&join:raise objc.error('exclusive')
                self.behavior=value
        window=Window();widget=MagicMock();widget.winId.return_value=1
        with patch('PySide6.QtGui.QGuiApplication.platformName',return_value='cocoa'),patch('objc.objc_object') as native:
            native.return_value.window.return_value=window
            p.configure_mac_window(widget)
        self.assertEqual(window.behavior,join|256)
    def test_offscreen_window_id_is_never_dereferenced(self):
        with patch.object(sys,'platform','darwin'),patch('PySide6.QtGui.QGuiApplication.platformName',return_value='offscreen'),patch('objc.objc_object') as native:
            p.configure_mac_window(MagicMock())
        native.assert_not_called()
    def test_codex_is_found_inside_renamed_chatgpt_app(self):
        import quota
        bundled='/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex'
        with patch.object(sys,'platform','darwin'),patch('quota.shutil.which',return_value=None),patch.dict(os.environ,{'BAILONG_CODEX':''}),\
             patch('pathlib.Path.is_file',lambda path:str(path)==bundled),patch('quota.os.access',return_value=True):
            self.assertEqual(quota.find_codex(),bundled)
    def test_codex_child_can_reach_node_from_a_finder_launch(self):
        import quota
        with patch.object(sys,'platform','darwin'),patch.dict(os.environ,{'PATH':'/usr/bin:/bin'}):
            self.assertIn('/opt/homebrew/bin',quota.codex_env()['PATH'].split(':'))
        with patch.object(sys,'platform','win32'):self.assertIsNone(quota.codex_env())

if __name__=='__main__':unittest.main()
