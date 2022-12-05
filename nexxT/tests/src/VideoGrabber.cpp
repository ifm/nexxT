/*
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */
#include "VideoGrabber.hpp"
#include "nexxT/Logger.hpp"
#include <QtGui/QImage>
#include <QtMultimedia/QVideoFrame>

using namespace nexxT;

VideoGrabber::VideoGrabber(QObject *parent) : QVideoSink(parent) {
    connect(this, SIGNAL(videoFrameChanged(const QVideoFrame &)),
            this, SLOT(videoFrameChanged(const QVideoFrame &)));
}

VideoGrabber::~VideoGrabber()
{
    NEXXT_LOG_INTERNAL("VideoGrabber::~VideoGrabber (qt message)");
}

void VideoGrabber::videoFrameChanged(const QVideoFrame &frame)
{
    NEXXT_LOG_DEBUG("new frame");
    QImage img = frame.toImage();
    emit newImage(img);
}