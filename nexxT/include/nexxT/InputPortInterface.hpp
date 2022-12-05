/* 
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

/**
    \file InputPortInterface.hpp
    The interface corresponding to \verbatim embed:rst :py:mod:`nexxT.interface.Ports` \endverbatim
*/

#ifndef NEXXT_INPUT_PORT_INTERFACE_HPP
#define NEXXT_INPUT_PORT_INTERFACE_HPP

#include <QtCore/QObject>
#include <QtCore/QSemaphore>
#include "nexxT/NexxTLinkage.hpp"
#include "nexxT/SharedPointerTypes.hpp"
#include "nexxT/Ports.hpp"

namespace nexxT
{
    class BaseFilterEnvironment;
    struct InputPortD;

    /*!
        This class is the C++ variant of \verbatim embed:rst:inline :py:class:`nexxT.interface.Ports.InputPortInterface`
        \endverbatim.

        In contrast to the python version, this class is not abstract but directly implements the functionality.
    */
    class DLLEXPORT InputPortInterface : public Port
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
        virtual SharedPortPtr clone(BaseFilterEnvironment *) const;

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
        void receiveAsync(const QSharedPointer<const nexxT::DataSample> &sample, QSemaphore *semaphore, bool isPending=false);
        /*!
            Called by the nexxT framework, not intended to be used directly.
        */
        void receiveSync (const QSharedPointer<const nexxT::DataSample> &sample);

    private:
        void addToQueue(const SharedDataSamplePtr &sample);
        void transmit();
    };

    /*!
        A typedef for an InputPortInterface instance handled by a shared pointer.
    */
    typedef QSharedPointer<InputPortInterface> SharedInputPortPtr;

};

#endif
