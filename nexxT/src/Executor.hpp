/*
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

/**
    \file Executor.hpp
    This file is the c++ version of \verbatim embed:rst :py:mod:`nexxT.core.Executor` \endverbatim
*/

#ifndef NEXXT_EXECUTOR_HPP
#define NEXXT_EXECUTOR_HPP

#include <QtCore/QObject>

#include "SharedPointerTypes.hpp"
#include "Filters.hpp"
#include "DataSamples.hpp"
#include "NexxTLinkage.hpp"

class QSemaphore;
class QThread;

//! @cond Doxygen_Suppress
namespace nexxT
{
    struct ExecutorD;

    /*!
        This class is the C++ variant of \verbatim embed:rst:inline :py:class:`nexxT.core.Executor.Executor`
        \endverbatim
    */
    class DLLEXPORT Executor: public QObject
    {
        Q_OBJECT

        ExecutorD *d;
    public:
        /*!
            Constructor, see \verbatim embed:rst:inline :py:meth:`nexxT.core.Executor.Executor.__init__`
            \endverbatim
        */
        Executor(QThread *qthread);
        /*!
            Destructor
        */
        virtual ~Executor();

        /*!
            See \verbatim embed:rst:inline :py:meth:`nexxT.core.Executor.Executor.getContent` \endverbatim
        */
        void finalize();
        /*!
            See \verbatim embed:rst:inline :py:meth:`nexxT.core.Executor.Executor.clear` \endverbatim
        */
        void clear();

        /*!
            Returns a shared pointer of the given executor instance, which takes the ownership of the instance.
        */
        static SharedExecutorPtr make_shared(Executor *executor);

    signals:

        /*!
            See \verbatim embed:rst:inline :py:meth:`nexxT.core.Executor.Executor.notify` \endverbatim
        */
        void notify();

    protected slots:
        /*!
            This function processes a bunch of step() functions. It's only called via QTimer::singleShot
        */
        void multiStep();

    public slots:
        /*!
            See \verbatim embed:rst:inline :py:meth:`nexxT.core.Executor.Executor.registerPendingRcvSync` \endverbatim
        */
        void registerPendingRcvSync(const SharedInputPortPtr &inputPort, const SharedDataSamplePtr &dataSample);
        /*!
            See \verbatim embed:rst:inline :py:meth:`nexxT.core.Executor.Executor.registerPendingRcvAsync` \endverbatim
        */
        void registerPendingRcvAsync(const SharedInputPortPtr &inputPort, const SharedDataSamplePtr &dataSample, QSemaphore *semaphore);
        /*!
            See \verbatim embed:rst:inline :py:meth:`nexxT.core.Executor.Executor.notifyInThread` \endverbatim
        */
        void notifyInThread();
        /*!
            See \verbatim embed:rst:inline :py:meth:`nexxT.core.Executor.Executor.step` \endverbatim
        */
        bool step(const SharedFilterPtr &fromFilter = SharedFilterPtr());
    };
};
//! @endcond

#endif
