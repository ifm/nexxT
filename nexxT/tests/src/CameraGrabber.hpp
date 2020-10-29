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

/* This class implements a Grabber for USB camera images using the
 * QtMultimedia framework. Note that this is not really the ideal
 * choice because of some known bugs, but it helps to keep dependencies
 * small. Note that C++ has been chosen here because of two reasons.
 * First to show how to write a nexxT filter in C++, and second,
 * because the PySide2 bindings of QCamera and QAbstractVideoSurface
 * do not allow to do this in python.
 */
class CameraGrabber : public Filter
{
    Q_OBJECT

    /* the port where the data will be transmitted to */
    SharedOutputPortPtr video_out;
    /* the camera instance (created at onOpen(...)) */
    QCamera *camera;
    /* the video surface needed to actually grab QImages from the QCamera */
    VideoGrabber *videoSurface;

public:
    /* The following line is needed to declare a nexxT plugin. Note that also the following
     * is needed in a cpp file:
     *
     * NEXXT_PLUGIN_DEFINE_START()
     * NEXXT_PLUGIN_ADD_FILTER(CameraGrabber)
     * // more filters can be added
     * NEXXT_PLUGIN_DEFINE_FINISH()
     *
     */
    NEXXT_PLUGIN_DECLARE_FILTER(CameraGrabber)

    /* Constructor with standard arguments */
    CameraGrabber(BaseFilterEnvironment *env);
    /* destructor */
    virtual ~CameraGrabber();

public slots:
    /* Slot called from the videoSurface instance when a new image arrives */
    void newImage(const QImage &img);
    /* Slot called by the QtMultimedia framework to detect errors (they will happen!) */
    void onStateChanged(QCamera::State state);

protected: // folowing functions are overloaded from the nexxT::Filter API
    void onOpen();
    void onStart();
    void onStop();
    void onClose();
};

#endif
