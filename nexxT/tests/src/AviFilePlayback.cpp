/* 
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

#include "AviFilePlayback.hpp"
#include "Services.hpp"
#include "PropertyCollection.hpp"
#include "Logger.hpp"
#include <QtCore/QDateTime>
#include <QtCore/QThread>
#include <QtCore/QBuffer>
#include <QtGui/QImageWriter>
#include <QtMultimedia/QAbstractVideoSurface>
#include <QtMultimedia/QVideoSurfaceFormat>

using namespace nexxT;

QImage qt_imageFromVideoFrame( const QVideoFrame& f );

class DummyVideoSurface : public QAbstractVideoSurface
{
    Q_OBJECT

signals:
    void newImage(const QImage &);
public:
    DummyVideoSurface(QObject *parent) : QAbstractVideoSurface(parent) {}
    virtual ~DummyVideoSurface()
    {
        qDebug("DummyVideoSurface::~DummyVideoSurface (qt message)");
    }


    QList<QVideoFrame::PixelFormat> supportedPixelFormats(QAbstractVideoBuffer::HandleType handleType) const
    {
        NEXT_LOG_DEBUG("QVideoSurfaceFormat::supportedPixelFormats called");

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

    bool isFormatSupported(const QVideoSurfaceFormat &format) const
    {
        NEXT_LOG_DEBUG("QVideoSurfaceFormat::isFormatSupported called");

        const QImage::Format imageFormat = QVideoFrame::imageFormatFromPixelFormat(format.pixelFormat());
        const QSize size = format.frameSize();

        return imageFormat != QImage::Format_Invalid
                && !size.isEmpty()
                && format.handleType() == QAbstractVideoBuffer::NoHandle;
    }

    bool start(const QVideoSurfaceFormat &format)
    {
        NEXT_LOG_DEBUG("QVideoSurfaceFormat::start called");

        QAbstractVideoSurface::start(format);
        return true;
    }

    void stop()
    {
        NEXT_LOG_DEBUG("QVideoSurfaceFormat::stop called");
        QAbstractVideoSurface::stop();
    }

    bool present(const QVideoFrame &_frame)
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

};

void VideoPlaybackDevice::openVideo()
{
    if( QThread::currentThread() != thread() )
    {
        throw std::runtime_error("unexpected thread.");
    }
    NEXT_LOG_DEBUG("entering openVideo");
    pauseOnStream = QString();
    player = new QMediaPlayer(this, QMediaPlayer::VideoSurface);
    player->setMuted(true);
    videoSurface = new DummyVideoSurface(this);
    connect(player, SIGNAL(durationChanged(qint64)),
            this, SLOT(newDuration(qint64)));
    connect(player, SIGNAL(positionChanged(qint64)),
            this, SLOT(newPosition(qint64)));
    connect(player, SIGNAL(currentMediaChanged(const QMediaContent &)),
            this, SLOT(currentMediaChanged(const QMediaContent &)));
    connect(videoSurface, SIGNAL(newImage(const QImage &)),
            this, SLOT(newImage(const QImage &)));
    connect(player, SIGNAL(error(QMediaPlayer::Error)),
            this, SLOT(mediaPlayerError(QMediaPlayer::Error)));
    connect(player, SIGNAL(stateChanged(QMediaPlayer::State)),
            this, SLOT(mediaPlayerStateChanged(QMediaPlayer::State)));
    connect(player, SIGNAL(playbackRateChanged(qreal)),
            this, SLOT(mediaPlayerPlaybackRateChanged(qreal)));
    player->setMedia(QUrl::fromLocalFile(filename));
    player->setVideoOutput(videoSurface);
    player->setPlaybackRate(playbackRate);
    player->pause();
    NEXT_LOG_DEBUG("leaving openVideo");
}

void VideoPlaybackDevice::closeVideo()
{
    NEXT_LOG_DEBUG("entering closeVideo");
    if(player)
    {
        delete player;
        player = nullptr;
    }
    if(videoSurface)
    {
        delete videoSurface;
        videoSurface = nullptr;
    }
    NEXT_LOG_INFO("emitting playback paused.");
    emit playbackPaused();
    NEXT_LOG_DEBUG("leaving closeVideo");
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

void VideoPlaybackDevice::newImage(const QImage &img)
{
    if(!pauseOnStream.isNull())
    {
        pauseOnStream = QString();
        QMetaObject::invokeMethod(this, "pausePlayback", Qt::QueuedConnection);
    }
    QByteArray a;
    {
        QBuffer b(&a);
        QImageWriter w;
        w.setFormat("png");
        w.setDevice(&b);
        if( !w.write(img) )
        {
            NEXT_LOG_ERROR(QString("Can't serialize image, %1").arg(w.errorString()));
        }
    }
    SharedDataSamplePtr newSample(new DataSample(a, "qimage", QDateTime::currentDateTime().toMSecsSinceEpoch()));
    video_out->transmit(newSample);
}

void VideoPlaybackDevice::mediaPlayerError(QMediaPlayer::Error)
{
    if(player) NEXT_LOG_WARN(QString("error from QMediaPlayer: %1").arg(player->errorString()));
}

void VideoPlaybackDevice::mediaPlayerStateChanged(QMediaPlayer::State newState)
{
    if(newState == QMediaPlayer::PlayingState)
    {
        emit playbackStarted();
    } else
    {
        NEXT_LOG_INFO("emitting playback paused.");
        emit playbackPaused();
    }
}

void VideoPlaybackDevice::mediaPlayerPlaybackRateChanged(qreal newRate)
{
    playbackRate = newRate;
    emit timeRatioChanged(newRate);
}

void VideoPlaybackDevice::newDuration(qint64 duration)
{
    NEXT_LOG_DEBUG(QString("newDuration %1").arg(duration));
    emit sequenceOpened(filename,
                        QDateTime::fromMSecsSinceEpoch(0, Qt::UTC),
                        QDateTime::fromMSecsSinceEpoch(duration, Qt::UTC),
                        QStringList() << "video");
}

void VideoPlaybackDevice::newPosition(qint64 position)
{
    emit currentTimestampChanged(QDateTime::fromMSecsSinceEpoch(position, Qt::UTC));
}

void VideoPlaybackDevice::currentMediaChanged(const QMediaContent &)
{
    NEXT_LOG_DEBUG("currentMediaChanged called");
}

void VideoPlaybackDevice::startPlayback()
{
    NEXT_LOG_DEBUG("startPlayback called");
    if(player) player->play();
}

void VideoPlaybackDevice::pausePlayback()
{
    NEXT_LOG_DEBUG("pausePlayback called");
    if(player) player->pause();
}

void VideoPlaybackDevice::stepForward(const QString &stream)
{
    NEXT_LOG_DEBUG(QString("stepForward(%1) called").arg(stream));
    pauseOnStream = "video";
    if( player && player->state() != QMediaPlayer::PlayingState )
    {
        NEXT_LOG_DEBUG("calling play");
        if(player) player->play();
    }
}

void VideoPlaybackDevice::seekBeginning()
{
    NEXT_LOG_DEBUG("seekBeginning called");
    if(player) player->setPosition(0);
}

void VideoPlaybackDevice::seekEnd()
{
    NEXT_LOG_DEBUG("seekEnd called");
    if(player) player->setPosition(player->duration()-1);
}

void VideoPlaybackDevice::seekTime(const QDateTime &pos)
{
    NEXT_LOG_DEBUG("seekTime called");
    if(player) player->setPosition(pos.toMSecsSinceEpoch());
}

void VideoPlaybackDevice::setSequence(const QString &_filename)
{
    NEXT_LOG_DEBUG("setSequence called");
    closeVideo();
    filename = _filename;
    openVideo();
}

void VideoPlaybackDevice::setTimeFactor(double factor)
{
    NEXT_LOG_DEBUG("setTimeFactor called");
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

#include "AviFilePlayback.moc"

