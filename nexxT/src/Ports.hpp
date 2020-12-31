/* 
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

/**
    \file Ports.hpp
    The interface corresponding to \verbatim embed:rst :py:mod:`nexxT.interface.Ports` \endverbatim
*/

#ifndef NEXXT_PORTS_HPP
#define NEXXT_PORTS_HPP

#include <QtCore/QObject>
#include <QtCore/QSemaphore>
#include "NexxTLinkage.hpp"
#include "DataSamples.hpp"

namespace nexxT
{
    class BaseFilterEnvironment;
    struct PortD;
    struct InputPortD;
    struct InterThreadConnectionD;
    class Port;
    class InputPortInterface;
    class OutputPortInterface;

    /*!
        A typedef for a Port instance handled by a shared pointer.
    */
    typedef QSharedPointer<Port> SharedPortPtr;

    /*!
        A typedef for an OutputPortInterface instance handled by a shared pointer.
    */
    typedef QSharedPointer<OutputPortInterface> SharedOutputPortPtr;

    /*!
        A typedef for an InputPortInterface instance handled by a shared pointer.
    */
    typedef QSharedPointer<InputPortInterface> SharedInputPortPtr;

    /*!
        This class is the C++ variant of \verbatim embed:rst:inline :py:class:`nexxT.interface.Ports.Port`
        \endverbatim
    */
    class DLLEXPORT Port : public QObject
    {
        Q_OBJECT
        
        PortD *const d;

    public:
        /*!
            Constructor, see \verbatim embed:rst:inline :py:meth:`nexxT.interface.Ports.Port.__init__`
            \endverbatim
        */
        Port(bool dynamic, const QString &name, BaseFilterEnvironment *env);
        /*!
            Destructor
        */
        virtual ~Port();

        /*!
            See \verbatim embed:rst:inline :py:meth:`nexxT.interface.Ports.Port.dynamic` \endverbatim
        */
        bool dynamic() const;
        /*!
            See \verbatim embed:rst:inline :py:meth:`nexxT.interface.Ports.Port.name` \endverbatim
        */
        const QString &name() const;
        /*!
            See \verbatim embed:rst:inline :py:meth:`nexxT.interface.Ports.Port.setName` \endverbatim
        */
        void setName(const QString &name);
        /*!
            See \verbatim embed:rst:inline :py:meth:`nexxT.interface.Ports.Port.environment` \endverbatim
        */
        BaseFilterEnvironment *environment() const;
        /*!
            See \verbatim embed:rst:inline :py:meth:`nexxT.interface.Ports.Port.isOutput` \endverbatim
        */
        bool isOutput() const;
        /*!
            See \verbatim embed:rst:inline :py:meth:`nexxT.interface.Ports.Port.isInput` \endverbatim
        */
        bool isInput() const;

        /*!
            See \verbatim embed:rst:inline :py:meth:`nexxT.interface.Ports.Port.clone` \endverbatim
        */
        SharedPortPtr clone(BaseFilterEnvironment *) const;

        /*!
            Return a shared pointer referencing the given instance. The ownership of the pointer is transferred to the
            shared pointer.
        */
        static SharedPortPtr make_shared(Port *port);
    };

    /*!
        A typedef for a list of ports.
    */
    typedef QList<QSharedPointer<Port> > PortList;

    /*!
        This class is the C++ variant of \verbatim embed:rst:inline :py:class:`nexxT.interface.Ports.OutputPortInterface`
        \endverbatim.

        In contrast to the python version, this class is not abstract but directly implements the functionality.
    */
    class DLLEXPORT OutputPortInterface final : public Port
    {
        Q_OBJECT
        
    signals:
        /*!
            QT signal for transmitting a sample over threads. Note that this signal is not intended to be used directly.
            Use the transmit method instead.

            See \verbatim embed:rst:inline :py:attr:`nexxT.interface.Ports.OutputPortInterface.transmitSample`
            \endverbatim.
        */
        void transmitSample(const QSharedPointer<const nexxT::DataSample> &sample);

