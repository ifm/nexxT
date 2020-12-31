# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This module defines the filter ImageBlur as a little showcase for a long-running algorithm
"""

import numpy as np
from nexxT.interface import Filter, DataSample
from nexxT.examples.framework.ImageData import byteArrayToNumpy, numpyToByteArray

class ImageBlur(Filter):
    """
    A filter providing the parameter kernelSize. A box filter of this size is applied to the input image
    and the output is transferred over the output port.
    """
    def __init__(self, env):
        super().__init__(False, False, env)
        # add the input port for the filter
        self.inPort = self.addStaticInputPort("video_in")
        # add the output port for the filter
        self.outPort = self.addStaticOutputPort("video_out")
        # define the kernelSize property
        pc = self.propertyCollection()
        pc.defineProperty("kernelSize", 3, "Kernel size of a simple blurring kernel", options=dict(min=1, max=99))

    def onPortDataChanged(self, port):
        """
        Overloaded from Filter base class. The method is called whenever new data arrives at an input port.
        :param port: the port which has new data.
        :return:
        """
        if port.getData().getDatatype() == "example/image":
            # we don't (want to) have scipy or opencv in the dependency list, so we do that by hand, it is just a
            # showcase
            ks = self.propertyCollection().getProperty("kernelSize")
            # assert odd kernel size
            ks = (ks//2)*2 + 1
            if ks > 1: # non-trivial size ?
                # efficient (zero-copy) conversion
                in_img = byteArrayToNumpy(port.getData().getContent())
                # apply the filter
                res = boxFilter(in_img, ks)
                # create a DataSample instance to be transferred over the port
                sample = DataSample(numpyToByteArray(res), "example/image", port.getData().getTimestamp())
            else:
                # filter is no-op, we reuse the input data in this case
                sample = port.getData()
            # finally transmit the result
            self.outPort.transmit(sample)

def boxFilter(img, kernelSize):
    """
    2D box filter operating on single or multichannel input images
    :param img: the image as a numpy array
    :param kernel_size: the size of the filter (must be odd)
    :return: the filtered image (same type as input image)
    """
    kernel = np.ones(kernelSize, np.float32)/kernelSize
    kd2 = kernelSize//2
    res = np.zeros(img.shape, np.float32)
    h, w = res.shape[:2] # pylint: disable=unsubscriptable-object
    # filter in y direction
    res[kd2:h-kd2, ...] = (img[kd2:h-kd2, ...]*kernel[kd2])
    for y in range(1, kd2+1):
        res[kd2:h-kd2, ...] += img[kd2-y:h-kd2-y, ...]*kernel[kd2-y] + img[kd2+y:h-kd2+y, ...]*kernel[kd2+y]
    # result becomes input now
    img = res.astype(img.dtype)
    res = np.zeros(img.shape, np.float32)
    # filter in x direction
    res[:, kd2:w-kd2, ...] = (img[:, kd2:w-kd2, ...]*kernel[kd2])
    for x in range(1, kd2+1):
        res[:, kd2:w-kd2, ...] += img[:, kd2-x:w-kd2-x, ...]*kernel[kd2-x] + img[:, kd2+x:w-kd2+x, ...]*kernel[kd2+x]
    res = res.astype(img.dtype)
    return res
