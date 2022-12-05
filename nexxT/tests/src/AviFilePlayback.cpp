/* 
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

#include "AviFilePlayback.hpp"
#include "nexxT/Services.hpp"
#include "nexxT/PropertyCollection.hpp"
#include "nexxT/Logger.hpp"
#include "ImageFormat.h"
#include <QtCore/QThread>
#include <QtCore/QBuffer>
#include <QtGui/QImageWriter>
#include <cstring>

using namespace nexxT;

void VideoPlaybackDevice::openVideo()
{
    if( QThread::currentThread() != thread() )
    {
        throw std::runtime_error("unexpected thread.");
    }
    NEXXT_LOG_DEBUG("entering openVideo");
    pauseOnStream = QString();
    player = new QMediaPlayer(this);
    videoSurface = new VideoGrabber(this);
    connect(player, SIGNAL(durationChanged(qint64)),
            this, SLOT(newDuration(qint64)));
    connect(player, SIGNAL(positionChanged(qint64)),
            this, SLOT(newPosition(qint64)));
    connect(player, SIGNAL(sourceChanged(const QUrl &)),
            this, SLOT(currentMediaChanged(const QUrl &)));
    connect(videoSurface, SIGNAL(newImage(const QImage &)),
            this, SLOT(newImage(const QImage &)));
    connect(player, SIGNAL(errorOccurred(QMediaPlayer::Error, const QString &)),
            this, SLOT(mediaPlayerError(QMediaPlayer::Error, const QString &)));
    connect(player, SIGNAL(playbackStateChanged(QMediaPlayer::PlaybackState)),
            this, SLOT(mediaPlayerStateChanged(QMediaPlayer::PlaybackState)));
    connect(player, SIGNAL(playbackRateChanged(qreal)),
            this, SLOT(mediaPlayerPlaybackRateChanged(qreal)));
    player->setSource(QUrl::fromLocalFile(filename));
    player->setVideoOutput(videoSurface);
    player->setAudioOutput(0);
    player->setPlaybackRate(playbackRate);
    player->pause();
    NEXXT_LOG_DEBUG("leaving openVideo");
}

void VideoPlaybackDevice::closeVideo()
{
    NEXXT_LOG_INFO("entering closeVideo");
    NEXXT_LOG_INFO("emitting playback paused.");
    emit playbackPaused();
    if(videoSurface)
    {
        videoSurface->deleteLater();
        videoSurface = nullptr;
    }
    if(player)
    {
        player->stop();
        player->deleteLater();
        player = nullptr;
    }
    NEXXT_LOG_INFO("leaving closeVideo");
}

VideoPlaybackDevice::VideoPlaybackDevice(BaseFilterEnvironment *env) :
    Filter(false, false, env),
    player(nullptr),
    videoSurface(nullptr)
{
    pauseOnStream = QString();
    playbackRate = 1.0;
    video_out = SharedOutputPortPtr(new OutputPortInterface(false, "video_out", env));
    addStaticPort(video_out);
}

VideoPlaybackDevice::~VideoPlaybackDevice()
{
    closeVideo();
}

void VideoPlaybackDevice::newImage(const QImage &_img)
{
    if(!pauseOnStream.isNull())
    {
        pauseOnStream = QString();
        QMetaObject::invokeMethod(this, "pausePlayback", Qt::QueuedConnection);
    }
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

void VideoPlaybackDevice::mediaPlayerError(QMediaPlayer::Error, const QString &msg)
{
    if(player) NEXXT_LOG_WARN(QString("error from QMediaPlayer: %1").arg(msg));
}

void VideoPlaybackDevice::mediaPlayerStateChanged(QMediaPlayer::PlaybackState newState)
{
    if(newState == QMediaPlayer::PlayingState)
    {
        NEXXT_LOG_INFO("emitting playback started.");
        emit playbackStarted();
    } else if(newState == QMediaPlayer::PausedState)
    {
        NEXXT_LOG_INFO("emitting playback paused.");
        emit playbackPaused();
    } else
    {
        NEXXT_LOG_INFO("unknown state.");
    }
}

void VideoPlaybackDevice::mediaPlayerPlaybackRateChanged(qreal newRate)
{
    playbackRate = newRate;
    emit timeRatioChanged(newRate);
}

void VideoPlaybackDevice::newDuration(qint64 duration)
{
    NEXXT_LOG_DEBUG(QString("newDuration %1").arg(duration));
    emit sequenceOpened(filename,
                        0,
                        duration*1000000,
                        QStringList() << "video");
}

void VideoPlaybackDevice::newPosition(qint64 position)
{
    emit currentTimestampChanged(position*1000000);
}

void VideoPlaybackDevice::currentMediaChanged(const QUrl &)
{
    NEXXT_LOG_DEBUG("currentMediaChanged called");
}

void VideoPlaybackDevice::startPlayback()
{
    NEXXT_LOG_DEBUG("startPlayback called");
    if(player) player->play();
}

void VideoPlaybackDevice::pausePlayback()
{
    NEXXT_LOG_DEBUG("pausePlayback called");
    if(player) player->pause();
}

void VideoPlaybackDevice::stepForward(const QString &stream)
{
    NEXXT_LOG_DEBUG(QString("stepForward(%1) called").arg(stream));
    pauseOnStream = "video";
    if( player && player->playbackState() != QMediaPlayer::PlayingState )
    {
        NEXXT_LOG_DEBUG("calling play");
        if(player) player->play();
    }
}

void VideoPlaybackDevice::seekBeginning()
{
    NEXXT_LOG_DEBUG("seekBeginning called");
    if(player) player->setPosition(0);
}

void VideoPlaybackDevice::seekEnd()
{
    NEXXT_LOG_DEBUG("seekEnd called");
    if(player) player->setPosition(player->duration()-1);
}

void VideoPlaybackDevice::seekTime(qint64 pos)
{
    NEXXT_LOG_DEBUG("seekTime called");
    if(player) player->setPosition(pos / 1000000);
}

void VideoPlaybackDevice::setSequence(const QString &_filename)
{
    NEXXT_LOG_DEBUG(QString("setSequence called filename=%1").arg(_filename));
    closeVideo();
    filename = _filename;
    openVideo();
}

void VideoPlaybackDevice::setTimeFactor(double factor)
{
    NEXXT_LOG_DEBUG("setTimeFactor called");
    if(player) player->setPlaybackRate(factor);
}

void VideoPlaybackDevice::onOpen()
{
    QStringList filters;
    filters << "*.avi" << "*.mp4" << "*.wmv";
    SharedQObjectPtr ctrlSrv = Services::getService("PlaybackControl");
    QMetaObject::invokeMethod(ctrlSrv.data(),
                              "setupConnections",
                              Qt::DirectConnection,
                              Q_ARG(QObject*, this),
                              Q_ARG(const QStringList &, filters));
}

void VideoPlaybackDevice::onStart()
{
    openVideo();
}

void VideoPlaybackDevice::onStop()
{
    closeVideo();
}

void VideoPlaybackDevice::onClose()
{
    SharedQObjectPtr ctrlSrv = Services::getService("PlaybackControl");
    QMetaObject::invokeMethod(ctrlSrv.data(),
                              "removeConnections",
                              Qt::DirectConnection,
                              Q_ARG(QObject*,this));
}
