# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This module defines the nexxT interface class DataSample.
"""
import time
from PySide2.QtCore import QByteArray

class DataSample:
    """
    .. note::
        Import this class with :code:`from nexxT.interface import DataSample`.

    This class is used for storing a data sample of the nexxT framework. For most generic usage, a QByteArray is used
    for the storage. This means that deserialization has to be performed on every usage and data generators need to
    serialize the data. Assumes that serializing / deserializing are efficient operations.

    DataSample instances additionally have a type, which is a string and it should uniquely define the serialization
    method. Last but not least, an integer timestamp is stored for all DataSample instances.

    .. note::
        Usually, nexxT is using the wrapped C++ class instead of the python version. In python there are no
        differences between the wrapped C++ class and this python class. The C++ interface is defined in
        :cpp:class:`nexxT::DataSample`
    """

    TIMESTAMP_RES = 1e-6
    """the resolution of the timestamps"""

    def __init__(self, content, datatype, timestamp):
        """
        Create a new data sample instance.

        :param content: A QByteArray instance containing the (serialized) content
        :param datatype: A string instance which uniquely defines the serialized content
        :param timestamp: An integer representing the sample's time stamp [µs]
        """
        self._content = QByteArray(content)
        self._timestamp = timestamp
        self._type = datatype
        self._transmitted = False

    def getContent(self):
        """
        Get the contents of this sample as a QByteArray. Note that this is an efficient operation due to the copy on
        write semantics of QByteArray. It also asserts that the original contents cannot be modified.

        :return: QByteArray instance copy
        """
        return QByteArray(self._content)

    def getTimestamp(self):
        """
        Return the timestamp associated to the data.

        :return: integer timestamp
        """
        return self._timestamp

    def getDatatype(self):
        """
        Return the data type.

        :return: data type string
        """
        return self._type

    @staticmethod
    def copy(src):
        """
        Create a copy of this DataSample instance

        :param src: the instance to be copied
        :return: the cloned data sample
        """
        return DataSample(src.getContent(), src.getDatatype(), src.getTimestamp())

    @staticmethod
    def currentTime():
        """
        Returns the current system time suitable for data sample timestamps.
        Note: The python implementation uses time.time_ns, which unfortunately has
        limited accuracy under windows (16 ms).

        :return: an integer instance
        """
        factor = round(DataSample.TIMESTAMP_RES / 1e-9)
        return time.time_ns() // factor
