/* 
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

#include "OutputPortInterface.hpp"
#include "InputPortInterface.hpp"
#include "DataSamples.hpp"
#include "FilterEnvironment.hpp"
#include "Filters.hpp"
#include "Logger.hpp"
#include "Services.hpp"
#include "Executor.hpp"
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

QObject *OutputPortInterface::setupPortToPortConnection(const SharedExecutorPtr &executorFrom,
                                                        const SharedExecutorPtr &executorTo,
                                                        const SharedPortPtr &_outputPort,
                                                        const SharedPortPtr &_inputPort)
{
    SharedOutputPortPtr outputPort = _outputPort.dynamicCast<OutputPortInterface>();
    SharedInputPortPtr inputPort = _inputPort.dynamicCast<InputPortInterface>();
    PortToPortConnection *p2pc = new PortToPortConnection(executorFrom, executorTo, outputPort, inputPort);
    if( outputPort->thread() != executorFrom->thread() )
    {
        NEXXT_LOG_ERROR("Unexpected threads (outputPort vs executorFrom)");
    }
    if( inputPort->thread() != executorTo->thread() )
    {
        NEXXT_LOG_ERROR("Unexpected threads (inputPort vs executorTo)");
    }
    const OutputPortInterface *p0 = dynamic_cast<const OutputPortInterface *>(outputPort.data());
    QObject::connect(p0, SIGNAL(transmitSample(const QSharedPointer<const nexxT::DataSample>&)),
                     p2pc, SLOT(receiveSample(const QSharedPointer<const nexxT::DataSample>&)),
                     Qt::DirectConnection);
    return p2pc;
}
