/* 
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

#include "Filters.hpp"
#include "FilterEnvironment.hpp"
#include "Ports.hpp"
#include "Logger.hpp"

using namespace nexxT;

// we need these on linux for some reason
const int FilterState::CONSTRUCTING;
const int FilterState::CONSTRUCTED;
const int FilterState::INITIALIZING;
const int FilterState::INITIALIZED;
const int FilterState::OPENING;
const int FilterState::OPENED;
const int FilterState::STARTING;
const int FilterState::ACTIVE;
const int FilterState::STOPPING;
const int FilterState::CLOSING;
const int FilterState::DEINITIALIZING;
const int FilterState::DESTRUCTING;
const int FilterState::DESTRUCTED;

QString FilterState::state2str(int state)
{
    switch (state)
    {
    case FilterState::CONSTRUCTING: return "CONSTRUCTING";
    case FilterState::CONSTRUCTED: return "CONSTRUCTED";
    case FilterState::INITIALIZING: return "INITIALIZING";
    case FilterState::INITIALIZED: return "INITIALIZED";
    case FilterState::OPENING: return "OPENING";
    case FilterState::OPENED: return "OPENED";
    case FilterState::STARTING: return "STARTING";
    case FilterState::ACTIVE: return "ACTIVE";
    case FilterState::STOPPING: return "STOPPING";
    case FilterState::CLOSING: return "CLOSING";
    case FilterState::DEINITIALIZING: return "DEINITIALIZING";
    case FilterState::DESTRUCTING: return "DESTRUCTING";
    case FilterState::DESTRUCTED: return "DESTRUCTED";
    default:
        throw(std::runtime_error("Unknown state"));
    }
}

namespace nexxT
{
    struct FilterD 
    {
        BaseFilterEnvironment *environment;
    };
};

Filter::Filter(bool dynInPortsSupported, bool dynOutPortsSupported, BaseFilterEnvironment *environment)
    : d(new FilterD{environment})
{
    NEXXT_LOG_INTERNAL("Filter::Filter");
    d->environment->setDynamicPortsSupported(dynInPortsSupported, dynOutPortsSupported);
}

Filter::~Filter()
{
    NEXXT_LOG_INTERNAL(QString("Filter::~Filter: ") + objectName());
    delete d;
}

PropertyCollection *Filter::propertyCollection()
{
    return d->environment->propertyCollection();
}

PropertyCollection *Filter::guiState()
{
    return d->environment->guiState();
}

void Filter::addStaticPort(const SharedPortPtr &port)
{
    if( port->dynamic() )
    {
        throw std::runtime_error("The given port should be static but is dynamic.");
    }
    d->environment->addPort(port);
}

SharedPortPtr Filter::addStaticOutputPort(const QString &name)
{
    SharedPortPtr port = SharedPortPtr(new OutputPortInterface(false, name, environment()));
    addStaticPort(port);
    return port;
}

SharedPortPtr Filter::addStaticInputPort(const QString &name, int queueSizeSamples, double queueSizeSeconds)
{
    SharedPortPtr port = SharedPortPtr(new InputPortInterface(false, name, environment(), queueSizeSamples, queueSizeSeconds));
    addStaticPort(port);
    return port;
}

void Filter::removeStaticPort(const SharedPortPtr &port)
{
    if( port->dynamic() )
    {
        throw std::runtime_error("The given port should be static but is dynamic.");
    }
    d->environment->removePort(port);
}

PortList Filter::getDynamicInputPorts()
{
    return d->environment->getDynamicInputPorts();
}

PortList Filter::getDynamicOutputPorts()
{
    return d->environment->getDynamicOutputPorts();
}

void Filter::onInit()
{
    /* intentionally empty */
}

void Filter::onOpen()
{
    /* intentionally empty */
}

void Filter::onStart()
{
    /* intentionally empty */
}

void Filter::onPortDataChanged(const InputPortInterface &)
{
    /* intentionally empty */
}

void Filter::onStop()
{
    /* intentionally empty */
}

void Filter::onClose()
{
    /* intentionally empty */
}

void Filter::onDeinit()
{
    /* intentionally empty */
}

QList<QList<QString> > Filter::onSuggestDynamicPorts()
{
    QList<QString> inputPorts;
    QList<QString> outputPorts;
    return {inputPorts, outputPorts};
}


BaseFilterEnvironment *Filter::environment() const
{
    return d->environment;
}

 SharedFilterPtr Filter::make_shared(Filter *filter)
 {
     return SharedFilterPtr(filter);
 }
