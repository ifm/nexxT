/*
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

#ifndef IMAGEFORMAT_H
#define IMAGEFORMAT_H

#include <stdint.h>

extern "C"
{
    /* see nexxT.examples.framework.ImageData */
    typedef struct ImageHeader
    {
        uint32_t width;
        uint32_t height;
        uint32_t lineInc;
        char format[32];
    } ImageHeader;
}

#endif // IMAGEFORMAT_H
