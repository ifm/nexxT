/* 
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

#include "nexxT/OutputPortInterface.hpp"
#include "nexxT/InputPortInterface.hpp"
#include "nexxT/DataSamples.hpp"
#include "nexxT/FilterEnvironment.hpp"
#include "nexxT/Filters.hpp"
#include "nexxT/Logger.hpp"
#include "nexxT/Services.hpp"
#include <atomic>

#include <QtCore/QThread>
#include <map>
#include <cstdio>

using namespace nexxT;

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

QObject *OutputPortInterface::setupInterThreadConnection(const SharedPortPtr &op, const SharedPortPtr &ip, QThread &outputThread, int width)
{
    InterThreadConnection *itc = new InterThreadConnection(&outputThread, width);
    const OutputPortInterface *p0 = dynamic_cast<const OutputPortInterface *>(op.data());
    const InputPortInterface *p1 = dynamic_cast<const InputPortInterface *>(ip.data());
    QObject::connect(p0, SIGNAL(transmitSample(const QSharedPointer<const nexxT::DataSample>&)),
                     itc, SLOT(receiveSample(const QSharedPointer<const nexxT::DataSample>&)));
    QObject::connect(itc, SIGNAL(transmitInterThread(const QSharedPointer<const nexxT::DataSample> &, QSemaphore *)),
                     p1, SLOT(receiveAsync(const QSharedPointer<const nexxT::DataSample> &, QSemaphore *)));
    return itc;
}

