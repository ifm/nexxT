/*
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

#include "Executor.hpp"
#include "FilterEnvironment.hpp"
#include "InputPortInterface.hpp"
#include "OutputPortInterface.hpp"
#include "Logger.hpp"

#include <QtCore/QThread>
#include <QtCore/Qt>
#include <QtCore/QMutex>
#include <QtCore/QMutexLocker>
#include <QtCore/QSemaphore>
#include <QtCore/QTimer>

#include <vector>
#include <set>
#include <chrono>

/* maximum number of events processed before step function returns */
#define MAX_EVENTS_PER_STEP (32)
/* after this time has elapsed, the step function will return to avoid unresponsiveness */
#define STEP_DEADLINE (100ms)

using namespace nexxT;

namespace nexxT
{
    struct ExecutorD
    {
        struct ReceiveEvent
        {
            SharedInputPortPtr inputPort;
            SharedDataSamplePtr dataSample;
            QSemaphore *semaphore;
        };

        static const int MAX_LOOPS_FINALIZE = 5;

        QMutex pendingReceivesMutex;
        std::vector<ReceiveEvent> pendingReceives;
        std::set<Filter *> blockedFilters;
        bool stopped;
        // in contrast to the python reference implementation, the pressure on the QT event loop is reduced in the C++
        // implementation by omitting unnecessary notify calls through the event loop. We count the number of pending
        // notify calls and omit the call if there is already a pending call in the event loop.
        int32_t numNotifiesInQueue;
    };
};

Executor::Executor(QThread *qthread) :
    QObject(),
    d(new ExecutorD())
{
    moveToThread(qthread);
    QObject::connect(this, SIGNAL(notify()), this, SLOT(notifyInThread()), Qt::QueuedConnection);
    d->numNotifiesInQueue = 0;
}

Executor::~Executor()
{
    delete d;
}

void Executor::registerPendingRcvSync(const SharedInputPortPtr &inputPort,
                                      const SharedDataSamplePtr &dataSample)
{
    if( !d->stopped )
    {
        ExecutorD::ReceiveEvent ev{inputPort, dataSample, 0};
        {
            QMutexLocker locker(&d->pendingReceivesMutex);
            //NEXXT_LOG_INFO(QString("add to executor queue %1/%2 (sync)").
            //    arg(inputPort->environment()->getFullQualifiedName()).
            //    arg(inputPort->name()));
            d->pendingReceives.push_back(ev);
        }
        notifyInThread();
    }
}

void Executor::registerPendingRcvAsync(const SharedInputPortPtr &inputPort,
                                       const SharedDataSamplePtr &dataSample,
                                       QSemaphore *semaphore)
{
    if( !d->stopped )
    {
        ExecutorD::ReceiveEvent ev{inputPort, dataSample, semaphore};
        {
            QMutexLocker locker(&d->pendingReceivesMutex);
            //NEXXT_LOG_INFO(QString("add to executor queue %1/%2 (async)").
            //   arg(inputPort->environment()->getFullQualifiedName()).arg(inputPort->name()));
            d->pendingReceives.push_back(ev);
        }
        emit notify();
    }
}

void Executor::notifyInThread()
{
    if( QThread::currentThread() != thread() )
    {
        NEXXT_LOG_ERROR("Executor::notifyInThread: Unexpected thread!");
    }
    if(d->numNotifiesInQueue == 0)
    {
        //NEXXT_LOG_INFO(QString("[%1] calling step via QT event.").arg(QThread::currentThread()->objectName()));
        d->numNotifiesInQueue++;
        QTimer::singleShot(0, this, SLOT(multiStep()));
    }
}

void Executor::multiStep()
{
    using namespace std::literals::chrono_literals;
    std::chrono::steady_clock::time_point begin = std::chrono::steady_clock::now();
    std::chrono::steady_clock::time_point curr = begin;
    uint32_t maxEvents = MAX_EVENTS_PER_STEP;
    d->numNotifiesInQueue--;
    if(d->numNotifiesInQueue < 0)
    {
        NEXXT_LOG_ERROR("Unexpected numNotifiesInQueue!");
    }
    while( (!d->stopped) && (maxEvents > 0) && (curr - begin < STEP_DEADLINE) )
    {
        if(!step())
        {
            /* no more events to process */
            return;
        } else
        {
            maxEvents--;
        }
        curr = std::chrono::steady_clock::now();
    }
    /* the last step() function result was true, so we aborted early, register another multiStep call */
    notifyInThread();
}

