/* 
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

#ifndef NEXXT_FILTER_ENVIRONMENT_HPP
#define NEXXT_FILTER_ENVIRONMENT_HPP

#include <QtCore/QObject>

#include "Ports.hpp"
#include "Filters.hpp"
#include "NexxTLinkage.hpp"

namespace nexxT
{
    struct BaseFilterEnvironmentD;
    class PropertyCollection;

    class DLLEXPORT BaseFilterEnvironment: public QObject
    {
        Q_OBJECT

        BaseFilterEnvironmentD *d;
    public:
        BaseFilterEnvironment(PropertyCollection* propertyCollection);
        BaseFilterEnvironment(const BaseFilterEnvironment &) = delete;
        virtual ~BaseFilterEnvironment();

        void setPlugin(const SharedFilterPtr &plugin);
        void resetPlugin();
        SharedFilterPtr getPlugin();

        void setDynamicPortsSupported(bool dynInPortsSupported, bool dynOutPortsSupported);
        void getDynamicPortsSupported(bool &dynInPortsSupported, bool &dynOutPortsSupported);

        void portDataChanged(const InputPortInterface &port);
        
        PropertyCollection *propertyCollection() const;

        virtual PropertyCollection *guiState() const = 0;

        virtual void addPort(const SharedPortPtr &port) = 0;
        virtual void removePort(const SharedPortPtr &port) = 0;

        virtual QList<QSharedPointer<Port> > getDynamicInputPorts() = 0;
        virtual QList<QSharedPointer<Port> > getStaticInputPorts() = 0;
        virtual QList<QSharedPointer<Port> > getAllInputPorts() = 0;

        virtual QList<QSharedPointer<Port> > getDynamicOutputPorts() = 0;
        virtual QList<QSharedPointer<Port> > getStaticOutputPorts() = 0;
        virtual QList<QSharedPointer<Port> > getAllOutputPorts() = 0;

        /*virtual SharedPortPtr getPort(QString portName, bool input) = 0;
        virtual SharedPortPtr getOutputPort(QString portName) = 0;
        virtual SharedPortPtr getInputPort(QString portName) = 0;*/

        virtual void updatePortInformation(const BaseFilterEnvironment &other) = 0;

        virtual QString getFullQualifiedName() const = 0;

    public:
        virtual int state() const = 0;

    protected:
        void assertMyThread();
    };
};

#endif
