/* 
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

/**
    \file DataSamples.hpp
    The interface corresponding to \verbatim embed:rst :py:mod:`nexxT.interface.DataSample` \endverbatim
*/

#ifndef NEXXT_DATA_SAMPLES_HPP
#define NEXXT_DATA_SAMPLES_HPP

#include <cstdint>
#include <QtCore/QByteArray>
#include <QtCore/QString>
#include <QtCore/QSharedPointer>

#include "NexxTLinkage.hpp"

namespace nexxT
{
    struct DataSampleD;
    class DataSample;

    /*!
        A typedef for a Datasample handled by a shared pointer.
    */
    typedef QSharedPointer<const DataSample> SharedDataSamplePtr;

    /*!
        This class is the C++ variant of \verbatim embed:rst:inline :py:class:`nexxT.interface.DataSamples.DataSample`
        \endverbatim
    */
    class DLLEXPORT DataSample
    {
        DataSampleD *d;
      public:
        /*!
            The resolution of the timstamps in [seconds]
        */
        static const double TIMESTAMP_RES;

        /*!
            Constructor, see \verbatim embed:rst:inline :py:meth:`nexxT.interface.DataSamples.DataSample.__init__`
            \endverbatim
        */
        DataSample(const QByteArray &content, const QString &datatype, int64_t timestamp);
        /*!
            Destructor
        */
        virtual ~DataSample();

        /*!
            See \verbatim embed:rst:inline :py:meth:`nexxT.interface.DataSamples.DataSample.getContent` \endverbatim
        */
        QByteArray getContent() const;

        /*!
            See \verbatim embed:rst:inline :py:meth:`nexxT.interface.DataSamples.DataSample.getTimestamp` \endverbatim
        */
        int64_t getTimestamp() const;

        /*!
            See \verbatim embed:rst:inline :py:meth:`nexxT.interface.DataSamples.DataSample.getDatatype` \endverbatim
        */
        QString getDatatype() const;
        
        /*!
            See \verbatim embed:rst:inline :py:meth:`nexxT.interface.DataSamples.DataSample.copy` \endverbatim
        */
        static SharedDataSamplePtr copy(const SharedDataSamplePtr &src);

        /*!
            Return a shared pointer referencing the given instance. The ownership of the pointer is transferred to the
            shared pointer.
        */
        static SharedDataSamplePtr make_shared(DataSample *sample);

        /*!
            See \verbatim embed:rst:inline :py:meth:`nexxT.interface.DataSamples.DataSample.currentTime` \endverbatim
        */
        static int64_t currentTime();

//! @cond Doxygen_Suppress
        static void registerMetaType();
//! @endcond
    };
};

//! @cond Doxygen_Suppress
Q_DECLARE_METATYPE(QSharedPointer<const nexxT::DataSample>);
//! @endcond

#endif
