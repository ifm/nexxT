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
#include "Executor.hpp"
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

    struct PortToPortConnectionD
    {
        QSemaphore semaphore;
        std::atomic_bool stopped;
        SharedExecutorPtr executorFrom;
        SharedExecutorPtr executorTo;
        SharedOutputPortPtr portFrom;
        SharedInputPortPtr portTo;
        PortToPortConnectionD(int n,
                               const SharedExecutorPtr &_executorFrom,
                               const SharedExecutorPtr &_executorTo,
                               const SharedOutputPortPtr &_portFrom,
                               const SharedInputPortPtr &_portTo)
            : semaphore(n)
            , stopped(true)
            , executorFrom(_executorFrom)
            , executorTo(_executorTo)
            , portFrom(_portFrom)
            , portTo(_portTo)
            {}
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

PortToPortConnection::PortToPortConnection(const SharedExecutorPtr &executorFrom,
                                           const SharedExecutorPtr &executorTo,
                                           const SharedOutputPortPtr &portFrom,
                                           const SharedInputPortPtr &portTo)
    : d(new PortToPortConnectionD(1, executorFrom, executorTo, portFrom, portTo))
{
}

PortToPortConnection::~PortToPortConnection()
{
    delete d;
}

void PortToPortConnection::receiveSample(const QSharedPointer<const DataSample> &sample)
{
    if( d->executorFrom.get() == d->executorTo.get() )
    {
        d->executorTo->registerPendingRcvSync(d->portTo, sample);
    } else
    {
        int32_t timeoutMS = 0;
        while(true)
        {
            if( d->stopped.load() )
            {
                NEXXT_LOG_WARN("The inter-thread connection is set to stopped mode; data sample discarded.");
                break;
            }
            if( !d->semaphore.tryAcquire(1, timeoutMS) )
            {
                if( d->executorFrom->step(d->portFrom->environment()->getPlugin()) )
                {
                    timeoutMS = 0;
                } else
                {
                    timeoutMS = 10;
                }
            } else
            {
                d->executorTo->registerPendingRcvAsync(d->portTo, sample, &d->semaphore);
                break;
            }
        }
    }
}

void PortToPortConnection::setStopped(bool stopped)
{
    d->stopped.store(stopped);
}