/* 
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

#ifndef NEXT_PORTS_HPP
#define NEXT_PORTS_HPP

#include <QtCore/QObject>
#include <QtCore/QSemaphore>
#include "NexTConfig.hpp"
#include "NexTLinkage.hpp"
#include "DataSamples.hpp"

START_NAMESPACE

    class BaseFilterEnvironment;
    struct PortD;
    struct InputPortD;
    struct InterThreadConnectionD;
    class Port;
    class InputPortInterface;
    class OutputPortInterface;
    typedef NEXT_SHARED_PTR<Port> SharedPortPtr;
    typedef NEXT_SHARED_PTR<OutputPortInterface> SharedOutputPortPtr;
    typedef NEXT_SHARED_PTR<InputPortInterface> SharedInputPortPtr;

    class DLLEXPORT Port : public QObject
    {
        Q_OBJECT
        
        PortD *const d;

    public:
        Port(bool dynamic, const QString &name, BaseFilterEnvironment *env);
        virtual ~Port();

        bool dynamic() const;
        const QString &name() const;
        void setName(const QString &name);
        BaseFilterEnvironment *environment() const;
        bool isOutput() const;
        bool isInput() const;

        SharedPortPtr clone(BaseFilterEnvironment *) const;

        static SharedPortPtr make_shared(Port *port);
    };
#if 0
    class DLLEXPORT PortList
    {
        typedef QSharedPointer<Port> T;
        QList< T > ports;
    public:
        void append(T p) {ports.append(p);}
        T at(int i) {return ports[i];}
        int size() {return ports.size();}
    };
#endif
    typedef QList<QSharedPointer<Port> > PortList;

    class DLLEXPORT OutputPortInterface final : public Port
    {
        Q_OBJECT
        
    signals:
        void transmitSample(const QSharedPointer<const nexxT::DataSample> &sample);

    public:
        OutputPortInterface(bool dynamic, const QString &name, BaseFilterEnvironment *env);
        void transmit(const SharedDataSamplePtr &sample);
        SharedPortPtr clone(BaseFilterEnvironment *) const;

        static void setupDirectConnection(const SharedPortPtr &, const SharedPortPtr &);
        static QObject *setupInterThreadConnection(const SharedPortPtr &, const SharedPortPtr &, QThread &);
    };

    class DLLEXPORT InputPortInterface final : public Port
    {
        Q_OBJECT

        InputPortD *const d;

    public:
        InputPortInterface(bool dynamic, const QString &name, BaseFilterEnvironment *env, int queueSizeSamples, double queueSizeSeconds);
        virtual ~InputPortInterface();

        SharedDataSamplePtr getData(int delaySamples=0, double delaySeconds=-1.) const;
        SharedPortPtr clone(BaseFilterEnvironment *) const;

    public slots:
        void receiveAsync(const QSharedPointer<const nexxT::DataSample> &sample, QSemaphore *semaphore);
        void receiveSync (const QSharedPointer<const nexxT::DataSample> &sample);

    private:
        void addToQueue(const SharedDataSamplePtr &sample);
    };

    class DLLEXPORT InterThreadConnection : public QObject
    {
        Q_OBJECT
        
        InterThreadConnectionD *const d;
    public:
        InterThreadConnection(QThread *qthread_from);
        virtual ~InterThreadConnection();

    signals:
        void transmitInterThread(const QSharedPointer<const nexxT::DataSample> &sample, QSemaphore *semaphore);

    public slots:
        void receiveSample(const QSharedPointer<const nexxT::DataSample> &sample);
    };

STOP_NAMESPACE

#endif
