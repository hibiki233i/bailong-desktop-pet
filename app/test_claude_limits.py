import http.server,json,os,shutil,socket,stat,subprocess,tempfile,threading,time,unittest
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

MAGPIE={'object':'list','data':[
    {'provider':'claude','name':'Claude Code','kind':'subscription','user':'someone@example.com','readAt':'2030-03-17T17:43:20+08:00','last':True,
     'windows':[{'name':'5 hours','used':55,'remaining':45,'resetsAt':'2030-03-18T01:20:00+08:00','holds':{'tokens':344}},
                {'name':'7 days','used':8,'remaining':92,'resetsAt':'2030-03-23T20:00:00+08:00'}]},
    {'provider':'codex','name':'Codex','user':'someone@example.com','readAt':'2030-03-17T17:43:20+08:00','windows':[{'name':'5 hours','used':14,'resetsAt':'2030-03-18T02:09:30+08:00'}]}]}
READ_AT=1899971000.0

class Magpie(unittest.TestCase):
    def rows(self,report=MAGPIE,provider='claude',now=READ_AT+120):
        return limits.magpie_windows(provider,report,now)
    def test_report_becomes_remaining_share_and_reset_time(self):
        rows=self.rows()
        self.assertEqual([row['name'] for row in rows],['5小时','一周','更新'])
        self.assertEqual(rows[0]['remaining'],45);self.assertEqual(rows[1]['remaining'],92)
        self.assertEqual(rows[0]['resetsAt'],1899998400.0);self.assertEqual(rows[2]['text'],'2 分钟前')
    def test_each_agent_reads_its_own_entry(self):
        self.assertEqual(self.rows(provider='codex')[0]['remaining'],86)
        self.assertIsNone(self.rows(provider='gemini'))
    def test_account_email_stays_out_of_the_rows(self):
        self.assertNotIn('example.com',json.dumps(self.rows(),ensure_ascii=False))
    def test_latest_account_wins_when_there_are_several(self):
        older={'provider':'claude','readAt':MAGPIE['data'][0]['readAt'],'windows':[{'name':'5 hours','used':99,'resetsAt':'2030-03-18T01:20:00+08:00'}]}
        report={'data':[older,MAGPIE['data'][0]]}
        self.assertEqual(self.rows(report)[0]['remaining'],45)
    def test_past_window_is_not_shown_as_current(self):
        rows=self.rows(now=1899998500.0)
        self.assertIn('已重置',rows[0]['text']);self.assertEqual(rows[1]['remaining'],92)
    def test_unknown_window_keeps_its_name(self):
        report={'data':[{'provider':'claude','windows':[{'name':'Weekly Opus','used':5,'resetsAt':None}]}]}
        self.assertEqual(self.rows(report),[{'name':'Weekly Opus','remaining':95,'resetsAt':None}])
    def test_changed_format_falls_back_instead_of_failing(self):
        for report in ([],{},{'data':3},{'data':[3]},{'data':[{'provider':'claude'}]},{'data':[{'provider':'claude','windows':3}]},
                       {'data':[{'provider':'claude','windows':[3,{'name':'5 hours'},{'name':'5 hours','used':'55'}]}]}):
            self.assertIsNone(self.rows(report),report)
    def test_bad_time_text_only_loses_that_detail(self):
        report={'data':[{'provider':'claude','readAt':'soon','windows':[{'name':'5 hours','used':10,'resetsAt':'later'}]}]}
        self.assertEqual(self.rows(report),[{'name':'5小时','remaining':90,'resetsAt':None}])

class MagpieServer(unittest.TestCase):
    def serve(self,status,body):
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(status);self.end_headers();self.wfile.write(body)
            def log_message(self,*args):pass
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        return f'http://127.0.0.1:{server.server_port}/v1/magpie/quotas'
    def test_reads_the_local_report(self):
        self.assertEqual(limits.read_magpie(self.serve(200,json.dumps(MAGPIE).encode())),MAGPIE)
    def test_error_page_or_other_service_is_none(self):
        self.assertIsNone(limits.read_magpie(self.serve(404,b'{}')))
        self.assertIsNone(limits.read_magpie(self.serve(200,b'<html>')))
    def test_stopped_magpie_is_none(self):
        with socket.socket() as probe:
            probe.bind(('127.0.0.1',0));closed=probe.getsockname()[1]
        self.assertIsNone(limits.read_magpie(f'http://127.0.0.1:{closed}/',timeout=1))
    def test_stopped_magpie_gives_no_rows(self):
        with patch('claude_limits.read_magpie',lambda:None):self.assertIsNone(limits.magpie_windows())

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
