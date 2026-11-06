import json,os,tempfile,unittest
os.environ['QT_QPA_PLATFORM']='offscreen'
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import Mock
from PySide6.QtWidgets import QApplication
from claude_status import ClaudeTaskReader,ClaudeTaskSync,TranscriptTail,process_alive,public_events,usage_windows

app=QApplication.instance() or QApplication([])
SESSION='11111111-2222-3333-4444-555555555555'

def write_session(home,status='idle',pid=123,kind='interactive',name='修桌宠',waiting=None):
    folder=Path(home)/'sessions';folder.mkdir(parents=True,exist_ok=True)
    record={'pid':pid,'sessionId':SESSION,'cwd':'/tmp/project','kind':kind,'status':status,'name':name,'statusUpdatedAt':1}
    if waiting:record['waitingFor']=waiting
    (folder/f'{pid}.json').write_text(json.dumps(record),encoding='utf-8')

def assistant(content,**extra):
    return json.dumps({'type':'assistant','message':{'id':extra.pop('id','m1'),'content':content,'usage':extra.pop('usage',{})},**extra})+'\n'

class Reader(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.home=self.temp.name
        self.reader=ClaudeTaskReader(self.home,alive=lambda pid,started:True)
    def tearDown(self):self.temp.cleanup()
    def test_key_files_are_never_opened(self):
        write_session(self.home)
        secret=Path(self.home)/'sessions/123.abc.key';secret.write_text('{"peerToken":"x"}',encoding='utf-8')
        opened=[]
        original=Path.read_text
        def spy(path,*args,**kwargs):
            opened.append(path.name);return original(path,*args,**kwargs)
        Path.read_text=spy
        try:self.assertEqual(len(self.reader.sessions()),1)
        finally:Path.read_text=original
        self.assertEqual(opened,['123.json'])
    def test_automated_sessions_are_ignored(self):
        write_session(self.home,kind='sdk');self.assertEqual(self.reader.sessions(),[])
    def test_dead_process_is_ignored(self):
        write_session(self.home,status='busy')
        self.assertEqual(ClaudeTaskReader(self.home,alive=lambda pid,started:False).sessions(),[])
    def test_only_public_text_and_tool_names_are_read(self):
        record=json.loads(assistant([{'type':'thinking','thinking':'私密推理'},{'type':'text','text':'公开进度'},{'type':'tool_use','name':'Bash','input':{'command':'私密命令'}}]))
        self.assertEqual(public_events(record),(['公开进度'],['Bash']))
        self.assertEqual(public_events({**record,'isSidechain':True}),([],[]))
    def test_tail_reads_new_lines_and_keeps_a_partial_line(self):
        with tempfile.NamedTemporaryFile('w',suffix='.jsonl',delete=False,encoding='utf-8') as file:
            file.write(assistant([{'type':'text','text':'第一段'}]));path=file.name
        tail=TranscriptTail(path);tail.update();self.assertEqual(tail.text,'第一段')
        line=assistant([{'type':'text','text':'第二段'}])
        with open(path,'a',encoding='utf-8') as file:file.write(line[:20])
        tail.update();self.assertEqual(tail.text,'第一段')
        with open(path,'a',encoding='utf-8') as file:file.write(line[20:])
        tail.update();self.assertEqual(tail.text,'第二段');os.unlink(path)
    def test_process_start_is_compared_in_utc(self):
        with unittest.mock.patch('claude_status.psutil.Process') as process:
            process.return_value.create_time.return_value=datetime(2026,11,6,10,10,52,tzinfo=timezone.utc).timestamp()
            self.assertTrue(process_alive(1,'Fri Nov  6 10:10:52 2026'))
            self.assertFalse(process_alive(1,'Fri Nov  6 18:10:52 2026'))
    def test_usage_counts_each_message_once(self):
        folder=Path(self.home)/'projects/p';folder.mkdir(parents=True)
        stamp=datetime.now(timezone.utc).isoformat()
        line=assistant([],timestamp=stamp,usage={'input_tokens':100,'output_tokens':7,'cache_creation_input_tokens':20})
        (folder/'a.jsonl').write_text(line+line,encoding='utf-8')
        rows=usage_windows(self.home)
        self.assertIn('输入 120 · 输出 7 · 1 次回复',rows[0]['text'])
        self.assertTrue(any('不是账户剩余额度' in row['text'] for row in rows))

class FakePet:
    hub=None
    def __init__(self):
        self.settings=Mock();self.settings.value.return_value=True
        for name in ('task_started','task_finished','task_completed','task_progress','task_waiting'):setattr(self,name,Mock())

class Sync(unittest.TestCase):
    def setUp(self):
        self.now=[100.];self.pet=FakePet();self.reader=Mock();self.reader.available.return_value=True
        self.sync=ClaudeTaskSync.__new__(ClaudeTaskSync)
        self.sync.pet=self.pet;self.sync.reader=self.reader;self.sync.clock=lambda:self.now[0]
        self.sync.known={};self.sync.running=set();self.sync.rows=[];self.sync.bootstrap=False
    def row(self,status,text='',key='a',waiting=''):
        return {'key':key,'title':'修桌宠','cwd':'/x','status':status,'waitingFor':waiting,'changed':1,'text':text,'step':''}
    def poll(self,*rows):
        self.reader.sessions.return_value=list(rows);self.sync._poll()
    def test_turn_start_and_completion(self):
        self.poll(self.row('idle'));self.pet.task_started.assert_not_called()
        self.poll(self.row('busy'));self.pet.task_started.assert_called_once()
        self.assertEqual(self.sync.status()['state'],'busy')
        self.poll(self.row('idle','旧回复'));self.pet.task_completed.assert_not_called()
        self.poll(self.row('idle','做好了'))
        self.pet.task_finished.assert_called_once();self.assertEqual(self.pet.task_completed.call_args.args[0],'做好了')
        self.assertEqual(self.sync.status()['state'],'idle')
    def test_session_busy_at_startup_is_silent_but_tracked(self):
        self.sync.bootstrap=True;self.poll(self.row('busy'))
        self.pet.task_started.assert_called_once();self.pet.task_progress.assert_not_called()
    def test_second_session_does_not_restart_or_end_the_work_state(self):
        self.poll(self.row('idle'),self.row('idle',key='b'))
        self.poll(self.row('busy'),self.row('idle',key='b'));self.poll(self.row('busy'),self.row('busy',key='b'))
        self.pet.task_started.assert_called_once()
        self.poll(self.row('idle','一'),self.row('busy',key='b'));self.poll(self.row('idle','一'),self.row('busy',key='b'))
        self.pet.task_finished.assert_not_called();self.pet.task_completed.assert_called_once()
        self.poll(self.row('idle','一'),self.row('idle','二',key='b'));self.poll(self.row('idle','一'),self.row('idle','二',key='b'))
        self.pet.task_finished.assert_called_once()
    def test_waiting_asks_once(self):
        self.poll(self.row('idle'));self.poll(self.row('waiting',waiting='input needed'));self.poll(self.row('waiting',waiting='input needed'))
        self.pet.task_waiting.assert_called_once();self.assertEqual(self.sync.status()['state'],'waiting')
    def test_progress_waits_a_moment_and_skips_repeats(self):
        self.poll(self.row('idle'));self.poll(self.row('busy','开始'));calls=self.pet.task_progress.call_count
        self.poll(self.row('busy','太快的第一条'));self.assertEqual(self.pet.task_progress.call_count,calls)
        self.now[0]+=5;self.poll(self.row('busy','第二条'));self.poll(self.row('busy','第二条'))
        self.assertEqual(self.pet.task_progress.call_count,calls+1)
    def test_a_new_turn_during_the_grace_poll_is_not_a_completion(self):
        self.poll(self.row('idle'));self.poll(self.row('busy'));self.poll(self.row('idle'));self.poll(self.row('busy'));self.poll(self.row('idle'))
        self.pet.task_completed.assert_not_called();self.assertEqual(self.sync.running,{'a'})
    def test_closed_session_is_not_reported_as_success(self):
        self.poll(self.row('idle'));self.poll(self.row('busy'));self.poll()
        self.pet.task_finished.assert_called_once();self.pet.task_completed.assert_not_called()
        self.assertIn('没有确认完成',self.pet.task_progress.call_args.args[0])
    def test_missing_claude_folder_reads_as_offline(self):
        self.reader.available.return_value=False;self.assertEqual(self.sync.status()['state'],'offline')

if __name__=='__main__':unittest.main()
