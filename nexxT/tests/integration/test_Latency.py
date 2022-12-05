# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

import datetime
from pathlib import Path
import re
import subprocess
import sys

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

def test_latency():
    try:
        p = subprocess.run(
            [sys.executable, "-m", "nexxT.core.AppConsole", "--gui", "false", "-a", "test_latency", "-e", """\
from nexxT.Qt.QtCore import QTimer, QObject, QCoreApplication
from nexxT.core.Application import Application
from nexxT.interface import Services, FilterState 
conf = Services.getService("Configuration")
def stateChanged(newState):
    if newState == FilterState.CONSTRUCTED:
        QCoreApplication.quit()
Application.activeApplication.stateChanged.connect(stateChanged)
QTimer.singleShot(10000, conf.deactivate)
""", str(Path(__file__).parent / "latency.json")
             ],
             capture_output=True, timeout=30., encoding="utf-8")
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
    samples = {}
    for t, level, module, msg in logs:
        M = re.search(r"transmit: Sample (\d+)", msg)
        if M is not None:
            s = int(M.group(1))
            assert not s in samples
            samples[s] = [t]
        for fi in range(1,5):
            M = re.search(r"filter%d:received: Sample (\d+)" % fi, msg)
            if M is not None:
                s = int(M.group(1))
                assert s in samples and len(samples[s]) == fi
                samples[s].append(t)
                assert s + 1 not in samples or len(samples[s + 1]) == 1
                assert s + 2 not in samples or len(samples[s + 2]) == 1

    for s in samples:
        ts = samples[s]
        assert len(ts) in [1,5]
        if len(ts) > 1:
            latency = (ts[-1] - ts[0]).total_seconds() + 1.0 # this is the last filter's processing time
            print("Latency of Sample %d: %.1f" % (s, latency))
            assert latency <= 8.2
