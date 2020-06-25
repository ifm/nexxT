# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

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

        for stage in range(2):

            if stage == 0:
                args = ["-e", "stage=0", "-s", "basicworkflow_script.py"]
            elif stage == 1:
                args = ["-e", "stage=1", "-s", "basicworkflow_script.py", "-a", "myApp", "basicworkflow.json"]

            try:
                p = subprocess.run(
                    [sys.executable, "-m", "nexxT.core.AppConsole", "--gui", "false"] + args,
                    cwd=d, capture_output=True, timeout=15., encoding="utf-8")
                #p = subprocess.run([sys.executable, Path(sys.executable).parent / "nexxT-gui", "-h"], capture_output=True, encoding="utf-8")
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




if __name__ == "__main__":
    test_BasicWorkflow()
