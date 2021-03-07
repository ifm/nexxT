/* 
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

#ifndef AVIFILEPLAYBACK_HPP
#define AVIFILEPLAYBACK_HPP

#include <QtCore/QObject>
#include <QtMultimedia/QMediaPlayer>
#include "VideoGrabber.hpp"
#include "Filters.hpp"
#include "Ports.hpp"
#include "NexxTPlugins.hpp"

using namespace nexxT;

class VideoPlaybackDevice : public Filter
{
    Q_OBJECT

    SharedOutputPortPtr video_out;
    QString filename;
    double playbackRate;
    QString pauseOnStream;
    QMediaPlayer *player;
    VideoGrabber *videoSurface;

    void openVideo();
    void closeVideo();

public:
    NEXXT_PLUGIN_DECLARE_FILTER(VideoPlaybackDevice)

    VideoPlaybackDevice(BaseFilterEnvironment *env);
    virtual ~VideoPlaybackDevice();

signals:
    void playbackStarted();
    void playbackPaused();
    void sequenceOpened(const QString &file,
                        const qint64 begin,
                        const qint64 end,
                        const QStringList &streams);
    void currentTimestampChanged(qint64);
    void timeRatioChanged(double);

public slots:
    void newImage(const QImage &img);
    void mediaPlayerError(QMediaPlayer::Error);
    void mediaPlayerStateChanged(QMediaPlayer::State newState);
    void mediaPlayerPlaybackRateChanged(qreal newRate);

    void newDuration(qint64 duration);
    void newPosition(qint64 position);
    void currentMediaChanged(const QMediaContent &);
    void startPlayback();
    void pausePlayback();
    void stepForward(const QString &stream);
    void seekBeginning();
    void seekEnd();
    void seekTime(qint64);
    void setSequence(const QString &_filename);
    void setTimeFactor(double factor);
protected:
    void onOpen();
    void onStart();
    void onStop();
    void onClose();

};

#endif // AVIFILEPLAYBACK_HPP
