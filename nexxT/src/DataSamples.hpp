/* 
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
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
    typedef QSharedPointer<const DataSample> SharedDataSamplePtr;

    class DLLEXPORT DataSample
    {
        DataSampleD *d;
      public:
        static const double TIMESTAMP_RES;
        
        DataSample(const QByteArray &content, const QString &datatype, int64_t timestamp);
        virtual ~DataSample();
        
        QByteArray getContent() const;
        int64_t getTimestamp() const;
        QString getDatatype() const;
        
        static SharedDataSamplePtr copy(const SharedDataSamplePtr &src);
        static SharedDataSamplePtr make_shared(DataSample *sample);
        static void registerMetaType();
        static int64_t currentTime();
    };
};

Q_DECLARE_METATYPE(QSharedPointer<const nexxT::DataSample>);

#endif
