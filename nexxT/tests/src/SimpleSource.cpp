/* 
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

#include "SimpleSource.hpp"
#include "PropertyCollection.hpp"
#include "DataSamples.hpp"
#include "Logger.hpp"
#include <chrono>

SimpleSource::SimpleSource(nexxT::BaseFilterEnvironment *env) : 
    nexxT::Filter(false, false, env),
    timer(),
    outPort(new nexxT::OutputPortInterface(false, "outPort", env)),
    counter(0)
{
    NEXXT_LOG_DEBUG("SimpleSource::SimpleSource");
    addStaticPort(outPort);
    propertyCollection()->defineProperty("frequency", double(1.0), "frequency of data generation [Hz]", {{"min", 0.01}});
    propertyCollection()->defineProperty("enumProp", "Hello", "an enum prop", {{"enum", QStringList{"Hello", "World"}}});
    connect(&timer, &QTimer::timeout, this, &SimpleSource::newDataEvent);
}

SimpleSource::~SimpleSource()
{
    NEXXT_LOG_DEBUG("SimpleSource::~SimpleSource");
}

void SimpleSource::onStart()
{
    int timeout_ms = int(1000. / propertyCollection()->getProperty("frequency").toDouble());
    timer.start(timeout_ms);
}

void SimpleSource::onStop()
{
    timer.stop();
}

void SimpleSource::newDataEvent()
{
    std::chrono::duration<double> t = std::chrono::high_resolution_clock::now().time_since_epoch();
    int64_t it = t.count() / nexxT::DataSample::TIMESTAMP_RES;
    counter++;
    QString c = QString("Sample %1").arg(counter);
    QSharedPointer<const nexxT::DataSample> s(new nexxT::DataSample(c.toUtf8(), "text/utf8", it));
    NEXXT_LOG_INFO(QString("Transmitting %1").arg(c));
    outPort->transmit(s);
}