    public:
        /*!
            Constructor.

            See \verbatim embed:rst:inline :py:func:`nexxT.interface.Ports.OutputPort`
            \endverbatim.
        */
        OutputPortInterface(bool dynamic, const QString &name, BaseFilterEnvironment *env);
        /*!
            See \verbatim embed:rst:inline :py:meth:`nexxT.interface.Ports.OutputPortInterface.transmit`
            \endverbatim.
        */
        void transmit(const SharedDataSamplePtr &sample);
        /*!
            See \verbatim embed:rst:inline :py:meth:`nexxT.interface.Ports.OutputPortInterface.clone`
            \endverbatim.
        */
        SharedPortPtr clone(BaseFilterEnvironment *) const;

        /*!
            Called by the nexxT framework, not intended to be used directly.
        */
        static void setupDirectConnection(const SharedPortPtr &, const SharedPortPtr &);
        /*!
            Called by the nexxT framework, not intended to be used directly.
        */
        static QObject *setupInterThreadConnection(const SharedPortPtr &, const SharedPortPtr &, QThread &);
    };

    /*!
        This class is the C++ variant of \verbatim embed:rst:inline :py:class:`nexxT.interface.Ports.InputPortInterface`
        \endverbatim.

        In contrast to the python version, this class is not abstract but directly implements the functionality.
    */
    class DLLEXPORT InputPortInterface final : public Port
    {
        Q_OBJECT

        InputPortD *const d;

    public:
        /*!
            Constructor.

            See \verbatim embed:rst:inline :py:func:`nexxT.interface.Ports.InputPort`
            \endverbatim.
        */
        InputPortInterface(bool dynamic, const QString &name, BaseFilterEnvironment *env, int queueSizeSamples = 1, double queueSizeSeconds = -1.0);
        /*!
            Destructor
        */
        virtual ~InputPortInterface();

        /*!
            See \verbatim embed:rst:inline :py:meth:`nexxT.interface.Ports.InputPortInterface.getData`
            \endverbatim.
        */
        SharedDataSamplePtr getData(int delaySamples=0, double delaySeconds=-1.) const;
        /*!
            See \verbatim embed:rst:inline :py:meth:`nexxT.interface.Ports.InputPortInterface.clone`
            \endverbatim.
        */
        SharedPortPtr clone(BaseFilterEnvironment *) const;

        /*!
            See \verbatim embed:rst:inline :py:meth:`nexxT.interface.Ports.InputPortInterface.setQueueSize`
            \endverbatim.
        */
        void setQueueSize(int queueSizeSamples, double queueSizeSeconds);
        /*!
            See \verbatim embed:rst:inline :py:meth:`nexxT.interface.Ports.InputPortInterface.queueSizeSamples`
            \endverbatim.
        */
        int queueSizeSamples();
        /*!
            See \verbatim embed:rst:inline :py:meth:`nexxT.interface.Ports.InputPortInterface.queueSizeSeconds`
            \endverbatim.
        */
        double queueSizeSeconds();

        /*!
            See \verbatim
            embed:rst:inline :py:meth:`nexxT.interface.Ports.InputPortInterface.setInterthreadDynamicQueue`
            \endverbatim.
        */
        void setInterthreadDynamicQueue(bool enabled);
        /*!
            See \verbatim
            embed:rst:inline :py:meth:`nexxT.interface.Ports.InputPortInterface.interthreadDynamicQueue`
            \endverbatim.
        */
        bool interthreadDynamicQueue();

    public slots:
        /*!
            Called by the nexxT framework, not intended to be used directly.
        */
        void receiveAsync(const QSharedPointer<const nexxT::DataSample> &sample, QSemaphore *semaphore);
        /*!
            Called by the nexxT framework, not intended to be used directly.
        */
        void receiveSync (const QSharedPointer<const nexxT::DataSample> &sample);

    private:
        void addToQueue(const SharedDataSamplePtr &sample);
        void transmit();
    };

 //! @cond Doxygen_Suppress
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
        void setStopped(bool stopped);
    };
//! @endcond
};

#endif
