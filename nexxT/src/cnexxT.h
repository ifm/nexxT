/* 
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

#define QT_ANNOTATE_ACCESS_SPECIFIER(a) __attribute__((annotate(#a)))

#include "nexxT/DataSamples.hpp"
#include "nexxT/Ports.hpp"
#include "nexxT/OutputPortInterface.hpp"
#include "nexxT/InputPortInterface.hpp"
#include "nexxT/Filters.hpp"
#include "nexxT/FilterEnvironment.hpp"
#include "nexxT/Services.hpp"
#include "nexxT/PropertyCollection.hpp"
#include "nexxT/NexxTPlugins.hpp"
#include "nexxT/Logger.hpp"
#include "nexxT/SharedPointerTypes.hpp"
#include "nexxT/Compatibility.hpp"
