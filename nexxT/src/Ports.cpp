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

SharedPortPtr Port::clone(BaseFilterEnvironment *env) const
{
    if( dynamic_cast<const OutputPortInterface*>(this) )
    {
        return dynamic_cast<const OutputPortInterface*>(this)->clone(env);
    } else if( dynamic_cast<const InputPortInterface*>(this)  )
    {
        return dynamic_cast<const InputPortInterface*>(this)->clone(env);
    }
    throw(std::runtime_error("Unknown port class. Must be either OutputPortInterface or InputPortInterface."));
}

SharedPortPtr Port::make_shared(Port *port)
{
    return SharedPortPtr(port);
}

OutputPortInterface::OutputPortInterface(bool dynamic, const QString &name, BaseFilterEnvironment *env) :
    Port(dynamic, name, env)
{
}

void OutputPortInterface::transmit(const SharedDataSamplePtr &sample)
{
    if( QThread::currentThread() != thread() )
    {
        throw std::runtime_error("OutputPort::transmit has been called from unexpected thread.");
    }
    emit transmitSample(sample);
}

SharedPortPtr OutputPortInterface::clone(BaseFilterEnvironment *env) const
{
    return SharedPortPtr(new OutputPortInterface(dynamic(), name(), env));
}

void OutputPortInterface::setupDirectConnection(const SharedPortPtr &op, const SharedPortPtr &ip)
{
    const OutputPortInterface *p0 = dynamic_cast<const OutputPortInterface *>(op.data());
    const InputPortInterface *p1 = dynamic_cast<const InputPortInterface *>(ip.data());
    QObject::connect(p0, SIGNAL(transmitSample(const QSharedPointer<const nexxT::DataSample>&)),
                     p1, SLOT(receiveSync(const QSharedPointer<const nexxT::DataSample> &)));
}

QObject *OutputPortInterface::setupInterThreadConnection(const SharedPortPtr &op, const SharedPortPtr &ip, QThread &outputThread)
{
    InterThreadConnection *itc = new InterThreadConnection(&outputThread);
    const OutputPortInterface *p0 = dynamic_cast<const OutputPortInterface *>(op.data());
    const InputPortInterface *p1 = dynamic_cast<const InputPortInterface *>(ip.data());
    QObject::connect(p0, SIGNAL(transmitSample(const QSharedPointer<const nexxT::DataSample>&)),
                     itc, SLOT(receiveSample(const QSharedPointer<const nexxT::DataSample>&)));
    QObject::connect(itc, SIGNAL(transmitInterThread(const QSharedPointer<const nexxT::DataSample> &, QSemaphore *)),
                     p1, SLOT(receiveAsync(const QSharedPointer<const nexxT::DataSample> &, QSemaphore *)));
    return itc;
}

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