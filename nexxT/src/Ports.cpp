/* 
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

#include "Ports.hpp"
#include "DataSamples.hpp"
#include "FilterEnvironment.hpp"
#include "Logger.hpp"
#include <QtCore/QThread>
#include <cstdio>

USE_NAMESPACE

START_NAMESPACE
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
        QList<SharedDataSamplePtr> queue;
    };

    struct InterThreadConnectionD
    {
        QSemaphore semaphore;
        InterThreadConnectionD(int n) : semaphore(n) {}
    };

STOP_NAMESPACE

Port::Port(bool dynamic, const QString &name, BaseFilterEnvironment *env)
    : d(new PortD{dynamic, name, env})
{
    NEXT_LOG_INTERNAL(QString("Port::Port %1").arg(uint64_t(this), 0, 16));
}

Port::~Port()
{
    NEXT_LOG_INTERNAL(QString("Port::~Port %1").arg(uint64_t(this), 0, 16));
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
    d(new InputPortD{queueSizeSamples, queueSizeSeconds})
{
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
    environment()->portDataChanged(*this);
}

void InputPortInterface::receiveAsync(const QSharedPointer<const DataSample> &sample, QSemaphore *semaphore)
{
    try
    {
        if( QThread::currentThread() != thread() )
        {
            throw std::runtime_error("InputPort.getData has been called from an unexpected thread.");
        }
        semaphore->release(1);
        addToQueue(sample);
    } catch(std::exception &e)
    {
        NEXT_LOG_ERROR(QString("Unhandled exception in port data changed: %1").arg(e.what()));
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
    } catch(std::exception &e)
    {
        NEXT_LOG_ERROR(QString("Unhandled exception in port data changed: %1").arg(e.what()));
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
    d->semaphore.acquire(1);
    emit transmitInterThread(sample, &d->semaphore);
}
