/*
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

#include "CameraGrabber.hpp"
#include "Logger.hpp"
#include <cstring>

using namespace nexxT;

CameraGrabber::CameraGrabber(BaseFilterEnvironment *env)
    : Filter(false, false, env)
    , camera()
    , videoSurface()
{
    video_out = SharedOutputPortPtr(new OutputPortInterface(false, "video_out", env));
    addStaticPort(video_out);
}

CameraGrabber::~CameraGrabber()
{
}

void CameraGrabber::newImage(const QImage &_img)
{
    QImage img = _img;
    ImageHeader hdr;
    QByteArray data;
    data.reserve(int(sizeof(ImageHeader)) + (img.height() * img.bytesPerLine()));
    QString format;
    switch(img.format())
    {
    case QImage::Format_RGB888:
        format = "rgb_u8";
        break;
    case QImage::Format_Grayscale8:
        format = "intensity_u8";
        break;
    case QImage::Format_Grayscale16:
        format = "intensity_u16";
        break;
    default:
        img = img.convertToFormat(QImage::Format_RGB888);
        format = "rgb_u8";
    }
    hdr.width = uint32_t(img.width());
    hdr.height = uint32_t(img.height());
    hdr.lineInc = uint32_t(img.bytesPerLine());
    std::strncpy(hdr.format, format.toLocal8Bit().constData(), sizeof(hdr.format));
    data = data.append((const char *)&hdr, sizeof(hdr));
    data = data.append((const char *)img.constBits(), hdr.lineInc*hdr.height);
    video_out->transmit(
         SharedDataSamplePtr(new DataSample(data, "example/image", DataSample::currentTime()))
    );
}

void CameraGrabber::onStateChanged(QCamera::State state)
{
    static bool recursive = false;
    if( camera->error() != QCamera::NoError && !recursive )
    {
        recursive = true;
        NEXXT_LOG_ERROR(QString("Error from QCamera: %1").arg(camera->errorString()));
        NEXXT_LOG_INFO("Trying to recover");
        camera->stop();
        camera->start();
        recursive = false;
    }
}

void CameraGrabber::onOpen()
{

    if(camera)
    {
        NEXXT_LOG_WARN("camera still allocated in onOpen");
        delete camera;
    }
    if(videoSurface)
    {
        NEXXT_LOG_WARN("videoSurface still allocated in onOpen");
        delete videoSurface;
    }
    camera = new QCamera(this);
    videoSurface = new VideoGrabber(this);
    QObject::connect(videoSurface, SIGNAL(newImage(const QImage &)), this, SLOT(newImage(const QImage &)));
    QObject::connect(camera, SIGNAL(stateChanged(QCamera::State)), this, SLOT(onStateChanged(QCamera::State)));
}

void CameraGrabber::onStart()
{
    camera->setCaptureMode(QCamera::CaptureVideo);
    camera->setViewfinder(videoSurface);
    camera->start();
}

void CameraGrabber::onStop()
{
    camera->stop();
}

void CameraGrabber::onClose()
{
    if(camera)
    {
        delete camera;
        camera = nullptr;
    }
    if(videoSurface)
    {
        delete videoSurface;
        videoSurface = nullptr;
    }
}


