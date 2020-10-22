/* 
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

#include "FilterEnvironment.hpp"
#include "Filters.hpp"
#include "Logger.hpp" 
#include "PropertyCollection.hpp"

#include <QtCore/QThread>
#include <QtCore/QMutex>

using namespace nexxT;

namespace nexxT
{
    struct BaseFilterEnvironmentD
    {
        SharedFilterPtr plugin;
        QThread *thread;
        /* propertyCollection is owned by the property subsystem and it is ensured that the object stays valid over the filter lifetime */
        PropertyCollection *propertyCollection; 
        bool dynamicInputPortsSupported;
        bool dynamicOutputPortsSupported;
    };
};

BaseFilterEnvironment::BaseFilterEnvironment(PropertyCollection *propertyCollection)
    : d(new BaseFilterEnvironmentD{SharedFilterPtr(), QThread::currentThread(), propertyCollection, false, false})
{
    NEXXT_LOG_INTERNAL(QString("BaseFilterEnvironment::BaseFilterEnvironment %1").arg(uint64_t(this), 0, 16));
}

BaseFilterEnvironment::~BaseFilterEnvironment()
{
    NEXXT_LOG_INTERNAL(QString("BaseFilterEnvironment::~BaseFilterEnvironment %1").arg(uint64_t(this), 0, 16));
    delete d;
}

void BaseFilterEnvironment::setPlugin(const SharedFilterPtr &plugin)
{
    d->plugin = plugin;
}

void BaseFilterEnvironment::resetPlugin()
{
    d->plugin.reset();
}

SharedFilterPtr BaseFilterEnvironment::getPlugin()
{
    return d->plugin;
}

void BaseFilterEnvironment::setDynamicPortsSupported(bool dynInPortsSupported, bool dynOutPortsSupported)
{
    assertMyThread();
    d->dynamicInputPortsSupported = dynInPortsSupported;
    d->dynamicOutputPortsSupported = dynOutPortsSupported;
    if(!dynInPortsSupported)
    {
        PortList p = getDynamicInputPorts();
        if( p.size() > 0 )
        {
            throw std::runtime_error("Dynamic input ports are not supported");
        }
    }
    if(!dynOutPortsSupported)
    {
        PortList p = getDynamicOutputPorts();
        if( p.size() > 0 )
        {
            throw std::runtime_error("Dynamic output ports are not supported");
        }
    }
}

void BaseFilterEnvironment::getDynamicPortsSupported(bool &dynInPortsSupported, bool &dynOutPortsSupported)
{
    assertMyThread();
    dynInPortsSupported = d->dynamicInputPortsSupported;
    dynOutPortsSupported = d->dynamicOutputPortsSupported;
}

void BaseFilterEnvironment::portDataChanged(const InputPortInterface &port)
{
    assertMyThread();
    if( state() != FilterState::ACTIVE )
    {
        if( state() != FilterState::OPENED )
        {
            throw std::runtime_error(QString("Unexpected filter state %1, expected ACTIVE or INITIALIZED.").arg(FilterState::state2str(state())).toStdString());
        }
        NEXXT_LOG_INFO("DataSample discarded because application has been stopped already.");
    } else
    {
        try
        {
            if( getPlugin() )
            {
                getPlugin()->onPortDataChanged(port);
            } else
            {
                NEXXT_LOG_ERROR(QString("no plugin found"));
            }
        } catch(std::exception &e)
        {
            NEXXT_LOG_ERROR(QString("Unexpected exception during onPortDataChanged from filter %1: %2").arg(d->propertyCollection->objectName()).arg(e.what()));
        }
    }
}

PropertyCollection *BaseFilterEnvironment::propertyCollection() const
{
    return d->propertyCollection;
}

void BaseFilterEnvironment::assertMyThread()
{
    if( QThread::currentThread() != d->thread )
    {
        throw std::runtime_error("Unexpected thread.");
    }
}
