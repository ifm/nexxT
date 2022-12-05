/* 
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

#include "nexxT/InputPortInterface.hpp"
#include "nexxT/DataSamples.hpp"
#include "nexxT/FilterEnvironment.hpp"
#include "nexxT/Filters.hpp"
#include "nexxT/Logger.hpp"
#include "nexxT/Services.hpp"
#include "nexxT/Logger.hpp"
#include <atomic>
#include <tuple>

#include <QtCore/QThread>
#include <QtCore/QVariant>
#include <QtCore/QCoreApplication>
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
    if( QThread::currentThread() != thread() )
    {
        throw std::runtime_error("InputPort.getData has been called from an unexpected thread.");
    }
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

void InputPortInterface::receiveAsync(const QSharedPointer<const DataSample> &sample, QSemaphore *semaphore, bool isPending)
{
    /* pending receives from the main thread are stored here to be processed later */
    typedef std::tuple<InputPortInterface*, QSharedPointer<const DataSample>, QSemaphore *> RcvArgs;
    static std::vector<RcvArgs> pendingReceives;
    try
    {
        if( QThread::currentThread() != thread() )
        {
            throw std::runtime_error("InputPort.getData has been called from an unexpected thread.");
        }
        if( (!isPending) && (QThread::currentThread() == QCoreApplication::instance()->thread()) )
        {
            /* avoid unresponsive main thread 
            
            It turned out that the main thread is getting unresponsive at high computational loads.
            Therefore, we apply processEvents with some extra care here. Note that receiveAsync is
            always called directly from the QT event loop, so processing events at this place should
            be safe. However, we have to take care that other receiveAsync events are still in the 
            correct order, that's why we have the buffering in pendingReceives.
            */
            static uint32_t stackDepth = 0;
            if( stackDepth > 0 )
            {
                /* 
                This sample was the result of an ongoing processEvents call. Store this sample for later
                processing to preserve sample order. 
                
                note that there is no concurrency problem here because we apply this only in main thread 
                */
                pendingReceives.push_back(std::make_tuple(this, sample, semaphore));
                return;
            }
            stackDepth++;
            QCoreApplication::instance()->thread()->setProperty("processEventsRunning", QVariant(true));
            QCoreApplication::processEvents();
            QCoreApplication::instance()->thread()->setProperty("processEventsRunning", QVariant(false));
            stackDepth--;
        }
        addToQueue(sample);
        if( (!d->interthreadDynamicQueue) || (!semaphore) )
        {
            transmit();
            if(semaphore)
            {
                semaphore->release(1);
            }
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
    if( QThread::currentThread() == QCoreApplication::instance()->thread() )
    {
        /* 
        process pending samples resulting from previous processEvents call 
        again, thread safety is not an issue here, because this is done only in the
        main thread.
        */
        std::vector<RcvArgs> pendingCopy = pendingReceives;
        pendingReceives.clear();
        for(auto c: pendingCopy)
        {
            InputPortInterface *pInstance;
            QSharedPointer<const DataSample> pSample;
            QSemaphore *pSemaphore;
            std::tie(pInstance, pSample, pSemaphore) = c;
            /* do not call processEvents again to save some performance (last argument is true) */
            pInstance->receiveAsync(pSample, pSemaphore, true);
        }
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

