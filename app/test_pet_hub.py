import os,sys,tempfile,time,unittest
os.environ['QT_QPA_PLATFORM']='offscreen'
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from characters import CLAUDE,CODEX,CHARACTERS
import pet as pet_module
from pet_hub import PetHub
from control_panel import ControlPanel,describe

app=QApplication.instance() or QApplication([])
def has_assets(character):return (pet_module.ROOT/character.assets/'素材清单.json').is_file()

@unittest.skipUnless(has_assets(CLAUDE) and has_assets(CODEX),'需要两套素材')
class Hub(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # QSettings(org,app) always means the real preferences, so point every copy at a scratch file.
        cls.settings=tempfile.TemporaryDirectory()
        scratch=lambda organization,application:QSettings(str(Path(cls.settings.name)/'pet.ini'),QSettings.Format.IniFormat)
        cls.patches=[patch('pet.QSettings',scratch),patch('pet_hub.QSettings',scratch)]
        for item in cls.patches:item.start()
        cls.hub=PetHub(pet_module.Pet);cls.claude,cls.codex=cls.hub.pets
    @classmethod
    def tearDownClass(cls):
        with patch('pet_hub.QApplication.quit'):cls.hub.quit()
        for item in cls.patches:item.stop()
        cls.settings.cleanup()
    def test_pets_are_separate_characters_with_separate_settings(self):
        self.assertEqual([p.character.id for p in self.hub.pets],['claude','codex'])
        self.assertNotEqual(self.claude.assets,self.codex.assets)
        self.assertNotEqual(self.claude.settings.group(),self.codex.settings.group())
        self.claude.set_size_percent(120);self.assertEqual(self.codex.size_percent,100);self.claude.set_size_percent(100)
    def test_reopen_listener_waits_for_the_event_loop(self):
        with patch('pet_hub.on_mac_reopen') as listen:
            self.hub.listen_for_reopen()
        listen.assert_called_once_with(self.hub.reveal)
    def test_pets_start_side_by_side(self):
        self.assertNotEqual(self.claude.pos(),self.codex.pos())
    def test_one_tray_serves_both(self):
        self.assertIs(self.claude.tray,self.codex.tray)
        self.hub.refresh_tray_menu()
        texts=[a.text() for a in self.hub.tray_menu.actions() if not a.isSeparator()]
        self.assertEqual(texts,['控制面板…','显示 Claude 桌宠','显示 Codex 桌宠','退出桌宠'])
    def test_hiding_one_pet_leaves_the_other_and_is_remembered(self):
        self.claude.set_manual_hidden(True)
        self.assertFalse(self.claude.isVisible());self.assertTrue(self.codex.isVisible())
        self.assertTrue(self.hub.saved_hidden(self.claude))
        self.claude.set_manual_hidden(False);self.assertFalse(self.hub.saved_hidden(self.claude))
    def test_claude_menu_has_no_codex_chat(self):
        claude=[a.text() for a in self.claude.context_menu().actions()]
        codex=[a.text() for a in self.codex.context_menu().actions()]
        self.assertNotIn('打开对话模式',claude);self.assertIn('打开对话模式',codex)
        self.assertEqual(claude[0],'控制面板…')
    def test_quota_titles_do_not_mix_up_agents(self):
        from PySide6.QtWidgets import QLabel
        pet=self.claude;pet.quota_generation=pet.generation;title=lambda:pet.bubble.findChildren(QLabel)[0].text()
        with patch.object(pet,'speech_hidden',lambda:False):
            pet.quota_ready([{'name':'今天','text':'输入 1'}]);self.assertEqual(title(),'Claude 本机用量')
            pet.quota_ready([{'name':'5小时','remaining':76.5,'resetsAt':None}]);self.assertEqual(title(),'Claude 剩余额度')
        pet.bubble.hide()
    def test_real_limits_come_first_and_local_usage_is_the_fallback(self):
        real=[{'name':'5小时','remaining':50,'resetsAt':None}]
        with patch('claude_limits.limit_windows',lambda:real),patch('claude_status.usage_windows',side_effect=AssertionError):
            self.assertEqual(CLAUDE.read_quota(None),real)
        with patch('claude_limits.limit_windows',lambda:None),patch('claude_status.usage_windows',lambda cancel:['local']):
            self.assertEqual(CLAUDE.read_quota(None),['local'])
    @unittest.skipUnless(sys.platform=='darwin','只有 macOS 提供这个开关')
    def test_panel_switch_changes_claude_settings_through_one_path(self):
        state={'on':False}
        # The panel reads the real settings unless this is patched first, and this machine may have the line enabled.
        with patch('claude_limits.enabled',lambda:state['on']),patch('claude_limits.enable',lambda:state.update(on=True)),patch('claude_limits.disable',lambda:state.update(on=False)):
            panel=ControlPanel(self.hub);panel.refresh();card=panel.cards[0];self.assertIsNone(panel.cards[1].limits)
            self.assertFalse(card.limits.isChecked())
            card.limits.setChecked(True);self.assertTrue(state['on']);self.assertTrue(card.limits.isChecked())
            card.limits.setChecked(False);self.assertFalse(state['on'])
            panel.close()
    @unittest.skipUnless(sys.platform=='darwin','只有 macOS 提供这个开关')
    def test_panel_switch_shows_why_it_could_not_change_settings(self):
        def refuse():raise RuntimeError('已经有自定义状态栏')
        with patch('claude_limits.enabled',lambda:False),patch('claude_limits.enable',refuse),patch('control_panel.QMessageBox.warning') as warning:
            panel=ControlPanel(self.hub);panel.refresh();card=panel.cards[0]
            card.limits.setChecked(True)
            warning.assert_called_once();self.assertFalse(card.limits.isChecked())
            panel.close()
    def test_ask_clip_plays_when_claude_waits(self):
        self.claude.task_waiting('请确认',lambda:None)
        self.assertEqual(self.claude.mode,'asking')
        self.claude.task_finished();self.assertNotEqual(self.claude.mode,'asking')
    def test_panel_controls_reach_the_pet_and_follow_it(self):
        self.hub.show_panel();panel=self.hub.panel;card=panel.cards[0];pet=card.pet
        before=pet.auto_movement_disabled
        card.walk.setChecked(before);self.assertEqual(pet.auto_movement_disabled,not before)
        pet.set_auto_movement_disabled(before);panel.refresh();self.assertEqual(card.walk.isChecked(),not before)
        card.size_slider.setValue(150);self.assertEqual(pet.width(),384);card.size_slider.setValue(100)
        card.show_box.setChecked(False);self.assertTrue(pet.manual_hidden);self.assertFalse(card.quota.isEnabled())
        card.show_box.setChecked(True);self.assertTrue(card.quota.isEnabled())
        panel.close()
    def test_panel_shows_each_agent_status(self):
        panel=ControlPanel(self.hub)
        with patch.object(self.claude.desktop_sync,'status',return_value={'state':'busy','sessions':[{'title':'修桌宠','state':'busy','detail':'正在修改文件'}],'open':2}):
            panel.refresh()
        self.assertIn('工作中',panel.cards[0].state.text());self.assertIn('修桌宠',panel.cards[0].detail.text())
        panel.close()

class Describe(unittest.TestCase):
    def test_empty_and_long_lists(self):
        self.assertEqual(describe({'state':'idle','sessions':[]}),'没有进行中的任务')
        rows=[{'title':str(i),'state':'busy','detail':''} for i in range(5)]
        self.assertIn('还有 2 项',describe({'state':'busy','sessions':rows}))

if __name__=='__main__':unittest.main()
