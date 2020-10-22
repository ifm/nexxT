/* 
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

#define QT_ANNOTATE_ACCESS_SPECIFIER(a) __attribute__((annotate(#a)))

#include "DataSamples.hpp"
#include "Ports.hpp"
#include "Filters.hpp"
#include "FilterEnvironment.hpp"
#include "Services.hpp"
#include "PropertyCollection.hpp"
#include "NexxTPlugins.hpp"
#include "Logger.hpp"
