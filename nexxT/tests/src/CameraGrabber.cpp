/*
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

#include "CameraGrabber.hpp"
#include "nexxT/Logger.hpp"
#include "nexxT/PropertyCollection.hpp"
#include <QtMultimedia/QCameraDevice>
#include <QtMultimedia/QMediaDevices>
#include <cstring>

using namespace nexxT;

// LITERAL_INCLUDE_START_1
CameraGrabber::CameraGrabber(BaseFilterEnvironment *env)
    : Filter(false, false, env)
    , camera()
    , videoSurface()
    , session()
{
    /* similar to the python API, we create an output port for transmitting images */
    video_out = SharedOutputPortPtr(new OutputPortInterface(false, "video_out", env));
    /* and register that port */
    addStaticPort(video_out);
    /* note that we do not connect to the hardware in the constructor, this is to be
     * done later in onOpen(...) for efficiency reasons.
     */
    PropertyCollection *pc = propertyCollection();
    QStringList devices;
    for (const QCameraDevice &cameraDevice : QMediaDevices::videoInputs())
    {
        devices.push_back(cameraDevice.description());
    }
    if(devices.size() == 0)
    {
        devices.push_back("dummy");
    }
    pc->defineProperty("device", devices[0], "the camera device", {{"enum", devices}});
}

CameraGrabber::~CameraGrabber()
{
}
// LITERAL_INCLUDE_END_1

// LITERAL_INCLUDE_START_2
/* A new image has arrived, we convert this here to a QByteArray
 * Note that QT takes care to call this method in the correct thread
 * due to the QueuedConnection mechanism.
 */
void CameraGrabber::newImage(const QImage &_img)
{
    QImage img = _img; /* we need a writable img */
    ImageHeader hdr;
    QByteArray data;
    /* reserve size for the image in the QByteArray for efficiency reasons */
    data.reserve(int(sizeof(ImageHeader)) + (img.height() * img.bytesPerLine()));
    /* determine the format */
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
        /* for all other formats, we create an rgb_u8 image using QImage functionality */
        img = img.convertToFormat(QImage::Format_RGB888);
        format = "rgb_u8";
    }
    /* fill the header fields */
    hdr.width = uint32_t(img.width());
    hdr.height = uint32_t(img.height());
    hdr.lineInc = uint32_t(img.bytesPerLine());
    std::strncpy(hdr.format, format.toLocal8Bit().constData(), sizeof(hdr.format)-1);
    /* fill the QByteArray instance */
    data = data.append((const char *)&hdr, sizeof(hdr));
    data = data.append((const char *)img.constBits(), hdr.lineInc*hdr.height);
    /* transmit over the port */
    video_out->transmit(
         SharedDataSamplePtr(new DataSample(data, "example/image", DataSample::currentTime()))
    );
}
// LITERAL_INCLUDE_END_2

/* in case of an error, we restart the camera stream */
void CameraGrabber::onErrorOccurred(QCamera::Error error, const QString &errString)
{
    static bool recursive = false;
    if( error != QCamera::NoError && !recursive )
    {
        recursive = true;
        NEXXT_LOG_ERROR(QString("Error from QCamera: %1").arg(errString));
        NEXXT_LOG_INFO("Trying to recover");
        camera->stop();
        camera->start();
        recursive = false;
    }
}

// LITERAL_INCLUDE_START_3
/* here we connect to the hardware */
void CameraGrabber::onOpen()
{
    if(videoSurface)
    {
        NEXXT_LOG_WARN("videoSurface still allocated in onOpen");
        delete videoSurface;
        videoSurface = 0;
    }
    if(camera)
    {
        NEXXT_LOG_WARN("camera still allocated in onOpen");
        delete camera;
        camera = 0;
    }
    if(session)
    {
        NEXXT_LOG_WARN("session still allocated in onOpen");
        delete session;
        session = 0;
    }
    /* create a QCamera and a VideoGrabber instance, the camera will run in a default mode
     * All these objects run in the same thread as this filter.
     */
    PropertyCollection *pc = propertyCollection();
    QString devname = pc->getProperty("device").value<QString>();
    for (const QCameraDevice &cameraDevice : QMediaDevices::videoInputs())
    {
        if( cameraDevice.description() == devname )
        {
            camera = new QCamera(cameraDevice, this);
            break;
        }
    }
    session = new QMediaCaptureSession(this);
    if(!camera)
    {
        NEXXT_LOG_WARN("Using default camera.");
        camera = new QCamera(this);
    }
    videoSurface = new VideoGrabber(this);
    session->setCamera(camera);
    session->setVideoOutput(videoSurface);
    /* make up signal/slot connections */
    QObject::connect(videoSurface, SIGNAL(newImage(const QImage &)), this, SLOT(newImage(const QImage &)));
    QObject::connect(camera, SIGNAL(errorOccurred(QCamera::Error, const QString &)),
                     this, SLOT(onErrorOccurred(QCamera::Error, const QString &)));
}

/* at that point, the streaming shall be started */
void CameraGrabber::onStart()
{
    camera->start();
}

/* inverse of onStart(...) */
void CameraGrabber::onStop()
{
    camera->stop();
}

/* inverse of onOpen(...) */
void CameraGrabber::onClose()
{
    if(videoSurface)
    {
        delete videoSurface;
        videoSurface = nullptr;
    }
    if(camera)
    {
        delete camera;
        camera = nullptr;
    }
    if(session)
    {
        delete session;
        session = nullptr;
    }
}
// LITERAL_INCLUDE_END_3
