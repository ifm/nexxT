# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

import logging
import math
import platform
import time
import pytest
from nexxT.interface import DataSample

logging.getLogger(__name__).debug("executing test_dataSample.py")

def test_basic():
    dataSample = DataSample(b"Hello", "String", 38)
    assert dataSample.getContent().data() == b'Hello'

    # get the content and modify it
    c = dataSample.getContent()
    c[:] = b'a'*c.size()
    assert c.data() == b'aaaaa'
    # but the modification is not affecting the original data
    assert dataSample.getContent().data() == b'Hello'

@pytest.mark.skipif(platform.system() == "Windows" and platform.release() == "7", 
                    reason="windows 10 or higher, windows 7 seems to have millisecond resolution on timestamps.")
def test_currentTime():
    shortestDelta = math.inf
    ts = time.time()
    lastT = DataSample.currentTime()
    factor = round(DataSample.TIMESTAMP_RES / 1e-9)
    deltas = []
    while time.time() - ts < 3:
        t = DataSample.currentTime()
        # assert that the impementation is consistent with time.time()
        deltas.append(abs(t - (time.time_ns() // factor))*DataSample.TIMESTAMP_RES)
        if t != lastT:
            shortestDelta = min(t - lastT, shortestDelta)
        lastT = t

    # make sure that the average delta is smaller than 1 millisecond
    assert sum(deltas)/len(deltas) < 1e-3
    shortestDelta = shortestDelta * DataSample.TIMESTAMP_RES
    # we want at least 10 microseconds resolution
    print("shortestDelta: %s" % shortestDelta)
    assert shortestDelta <= 1e-5

if __name__ == "__main__":
    test_basic()
    test_currentTime()