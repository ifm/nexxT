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
#include "nexxT/NexxTLinkage.hpp"
#include "nexxT/SharedPointerTypes.hpp"

namespace nexxT
{
    class BaseFilterEnvironment;
    struct PortD;
    struct InterThreadConnectionD;

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
        virtual SharedPortPtr clone(BaseFilterEnvironment *) const = 0;

        /*!
            Return a shared pointer referencing the given instance. The ownership of the pointer is transferred to the
            shared pointer.
        */
        static SharedPortPtr make_shared(Port *port);
    };

 //! @cond Doxygen_Suppress
   class DLLEXPORT InterThreadConnection : public QObject
    {
        Q_OBJECT

        InterThreadConnectionD *const d;
    public:
        InterThreadConnection(QThread *qthread_from, int width);
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
