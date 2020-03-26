/* 
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

#include "AviFilePlayback.hpp"
#include "SimpleSource.hpp"
#include "TestExceptionFilter.hpp"

NEXT_PLUGIN_DEFINE_START()
NEXT_PLUGIN_ADD_FILTER(SimpleSource)
NEXT_PLUGIN_ADD_FILTER(VideoPlaybackDevice)
NEXT_PLUGIN_ADD_FILTER(TestExceptionFilter)
NEXT_PLUGIN_DEFINE_FINISH()
