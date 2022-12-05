/*
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

#ifndef NEXXT_VIDEO_GRABBER_HPP
#define NEXXT_VIDEO_GRABBER_HPP

#include <QtCore/QObject>
#include <QtMultimedia/QVideoSink>
#include "nexxT/NexxTLinkage.hpp"

/* It would be lovely to do this stuff in python, but atm the binding is broken in PySide2
   See https://bugreports.qt.io/browse/PYSIDE-794
*/
class VideoGrabber : public QVideoSink
{
    Q_OBJECT

signals:
    void newImage(const QImage &);
private slots:
    void videoFrameChanged(const QVideoFrame &);
public:
    VideoGrabber(QObject *parent);
    virtual ~VideoGrabber();
};

#endif
