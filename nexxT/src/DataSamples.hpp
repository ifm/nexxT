/* 
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

#ifndef NEXT_DATA_SAMPLES_HPP
#define NEXT_DATA_SAMPLES_HPP

#include <cstdint>
#include <QtCore/QByteArray>
#include <QtCore/QString>

#include "NexTConfig.hpp"
#include "NexTLinkage.hpp"

START_NAMESPACE

    struct DataSampleD;
    class DataSample;
#if 1
    typedef NEXT_SHARED_PTR<const DataSample> SharedDataSamplePtr;
#else
# define SharedDataSamplePtr NEXT_SHARED_PTR<const DataSample>
#endif

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

STOP_NAMESPACE

Q_DECLARE_METATYPE(QSharedPointer<const nexxT::DataSample>);

#endif
