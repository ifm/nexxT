# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

import glob
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import datetime

def parse_log(strlog):
    res = []
    for l in strlog.split("\n"):
        l = l.strip()
        if l == "":
            continue
        try:
            t = datetime.datetime.strptime(l[:19], '%Y-%m-%d %H:%M:%S')
            ms = int(l[20:23])
            t = t + datetime.timedelta(microseconds=ms*1000)
            l = l[24:]
            level = l[:l.find(" ")]
            l = l[l.find(" ")+1:]
            module = l[:l.find(":")]
            l = l[l.find(":")+1:]
            msg = l.strip()
            res.append((t,level,module,msg))
        except:
            pass
    return res

def test_BasicWorkflow():
    with tempfile.TemporaryDirectory() as d:
        shutil.copy(Path(__file__).parent / "basicworkflow_script.py", d)
        shutil.copytree(Path(__file__).parent.parent / "binary", Path(d) / "binary")
        shutil.copy(Path(__file__).parent.parent / "interface" / "SimpleStaticFilter.py", d)

        h5files = []
        for stage in range(3):

            if stage == 0:
                args = ["-e", "stage=0", "-s", "basicworkflow_script.py"]
            elif stage == 1:
                args = ["-e", "stage=1", "-s", "basicworkflow_script.py", "-a", "myApp", "basicworkflow.json"]
            elif stage == 2:
                args = ["-e", "stage=2", "-s", "basicworkflow_script.py", "-a", "pbApp", "basicworkflow.json"]

            try:
                p = subprocess.run(
                    [sys.executable, "-m", "nexxT.core.AppConsole", "--gui", "false"] + args,
                    cwd=d, capture_output=True, timeout=15., encoding="utf-8")
                timeout = False
            except subprocess.TimeoutExpired as e:
                p = e
                timeout = True

            print("STDOUT", p.stdout)
            print("STDERR", p.stderr)
            assert not timeout
            p.check_returncode()
            assert p.stdout.strip() == ""
            logs = parse_log(p.stderr)
            if stage < 2:
                runs = []
                for l in logs:
                    if l[-1] == "app activated":
                        runs.append(dict(transmit=[],receive=[]))
                    if l[-1].startswith("Transmitting Sample") or l[-1].startswith("transmit:"):
                        runs[-1]["transmit"].append(l[0])
                    if l[-1].startswith("received:"):
                        runs[-1]["receive"].append(l[0])
                assert len(runs) == 3
                for r in runs:
                    nt = len(r["transmit"])
                    nr = len(r["receive"])
                    assert nt == nr or nt == nr+1
                    dtt = [(r["transmit"][i] - r["transmit"][i-1]).total_seconds() for i in range(1, nt)]
                    dtr = [(r["receive"][i] - r["receive"][i-1]).total_seconds() for i in range(1, nr)]
                    assert all([0.07 < dt < 0.13 for dt in dtt])
                    assert all([0.07 < dt < 0.13 for dt in dtr])
                recs = glob.glob(d + "/*.h5")
                assert len(recs) == len(h5files) + 1
                h5files = recs
            else:
                allFrames = []
                sample1Cnt = 0
                sample2Cnt = 0
                lastSample1 = None
                lastSample2 = None
                mode = "playing"
                for l in logs:
                    if mode == "playing":
                        if l[-1] == "played":
                            mode = "seekBegin"
                        if "(flt1)" in l[-1] or "(flt2)" in l[-1]:
                            allFrames.append(l)
                            idx = int(l[-1][len("(flt2) received: Sample "):])
                            if "(flt1)" in l[-1]:
                                sample1Cnt += 1
                                assert lastSample1 is None or idx == lastSample1 + 1
                                lastSample1 = idx
                            if "(flt2)" in l[-1]:
                                sample2Cnt += 1
                                assert lastSample2 is None or idx == lastSample2 + 1
                                lastSample2 = idx
                    elif mode == "seekBegin":
                        if l[-1] == "seekBeginning":
                            nsteps = 0
                            idx = 1
                            mode = "stepFwd[None]"
                        if "(flt1)" in l[-1] or "(flt2)" in l[-1]:
                            assert l[-1] == allFrames[0][-1]
                    elif mode == "stepFwd[None]":
                        if l[-1] == "stepForward[None]":
                            idx += 1
                            nsteps += 1
                            if idx > 10:
                                nsteps = 0
                                expectPause = False
                                mode = "stepFwd[stream1]"
                        if "(flt1)" in l[-1] or "(flt2)" in l[-1]:
                            assert l[-1] == allFrames[idx][-1]
                    elif mode == "stepFwd[stream1]":
                        if l[-1] == "stepForward[stream1]":
                            assert expectPause
                            expectPause = False
                            nsteps += 1
                            if nsteps >= 10:
                                nsteps = 0
                                expectPause = False
                                mode = "stepFwd[stream2]"
                        if "(flt1)" in l[-1] or "(flt2)" in l[-1]:
                            assert not expectPause
                            assert l[-1] == allFrames[idx][-1]
                            idx += 1
                            if "(flt1)" in l[-1]:
                                expectPause = True
                    elif mode == "stepFwd[stream2]":
                        if l[-1] == "stepForward[stream2]":
                            assert expectPause or idx >= len(allFrames)
                            expectPause = False
                            nsteps += 1
                            if nsteps >= 2:
                                nsteps = 0
                                expectPause = False
                                mode = "seekTime"
                        if "(flt1)" in l[-1] or "(flt2)" in l[-1]:
                            assert not expectPause
                            assert l[-1] == allFrames[idx][-1]
                            idx += 1
                            if "(flt2)" in l[-1]:
                                expectPause = True
                    elif mode == "seekTime":
                        if l[-1] == "seekTime":
                            assert expectPause
                            mode = "seekEnd"
                            expectPause = False
                        if "(flt1)" in l[-1] or "(flt2)" in l[-1]:
                            assert not expectPause
                            idx = [f[-1] for f in allFrames].index(l[-1])
                            assert idx >= len(allFrames)/3 and idx <= len(allFrames)*2/3
                            expectPause = True
                    elif mode == "seekEnd":
                        if l[-1] == "seekEnd":
                            assert expectPause
                            mode = "stepBwd[None]"
                            expectPause = False
                            nsteps = 0
                        if "(flt1)" in l[-1] or "(flt2)" in l[-1]:
                            assert not expectPause
                            assert l[-1] == allFrames[-1][-1]
                            idx = len(allFrames)-1
                            expectPause = True
                    elif mode == "stepBwd[None]":
                        if l[-1] == "stepBackward[None]":
                            assert expectPause
                            expectPause = False
                            nsteps += 1
                            if nsteps == 10:
                                mode = "seekTimeBegin"
                        if "(flt1)" in l[-1] or "(flt2)" in l[-1]:
                            idx -= 1
                            assert l[-1] == allFrames[idx][-1]
                            expectPause = True
                    elif mode == "seekTimeBegin":
                        if l[-1] == "seekTimeBegin":
                            assert expectPause
                            expectPause = False
                            mode = "seekTimeEnd"
                        if "(flt1)" in l[-1] or "(flt2)" in l[-1]:
                            assert l[-1] == allFrames[0][-1]
                            expectPause = True
                    elif mode == "seekTimeEnd":
                        if l[-1] == "seekTimeEnd":
                            assert expectPause
                            expectPause = False
                            mode = "done"
                        if "(flt1)" in l[-1] or "(flt2)" in l[-1]:
                            assert l[-1] == allFrames[-1][-1]
                            expectPause = True
                    elif mode == "done":
                        assert not "(flt1)" in l[-1] and not "(flt2)" in l[-1]
                    else:
                        assert False, "Unknown mode %s" % mode



if __name__ == "__main__":
    test_BasicWorkflow()
