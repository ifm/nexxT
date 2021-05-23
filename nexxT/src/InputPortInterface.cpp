/* 
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

#include "InputPortInterface.hpp"
#include "DataSamples.hpp"
#include "FilterEnvironment.hpp"
#include "Filters.hpp"
#include "Logger.hpp"
#include "Services.hpp"
#include "Logger.hpp"
#include <atomic>

#include <QtCore/QThread>
#include <map>
#include <cstdio>

using namespace nexxT;

namespace nexxT
{
    struct InputPortD
    {
        int queueSizeSamples;
        double queueSizeSeconds;
        bool interthreadDynamicQueue;
        QList<SharedDataSamplePtr> queue;
        std::map<QSemaphore*, uint32_t> semaphoreN;
        SharedQObjectPtr srvprof;
        QString profname;
    };
};

InputPortInterface::InputPortInterface(bool dynamic, const QString &name, BaseFilterEnvironment *env, int queueSizeSamples, double queueSizeSeconds) :
    Port(dynamic, name, env),
    d(new InputPortD{queueSizeSamples, queueSizeSeconds, false})
{
    d->srvprof = Services::getService("Profiling");
    d->profname = QString();
    setQueueSize(queueSizeSamples, queueSizeSeconds);
}

InputPortInterface::~InputPortInterface()
{
    delete d;
}

SharedDataSamplePtr InputPortInterface::getData(int delaySamples, double delaySeconds) const
{
    if( QThread::currentThread() != thread() )
    {
        throw std::runtime_error("InputPort.getData has been called from an unexpected thread.");
    }
    if( delaySamples >= 0 && delaySeconds >= 0. )
    {
        throw std::runtime_error("Both delaySamples and delaySecons are positive");
    }
    if( delaySamples >= 0 )
    {
        if( delaySamples >= d->queue.size() )
        {
            throw std::out_of_range("delaySamples is out of range.");
        }
        return d->queue[delaySamples];
    }
    if( delaySeconds >= 0. )
    {
        double delayTime = delaySeconds / (double)DataSample::TIMESTAMP_RES;
        int i;
        for(i = 0; (i < d->queue.size()) && (double(d->queue[0]->getTimestamp() - d->queue[i]->getTimestamp()) < delayTime); i++)
        {
        }
        if( i >= d->queue.size() )
        {
            throw std::out_of_range("delaySeconds is out of range.");
        }
        return d->queue[i];
    }
    throw std::runtime_error("Both delaySamples and delaySeconds are negative");
} 

void InputPortInterface::setQueueSize(int queueSizeSamples, double queueSizeSeconds)
{
    if(queueSizeSamples <= 0 && queueSizeSeconds <= 0.0)
    {
        NEXXT_LOG_WARN(QString("Warning: infinite buffering used for port \"%1\". "
                               "Using a one sample sized queue instead.").arg(name()));
        queueSizeSamples = 1;
    }
    d->queueSizeSamples = queueSizeSamples;
    d->queueSizeSeconds = queueSizeSeconds;
}

int InputPortInterface::queueSizeSamples()
{
    return d->queueSizeSamples;
}

double InputPortInterface::queueSizeSeconds()
{
    return d->queueSizeSeconds;
}

void InputPortInterface::setInterthreadDynamicQueue(bool enabled)
{
    if(enabled != d->interthreadDynamicQueue)
    {
        switch(environment()->state())
        {
        case FilterState::CONSTRUCTING:
        case FilterState::CONSTRUCTED:
        case FilterState::INITIALIZING:
        case FilterState::INITIALIZED:
            d->interthreadDynamicQueue = enabled;
            break;
        default:
            NEXXT_LOG_ERROR(QString("Cannot change the interthreadDynamicQueue setting in state %1.").arg(
                             FilterState::state2str(environment()->state())));
        }
    }
}

bool InputPortInterface::interthreadDynamicQueue()
{
    return d->interthreadDynamicQueue;
}

SharedPortPtr InputPortInterface::clone(BaseFilterEnvironment*env) const
{
    return SharedPortPtr(new InputPortInterface(dynamic(), name(), env, d->queueSizeSamples, d->queueSizeSeconds));
}

void InputPortInterface::addToQueue(const SharedDataSamplePtr &sample)
{
    d->queue.prepend(sample);
    if(d->queueSizeSamples > 0)
    {
        while(d->queue.size() > d->queueSizeSamples)
        {
            d->queue.removeLast();
        }
    }
    if(d->queueSizeSeconds > 0)
    {
        double queueSizeTime = d->queueSizeSeconds / (double)DataSample::TIMESTAMP_RES;
        while( d->queue.size() > 0 && (double(d->queue.first()->getTimestamp() - d->queue.last()->getTimestamp()) > queueSizeTime) )
        {
            d->queue.removeLast();
        }
    }
}

void InputPortInterface::transmit()
{
    if(d->srvprof.data())
    {
        if( d->profname.isNull())
        {
            d->profname = environment()->getFullQualifiedName() + "/" + name();
        }
        QMetaObject::invokeMethod(d->srvprof.data(), "beforePortDataChanged", Qt::DirectConnection,
                                  Q_ARG(QString, d->profname));
    }
    environment()->portDataChanged(*this);
    if(d->srvprof.data())
    {
        QMetaObject::invokeMethod(d->srvprof.data(), "afterPortDataChanged", Qt::DirectConnection,
                                  Q_ARG(QString, d->profname));
    }
}

void InputPortInterface::receiveAsync(const QSharedPointer<const DataSample> &sample, QSemaphore *semaphore)
{
    try
    {
        if( QThread::currentThread() != thread() )
        {
            throw std::runtime_error("InputPort.getData has been called from an unexpected thread.");
        }
        addToQueue(sample);
        if(!d->interthreadDynamicQueue)
        {
            semaphore->release(1);
            transmit();
        } else
        {
            if( d->semaphoreN.find(semaphore) == d->semaphoreN.end() )
            {
                d->semaphoreN[semaphore] = 1;
            }
            int32_t delta = d->semaphoreN[semaphore] - d->queue.size();
            if (delta <= 0)
            {
                semaphore->release(1-delta);
                d->semaphoreN[semaphore] += -delta;
                NEXXT_LOG_INTERNAL(QString("delta = %1: semaphoreN = %2").arg(delta).arg(d->semaphoreN[semaphore]));
                transmit();
            } else
            {
                /* the first item is already acquired by the calling thread */
                d->semaphoreN[semaphore]--;
                for(int32_t i = 1; i < delta; i++)
                {
                    if(semaphore->tryAcquire(1))
                    {
                        d->semaphoreN[semaphore]--;
                    } else
                    {
                        break;
                    }
                }
                NEXXT_LOG_INTERNAL(QString("delta = %1: semaphoreN = %2").arg(delta).arg(d->semaphoreN[semaphore]));
                transmit();
            }
        }
    } catch(std::exception &e)
    {
        NEXXT_LOG_ERROR(QString("Unhandled exception in port data changed: %1").arg(e.what()));
    }
}

void InputPortInterface::receiveSync (const QSharedPointer<const DataSample> &sample)
{
    try
    {
        if( QThread::currentThread() != thread() )
        {
            throw std::runtime_error("InputPort.getData has been called from an unexpected thread.");
        }
        addToQueue(sample);
        transmit();
    } catch(std::exception &e)
    {
        NEXXT_LOG_ERROR(QString("Unhandled exception in port data changed: %1").arg(e.what()));
    }
}

