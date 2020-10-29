/*
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */
#include "VideoGrabber.hpp"
#include "Logger.hpp"

using namespace nexxT;

/* workaround for converting video frames to QImage, see https://forum.qt.io/post/376581 */
QImage qt_imageFromVideoFrame( const QVideoFrame& f );

VideoGrabber::VideoGrabber(QObject *parent) : QAbstractVideoSurface(parent) {}

VideoGrabber::~VideoGrabber()
{
    NEXXT_LOG_INTERNAL("VideoGrabber::~VideoGrabber (qt message)");
}


QList<QVideoFrame::PixelFormat> VideoGrabber::supportedPixelFormats(QAbstractVideoBuffer::HandleType handleType) const
{
    NEXXT_LOG_INTERNAL("QVideoSurfaceFormat::supportedPixelFormats called");

    Q_UNUSED(handleType);
    return QList<QVideoFrame::PixelFormat>()
        << QVideoFrame::Format_ARGB32
        << QVideoFrame::Format_ARGB32_Premultiplied
        << QVideoFrame::Format_RGB32
        << QVideoFrame::Format_RGB24
        << QVideoFrame::Format_RGB565
        << QVideoFrame::Format_RGB555
        << QVideoFrame::Format_ARGB8565_Premultiplied
        << QVideoFrame::Format_BGRA32
        << QVideoFrame::Format_BGRA32_Premultiplied
        << QVideoFrame::Format_BGR32
        << QVideoFrame::Format_BGR24
        << QVideoFrame::Format_BGR565
        << QVideoFrame::Format_BGR555
        << QVideoFrame::Format_BGRA5658_Premultiplied
        << QVideoFrame::Format_AYUV444
        << QVideoFrame::Format_AYUV444_Premultiplied
        << QVideoFrame::Format_YUV444
        << QVideoFrame::Format_YUV420P
        << QVideoFrame::Format_YV12
        << QVideoFrame::Format_UYVY
        << QVideoFrame::Format_YUYV
        << QVideoFrame::Format_NV12
        << QVideoFrame::Format_NV21
        << QVideoFrame::Format_IMC1
        << QVideoFrame::Format_IMC2
        << QVideoFrame::Format_IMC3
        << QVideoFrame::Format_IMC4
        << QVideoFrame::Format_Y8
        << QVideoFrame::Format_Y16
        << QVideoFrame::Format_Jpeg
        << QVideoFrame::Format_CameraRaw
        << QVideoFrame::Format_AdobeDng;
}

bool VideoGrabber::isFormatSupported(const QVideoSurfaceFormat &format) const
{
    NEXXT_LOG_INTERNAL("QVideoSurfaceFormat::isFormatSupported called");

    const QImage::Format imageFormat = QVideoFrame::imageFormatFromPixelFormat(format.pixelFormat());
    const QSize size = format.frameSize();

    return imageFormat != QImage::Format_Invalid
            && !size.isEmpty()
            && format.handleType() == QAbstractVideoBuffer::NoHandle;
}

bool VideoGrabber::start(const QVideoSurfaceFormat &format)
{
    NEXXT_LOG_INTERNAL("QVideoSurfaceFormat::start called");

    return QAbstractVideoSurface::start(format);
}

void VideoGrabber::stop()
{
    NEXXT_LOG_INTERNAL("QVideoSurfaceFormat::stop called");
    QAbstractVideoSurface::stop();
}

bool VideoGrabber::present(const QVideoFrame &_frame)
{
    QImage img = qt_imageFromVideoFrame(_frame);
    if(!img.isNull())
    {
        emit newImage(img);
        return true;
    } else
    {
        return false;
    }
}


