# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This is the image data type used in the example files. The image type is selected
for simplicty and for minimal external dependencies. In the C++ part of the API, the
the ImageHeader ctypes structure is mapped to a corresponding C structure.
nexxT itself only knows about QByteArray's for data transport, the contents must
be defined by the user.
"""

import ctypes as ct
import numpy as np
from PySide2.QtCore import QByteArray

# The supported image formats and the mapping to the number of channels and the numpy type.
# Note that QT's QImage natively only supports intensity_u8, intensity_u16 and rgb_u8 images.
ImageFormats = {
    "intensity_u8": (1, np.uint8),     # 1 channel, uint8_t
    "intensity_u16": (1, np.uint16),   # 1 channel, uint16_t
    "intensity_u32": (1, np.uint32),   # 1 channel, uint32_t
    "intensity_f32": (1, np.float32),  # 1 channel, float32_t
    "intensity_f64": (1, np.float64),  # 1 channel, float64_t
    "rgb_u8": (3, np.uint8),           # 3 channels RGB, uint8_t
    "rgb_u16": (3, np.uint16),         # 3 channels RGB, uint16_t
    "rgb_u32": (3, np.uint32),         # 3 channels RGB, uint32_t
    "rgb_f32": (3, np.float32),        # 3 channels RGB, float32_t
    "rgb_f64": (3, np.float64),        # 3 channels RGB, float64_t
    # ...
}

class ImageHeader(ct.Structure):
    """
    The QByteArray starts with this header and the rest of the array is the actual image data
    according to the format given here.
    """
    _fields_ = [("width", ct.c_uint32),    # the width in pixels
                ("height", ct.c_uint32),   # the height in pixels
                ("lineInc", ct.c_uint32),  # the number of bytes per line (including padding for alignment)
                ("format", ct.c_char*32),  # the image format as a c string. See above ImageFormats for a list.
               ]

def byteArrayToNumpy(qByteArray):
    """
    Interpret the input instance as an image and convert that to a numpy array. If the alignment is ok, then this
    operation is a zero-copy operation, otherwise one copy is made.

    :param qByteArray: a QByteArray instance
    :return: a numpy instance
    """
    # efficient zero-copy cast to a python memoryview instance
    mv = memoryview(qByteArray)
    # interpret the ImageHeader structure from this buffer (zero-copy)
    hdr = ImageHeader.from_buffer(mv)
    # convert the format bytes instance to a string
    fmt = hdr.format.decode()
    # sanity check
    if not fmt in ImageFormats:
        raise RuntimeError("Unknown image format %s" % fmt)
    # get number of channels and the numpy dtype of the target array
    numChannels, dtype = ImageFormats[hdr.format.decode()]
    # calculate the number of bytes per pixel
    bpp = dtype().nbytes*numChannels
    if hdr.lineInc % bpp != 0:
        # there is a non-convertable padding at the end of the lines, so we have to fix that
        # first interpret the image data as a numpy uint8 buffer (zero-copy)
        tmp = np.frombuffer(mv, dtype=np.uint8, offset=ct.sizeof(hdr))
        # reshape to 2D with with lineInc as width
        tmp = np.reshape(tmp, (-1, hdr.lineInc))
        # crop the non-aligned padding bytes from the image,
        tmp = tmp[:, :(hdr.lineInc//bpp)*bpp]
        # we have to create a copy here (the frombuffer call does not work on memoryview(tmp))
        mv = bytes(tmp)
    # create the target array
    res = np.frombuffer(mv, dtype=dtype, offset=ct.sizeof(hdr))
    # reshape to requested dimenstions
    return np.reshape(res, (-1, hdr.lineInc//bpp, numChannels))

def numpyToByteArray(img):
    """
    Convert a numpy image to the corresponding QByteArray (and make a copy).

    :param img: a numpy array instance with 2 or 3 dimensions
    :return: a QByteArray instance
    """
    # make sure that img is a contiguous array
    img = np.ascontiguousarray(img)
    # allocate the result
    res = QByteArray(img.nbytes + ct.sizeof(ImageHeader), 0)
    # create a memory view
    mv = memoryview(res)
    # map the header into this view
    hdr = ImageHeader.from_buffer(mv)
    hdr.width = img.shape[1]
    hdr.height = img.shape[0]
    hdr.lineInc = img[0, ...].nbytes
    # select the format
    if img.dtype is np.dtype(np.uint8):
        hdr.format = b"intensity_u8" if len(img.shape) < 3 else b"rgb_u8"
    if img.dtype is np.dtype(np.uint16):
        hdr.format = b"intensity_u16" if len(img.shape) < 3 else b"rgb_u16"
    if img.dtype is np.dtype(np.uint32):
        hdr.format = b"intensity_u32" if len(img.shape) < 3 else b"rgb_u32"
    if img.dtype is np.dtype(np.float32):
        hdr.format = b"intensity_f32" if len(img.shape) < 3 else b"rgb_f32"
    if img.dtype is np.dtype(np.float64):
        hdr.format = b"intensity_f64" if len(img.shape) < 3 else b"rgb_f64"
    # assert reasonable shape
    assert len(img.shape) == 2 or (len(img.shape) == 3 and img.shape[2] == 3)
    # map the image data into the view
    tmp = np.frombuffer(mv, img.dtype, offset=ct.sizeof(hdr))
    # assign the pixels
    tmp[...] = img.flatten()
    return res
