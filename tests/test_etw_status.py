"""Synthetic PresentMon status-line regression; no ETW/game/process access."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'));sys.path.insert(0,str(ROOT/'tests'))
import capture_frame_intervals as candidate
import offline_xperf as offline
import test_offline_xperf as fixtures

STATUS='[ETW Status] BufferFillPct=25.0% BuffersInUse=16 TotalBuffers=64 EventsLost=0 BuffersLost=0, OverflowedPresents=0'

class StatusTests(unittest.TestCase):
    def test_absent_status_remains_compatible_without_claiming_zero_loss(self):
        self.assertFalse(candidate.event_loss('Started recording.\nStopped recording.\n'))
    def test_well_formed_zero_status_and_high_fill(self):
        self.assertFalse(candidate.event_loss(STATUS))
        self.assertFalse(candidate.event_loss(STATUS.replace('25.0%','100.0%').replace('BuffersInUse=16','BuffersInUse=64')))
    def test_each_positive_counter_is_rejected(self):
        for key in ('EventsLost','BuffersLost','OverflowedPresents'):
            self.assertTrue(candidate.event_loss(STATUS.replace(key+'=0',key+'=1')),key)
        self.assertTrue(candidate.event_loss(STATUS+'\n'+STATUS.replace('EventsLost=0','EventsLost=25')))
    def test_recognizable_malformed_or_missing_fields_fail_closed(self):
        for text in ('[ETW Status] BufferFillPct=25.0%', STATUS.replace('EventsLost=0 ',''),
                     STATUS.replace('BuffersLost=0','BuffersLost=-1'),STATUS.replace('EventsLost=0','EventsLost=NA'),
                     STATUS.replace('OverflowedPresents=0','OverflowedPresents=4294967296'),
                     STATUS.replace('25.0%','nan%'),STATUS.replace('25.0%','101.0%'),
                     STATUS.replace('BuffersInUse=16','BuffersInUse=65'),STATUS+' extra=1','[ETW Status]'):
            self.assertTrue(candidate.event_loss(text),text)
    def test_mixed_prose_warnings_still_rejected(self):
        self.assertTrue(candidate.event_loss(STATUS+'\nwarning: 1 ETW events were lost.'))
        self.assertTrue(candidate.event_loss(STATUS+'\nwarning: 2 overflowed present events detected.'))
    def test_status_tracking_not_automatically_enabled(self):
        self.assertNotIn('--track_etw_status',(ROOT/'tools'/'capture_frame_intervals.py').read_text(encoding='utf-8'))
    def test_mock_live_capture_rejects_positive_counter_with_usable_rows(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary); paths={name:folder/(name+ext) for name,ext in
                (('csv','.csv'),('log','.log'),('metadata','.json'))}
            before={'process_creation_filetime':42}
            args=argparse.Namespace(pid=123,mode='baseline',seconds=10,exe=folder/'synthetic.exe',exe_sha256='1'*64)
            class Collector:
                pid=1000;returncode=0
                def __init__(self,command,stdout,stderr,creationflags):
                    self.polls=0
                    stdout.buffer.write(('Started recording.\n'+STATUS.replace('EventsLost=0','EventsLost=2')+'\n').encode('utf-16'))
                    stdout.buffer.flush();paths['csv'].write_text('mock valid CSV')
                def poll(self):
                    self.polls+=1;return None if self.polls==1 else 0
            with patch.object(candidate,'verify_start',return_value=(folder,paths,before,{},'a'*64)), \
                 patch.object(candidate,'window_snapshot',return_value=before),patch.object(candidate,'sha',return_value='1'*64), \
                 patch.object(candidate.comparison,'read_frames',return_value=([16]*150,list(range(150)),'DXGI')), \
                 patch.object(candidate.subprocess,'Popen',side_effect=Collector),patch.object(candidate.time,'sleep'):
                with self.assertRaisesRegex(ValueError,'evidence checks'):candidate.capture(args)
            record=json.loads(paths['metadata'].read_text())
            self.assertEqual(record['state'],'invalid');self.assertTrue(record['collector_event_loss_warning'])
    def test_actual_offline_validator_rejects_bound_status_loss(self):
        fx=fixtures.OfflineEvidenceTests('runTest');fx.setUp();self.addCleanup(fx.doCleanups)
        log=fx.parse_log;proof=fx.capture['offline_etw']
        log.write_text(STATUS+'\n');proof['parse_log_sha256']=offline.base.sha(log)
        self.assertIn('parse_log=sha256_loss_checked',fx.check())
        for key in ('EventsLost','BuffersLost','OverflowedPresents'):
            log.write_text(STATUS.replace(key+'=0',key+'=1')+'\n');proof['parse_log_sha256']=offline.base.sha(log)
            with self.assertRaisesRegex(ValueError,'reports loss'):fx.check()
        log.write_text('[ETW Status] BufferFillPct=25.0%\n');proof['parse_log_sha256']=offline.base.sha(log)
        with self.assertRaisesRegex(ValueError,'reports loss'):fx.check()

if __name__=='__main__':unittest.main(verbosity=2,failfast=True)
