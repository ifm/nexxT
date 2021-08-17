/* 
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

#include "Ports.hpp"
#include "DataSamples.hpp"
#include "FilterEnvironment.hpp"
#include "Filters.hpp"
#include "Logger.hpp"
#include "Services.hpp"
#include "OutputPortInterface.hpp"
#include "InputPortInterface.hpp"
#include <atomic>

#include <QtCore/QThread>
#include <map>
#include <cstdio>

using namespace nexxT;

namespace nexxT
{
    struct PortD
    {
        bool dynamic;
        QString name;
        BaseFilterEnvironment *environment;
    };

    struct InterThreadConnectionD
    {
        QSemaphore semaphore;
        std::atomic_bool stopped;
        InterThreadConnectionD(int n) : semaphore(n), stopped(true) {}
    };

};

Port::Port(bool dynamic, const QString &name, BaseFilterEnvironment *env)
    : d(new PortD{dynamic, name, env})
{
    NEXXT_LOG_INTERNAL(QString("Port::Port %1").arg(uint64_t(this), 0, 16));
}

Port::~Port()
{
    NEXXT_LOG_INTERNAL(QString("Port::~Port %1").arg(uint64_t(this), 0, 16));
    delete d;
}

bool Port::dynamic() const
{
    return d->dynamic;
}

const QString &Port::name() const
{
    return d->name;
}

void Port::setName(const QString &name)
{
    d->name = name;
}

BaseFilterEnvironment *Port::environment() const
{
    return d->environment;
}

bool Port::isOutput() const
{
    return dynamic_cast<const OutputPortInterface*>(this) != 0;
}

bool Port::isInput() const
{
    return dynamic_cast<const InputPortInterface*>(this) != 0;
}

SharedPortPtr Port::make_shared(Port *port)
{
    return SharedPortPtr(port);
}

InterThreadConnection::InterThreadConnection(QThread *from_thread)
    : d(new InterThreadConnectionD(1))
{
    moveToThread(from_thread);
}

InterThreadConnection::~InterThreadConnection()
{
    delete d;
}

void InterThreadConnection::receiveSample(const QSharedPointer<const DataSample> &sample)
{
    while(true)
    {
        if( d->stopped.load() )
        {
            NEXXT_LOG_WARN("The inter-thread connection is set to stopped mode; data sample discarded.");
            break;
        }
        if( d->semaphore.tryAcquire(1, 500) )
        {
            emit transmitInterThread(sample, &d->semaphore);
            break;
        }
    }
}

void InterThreadConnection::setStopped(bool stopped)
{
    d->stopped.store(stopped);
}
