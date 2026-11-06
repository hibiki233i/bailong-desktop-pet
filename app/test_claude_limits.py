import json,os,shutil,stat,subprocess,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
import claude_limits as limits

REPORT={'model':{'display_name':'Opus'},'cwd':'/private/project','rate_limits':{'five_hour':{'used_percentage':23.5,'resets_at':2000000000},'seven_day':{'used_percentage':41.2,'resets_at':2000000000}}}

class Windows(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
        self.path=Path(self.folder.name)/'limits.json'
    def save(self,data,age=0):
        self.path.write_text(json.dumps(data),encoding='utf-8')
        stamp=1900000000-age;os.utime(self.path,(stamp,stamp))
    def test_report_becomes_remaining_share_and_reset_time(self):
        self.save(REPORT,age=180)
        rows=limits.limit_windows(self.path,now=1900000000)
        self.assertEqual(rows[0],{'name':'5小时','remaining':76.5,'resetsAt':2000000000})
        self.assertEqual(rows[1]['name'],'一周');self.assertAlmostEqual(rows[1]['remaining'],58.8)
        self.assertEqual(rows[2],{'name':'更新','text':'3 分钟前'})
    def test_past_window_is_not_shown_as_current(self):
        report={'rate_limits':{'five_hour':{'used_percentage':90,'resets_at':1800000000},'seven_day':{'used_percentage':10,'resets_at':2000000000}}}
        self.save(report)
        rows=limits.limit_windows(self.path,now=1900000000)
        self.assertNotIn('remaining',rows[0]);self.assertIn('已重置',rows[0]['text']);self.assertEqual(rows[1]['remaining'],90)
    def test_absent_window_is_reset_because_claude_code_drops_past_windows(self):
        self.save({'rate_limits':{'seven_day':{'used_percentage':10,'resets_at':2000000000}}})
        rows=limits.limit_windows(self.path,now=1900000000)
        self.assertIn('已重置',rows[0]['text']);self.assertEqual(rows[1]['remaining'],90)
    def test_nothing_current_falls_back(self):
        self.save({'rate_limits':{}})
        self.assertIsNone(limits.limit_windows(self.path,now=1900000000))
    def test_used_share_is_kept_in_range(self):
        self.save({'rate_limits':{'five_hour':{'used_percentage':130,'resets_at':2000000000}}})
        self.assertEqual(limits.limit_windows(self.path,now=1900000000)[0]['remaining'],0)
    def test_missing_or_damaged_report_falls_back(self):
        self.assertIsNone(limits.limit_windows(self.path))
        for text in ('{not json','[]','{"rate_limits":3}'):
            self.path.write_text(text,encoding='utf-8');self.assertIsNone(limits.limit_windows(self.path))
    def test_age_text(self):
        self.assertEqual([limits.age(s) for s in (5,120,7200,259200)],['刚刚','2 分钟前','2 小时前','3 天前'])

class Install(unittest.TestCase):
    def setUp(self):
        # Both folders are scratch: these tests must never reach the real Claude settings or app data.
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        self.home=Path(folder.name)/'claude home';self.home.mkdir()
        self.data=Path(folder.name)/'pet data'
        started=patch('claude_limits.user_data',lambda:self.data);started.start();self.addCleanup(started.stop)
        self.settings=self.home/'settings.json'
    def stored(self):return json.loads(self.settings.read_text(encoding='utf-8'))
    def script(self):return self.data/limits.SCRIPT_NAME
    def run_script(self,data,path=None):
        env={'PATH':path or os.environ['PATH']}
        return subprocess.run([str(self.script())],input=json.dumps(data),capture_output=True,text=True,env=env,timeout=10)
    def test_enable_keeps_other_settings_and_mode(self):
        self.settings.write_text(json.dumps({'model':'opus','hooks':{'Stop':[{'hooks':[]}]},'语言':'中文'},ensure_ascii=False),encoding='utf-8')
        self.settings.chmod(0o640)
        limits.enable(self.home)
        data=self.stored()
        self.assertEqual(list(data),['model','hooks','语言','statusLine'])
        self.assertEqual(data['hooks'],{'Stop':[{'hooks':[]}]});self.assertEqual(data['语言'],'中文')
        self.assertEqual(data['statusLine']['type'],'command')
        self.assertTrue(limits.enabled(self.home))
        self.assertEqual(stat.S_IMODE(self.settings.stat().st_mode),0o640)
        self.assertEqual(sorted(p.name for p in self.home.iterdir()),['settings.json'])
    def test_command_survives_a_folder_with_spaces(self):
        limits.enable(self.home)
        result=subprocess.run(self.stored()['statusLine']['command'],shell=True,input=json.dumps(REPORT),capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertTrue((self.data/limits.LIMITS_NAME).is_file())
    def test_enable_twice_is_harmless(self):
        limits.enable(self.home);limits.enable(self.home);self.assertTrue(limits.enabled(self.home))
    def test_enable_without_a_settings_file(self):
        limits.enable(self.home);self.assertEqual(list(self.stored()),['statusLine'])
    def test_someone_elses_status_line_is_left_alone(self):
        original=json.dumps({'statusLine':{'type':'command','command':'my-line'}})
        self.settings.write_text(original,encoding='utf-8')
        with self.assertRaisesRegex(RuntimeError,'已经有'):limits.enable(self.home)
        limits.disable(self.home)
        self.assertEqual(self.settings.read_text(encoding='utf-8'),original);self.assertFalse(self.script().exists())
    def test_damaged_settings_are_not_rewritten(self):
        self.settings.write_text('{"model": ',encoding='utf-8')
        with self.assertRaises(RuntimeError):limits.enable(self.home)
        self.assertEqual(self.settings.read_text(encoding='utf-8'),'{"model": ')
        self.assertFalse(limits.enabled(self.home))
    def test_disable_removes_only_what_enable_added(self):
        self.settings.write_text(json.dumps({'model':'opus'}),encoding='utf-8')
        limits.enable(self.home);self.run_script(REPORT)
        limits.disable(self.home)
        self.assertEqual(self.stored(),{'model':'opus'})
        self.assertEqual(list(self.data.iterdir()),[])
    @unittest.skipUnless(shutil.which('jq'),'需要 jq')
    def test_script_saves_only_the_limits_and_prints_a_line(self):
        limits.enable(self.home)
        result=self.run_script(REPORT)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout.strip(),'Opus · 5 小时剩 76% · 7 天剩 58%')
        saved=self.data/limits.LIMITS_NAME
        self.assertEqual(json.loads(saved.read_text(encoding='utf-8')),{'rate_limits':REPORT['rate_limits']})
        self.assertEqual(stat.S_IMODE(saved.stat().st_mode),0o600)
    def test_script_without_jq_still_saves_limits(self):
        limits.enable(self.home)
        tools=self.home/'tools';tools.mkdir()
        for name in ('cat','dirname','mv'):(tools/name).symlink_to(shutil.which(name))
        result=self.run_script(REPORT,str(tools))
        self.assertEqual(result.returncode,0,result.stderr)
        rows=limits.limit_windows(self.data/limits.LIMITS_NAME,now=1900000000)
        self.assertEqual(rows[0]['remaining'],76.5)
    def test_session_before_its_first_reply_keeps_saved_limits(self):
        limits.enable(self.home);self.run_script(REPORT)
        result=self.run_script({'model':{'display_name':'Opus'}})
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads((self.data/limits.LIMITS_NAME).read_text(encoding='utf-8'))['rate_limits'],REPORT['rate_limits'])
    def test_script_leaves_no_temporary_files(self):
        limits.enable(self.home);self.run_script(REPORT)
        self.assertEqual(sorted(p.name for p in self.data.iterdir()),[limits.LIMITS_NAME,limits.SCRIPT_NAME])

if __name__=='__main__':unittest.main()
