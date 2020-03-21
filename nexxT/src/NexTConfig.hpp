/* 
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

#ifndef NEXT_CONFIG_HPP
#define NEXT_CONFIG_HPP

//#define AVOID_NAMESPACE
#ifndef AVOID_NAMESPACE
    #define START_NAMESPACE namespace nexxT {
    #define STOP_NAMESPACE };
    #define USE_NAMESPACE using namespace nexxT;
#else
    #define START_NAMESPACE
    #define STOP_NAMESPACE
    #define USE_NAMESPACE
#endif

#include <QtCore/QSharedPointer>

#define NEXT_SHARED_PTR QSharedPointer

#endif
