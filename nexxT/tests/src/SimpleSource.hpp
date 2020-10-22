/* 
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

#ifndef SIMPLE_SOURCE_HPP
#define SIMPLE_SOURCE_HPP

#include "NexxTPlugins.hpp"
#include <QtCore/QTimer>
#include <cstdint>

class SimpleSource : public nexxT::Filter
{
    Q_OBJECT

    QTimer timer;
    nexxT::SharedOutputPortPtr outPort;
    uint32_t counter;
public:
    SimpleSource(nexxT::BaseFilterEnvironment *env);
    virtual ~SimpleSource();

    virtual void onStart();
    virtual void onStop();

    NEXXT_PLUGIN_DECLARE_FILTER(SimpleSource)

private slots:
    virtual void newDataEvent();
};

#endif
