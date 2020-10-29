/* 
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

#include "AviFilePlayback.hpp"
#include "CameraGrabber.hpp"
#include "SimpleSource.hpp"
#include "TestExceptionFilter.hpp"

NEXXT_PLUGIN_DEFINE_START()
NEXXT_PLUGIN_ADD_FILTER(VideoPlaybackDevice)
NEXXT_PLUGIN_ADD_FILTER(CameraGrabber)
NEXXT_PLUGIN_ADD_FILTER(SimpleSource)
NEXXT_PLUGIN_ADD_FILTER(TestExceptionFilter)
NEXXT_PLUGIN_DEFINE_FINISH()