struct StepFunctionHelper
{
    const SharedFilterPtr &fromFilter;
    ExecutorD *d;
    bool &res;

    StepFunctionHelper(const SharedFilterPtr &_fromFilter, ExecutorD *_d, bool &_res) :
        fromFilter(_fromFilter),
        d(_d),
        res(_res)
    {
        if( fromFilter.get() != 0 )
        {
            //NEXXT_LOG_INFO(QString("[%1] Entering Executor::step, blocking filter %2").
            //    arg(QThread::currentThread()->objectName()).
            //    arg(fromFilter->environment()->getFullQualifiedName()));
            d->blockedFilters.insert(fromFilter.get());
        } else
        {
            //NEXXT_LOG_INFO(QString("[%1] Entering Executor::step without blocking").
            //    arg(QThread::currentThread()->objectName()));
        }
    }
    ~StepFunctionHelper()
    {
        if( !res )
        {
            d->pendingReceivesMutex.unlock();
        }
        if( fromFilter.get() != 0 )
        {
            //NEXXT_LOG_INFO(QString("[%1] Unblocking filter %2").
            //    arg(QThread::currentThread()->objectName()).
            //    arg(fromFilter->environment()->getFullQualifiedName()));
            d->blockedFilters.erase(fromFilter.get());
        }
        //NEXXT_LOG_INFO(QString("[%1] Leaving Executor::step").
        //    arg(QThread::currentThread()->objectName()));
    }
};

bool Executor::step(const SharedFilterPtr &fromFilter)
{
    bool res = false;
    if( !d->stopped )
    {
        StepFunctionHelper helper(fromFilter, d, res);
        d->pendingReceivesMutex.lock();
        for(auto it=d->pendingReceives.begin(); it != d->pendingReceives.end(); it++)
        {
            if( d->blockedFilters.empty() ||
                d->blockedFilters.count(it->inputPort->environment()->getPlugin().get()) == 0 )
            {
                ExecutorD::ReceiveEvent ev(*it);
                d->pendingReceives.erase(it);
                /* it is invalid from here on */
                d->pendingReceivesMutex.unlock();
                res = true;
                if( !ev.semaphore )
                {
                    ev.inputPort->receiveSync(ev.dataSample);
                } else
                {
                    ev.inputPort->receiveAsync(ev.dataSample, ev.semaphore);
                }
                break;
            }
        }
    }
    return res;
}

void Executor::finalize()
{
    std::multiset<InputPortInterface *> numCalled;
    bool changed = true;
    while(changed)
    {
        changed = false;
        d->pendingReceivesMutex.lock();
        for(auto it=d->pendingReceives.begin(); it != d->pendingReceives.end(); it++)
        {
            bool cond1 = d->blockedFilters.count(it->inputPort->environment()->getPlugin().get()) == 0;
            bool cond2 = numCalled.count(it->inputPort.get()) < d->MAX_LOOPS_FINALIZE;
            if(cond1 && cond2)
            {
                ExecutorD::ReceiveEvent ev(*it);
                d->pendingReceives.erase(it);
                /* it is invalid from here on */
                d->pendingReceivesMutex.unlock();
                changed = true;
                numCalled.insert(ev.inputPort.get());
                if( !ev.semaphore )
                {
                    ev.inputPort->receiveSync(ev.dataSample);
                } else
                {
                    ev.inputPort->receiveAsync(ev.dataSample, ev.semaphore);
                }
                d->pendingReceivesMutex.lock();
                break;
            }
        }
        d->pendingReceivesMutex.unlock();
    }
}

void Executor::clear()
{
    d->stopped = true;
    d->pendingReceives.clear();
    d->blockedFilters.clear();
}

SharedExecutorPtr Executor::make_shared(Executor *executor)
{
    return SharedExecutorPtr(executor);
}
