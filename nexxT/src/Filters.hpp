/* 
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

#ifndef NEXT_FILTERS_HPP
#define NEXT_FILTERS_HPP

#include <cstdint>
#include <QtCore/QString>
#include <QtCore/QObject>
#include <QtCore/QList>

#include "NexTConfig.hpp"
#include "NexTLinkage.hpp"
#include "Ports.hpp"

START_NAMESPACE
    
    struct DLLEXPORT FilterState
    {
        static const int CONSTRUCTING = 0;
        static const int CONSTRUCTED = 1;
        static const int INITIALIZING = 2;
        static const int INITIALIZED = 3;
        static const int OPENING = 4;
        static const int OPENED = 5;
        static const int STARTING = 6;
        static const int ACTIVE = 7;
        static const int STOPPING = 8;
        static const int CLOSING = 9;
        static const int DEINITIALIZING = 10;
        static const int DESTRUCTING = 11;
        static const int DESTRUCTED = 12;

        static QString state2str(int state);
    };

    class Filter;
    struct FilterD;
    class BaseFilterEnvironment;
    class PropertyCollection;

    typedef NEXT_SHARED_PTR<Filter> SharedFilterPtr;

    class DLLEXPORT Filter : public QObject
    {
        Q_OBJECT 

        FilterD *const d;
    protected:
        Filter(bool dynInPortsSupported, bool dynOutPortsSupported, BaseFilterEnvironment *env);

        PropertyCollection *propertyCollection();
        PropertyCollection *guiState();

        void addStaticPort(const SharedPortPtr &port);
        SharedPortPtr addStaticOutputPort(const QString &name);
        SharedPortPtr addStaticInputPort(const QString &name, int queueSizeSamples, double queueSizeSeconds);
        void removeStaticPort(const SharedPortPtr &port);
        PortList getDynamicInputPorts();
        PortList getDynamicOutputPorts();

    public:
        virtual ~Filter();
        virtual void onInit();
        virtual void onOpen();
        virtual void onStart();
        virtual void onPortDataChanged(const InputPortInterface &inputPort);
        virtual void onStop();
        virtual void onClose();
        virtual void onDeinit();

        BaseFilterEnvironment *environment() const;

        static SharedFilterPtr make_shared(Filter *filter);
    };

STOP_NAMESPACE

#endif
