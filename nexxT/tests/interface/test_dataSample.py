# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

import logging
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

if __name__ == "__main__":
    test_basic()