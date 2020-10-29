/*
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

#ifndef CAMERA_GRABBER_HPP
#define CAMERA_GRABBER_HPP

#include <QtCore/QObject>
#include <QtMultimedia/QCamera>
#include "VideoGrabber.hpp"
#include "Filters.hpp"
#include "Ports.hpp"
#include "NexxTPlugins.hpp"
#include "ImageFormat.h"

using namespace nexxT;

class CameraGrabber : public Filter
{
    Q_OBJECT

    SharedOutputPortPtr video_out;
    QCamera *camera;
    VideoGrabber *videoSurface;

public:
    NEXXT_PLUGIN_DECLARE_FILTER(CameraGrabber)

    CameraGrabber(BaseFilterEnvironment *env);
    virtual ~CameraGrabber();

public slots:
    void newImage(const QImage &img);
    void onStateChanged(QCamera::State state);

protected:
    void onOpen();
    void onStart();
    void onStop();
    void onClose();
};

#endif
