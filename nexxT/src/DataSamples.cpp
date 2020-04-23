/* 
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

#include "DataSamples.hpp"
#include "Logger.hpp"
#include <chrono>

USE_NAMESPACE

static constexpr double TIMESTAMP_RES_VALUE = 1e-6;

const double DataSample::TIMESTAMP_RES = TIMESTAMP_RES_VALUE;
START_NAMESPACE
    struct DataSampleD
    {
        QByteArray content;
        QString datatype;
        int64_t timestamp;
    };
STOP_NAMESPACE

DataSample::DataSample(const QByteArray &content, const QString &datatype, int64_t timestamp) :
    d(new DataSampleD{content,datatype,timestamp})
{
    NEXT_LOG_INTERNAL("DataSample::DataSample");
}

DataSample::~DataSample() 
{
    NEXT_LOG_INTERNAL("DataSample::~DataSample");
    delete d;
}
        
QByteArray DataSample::getContent() const
{
    return d->content;
}
    
int64_t DataSample::getTimestamp() const
{
    return d->timestamp;
}

QString DataSample::getDatatype() const
{
    return d->datatype;
}

SharedDataSamplePtr DataSample::copy(const SharedDataSamplePtr &src)
{
    return SharedDataSamplePtr(new DataSample(src->d->content, src->d->datatype, src->d->timestamp));
}

SharedDataSamplePtr DataSample::make_shared(DataSample *sample)
{
    return SharedDataSamplePtr(sample);
}

void DataSample::registerMetaType()
{
    int id = qRegisterMetaType<QSharedPointer<const nexxT::DataSample> >();
}

int64_t DataSample::currentTime()
{
    using namespace std;
    static_assert(TIMESTAMP_RES_VALUE == 1e-6, "Assuming timestamps to be in microseconds.");
    return chrono::duration_cast<chrono::microseconds>(chrono::system_clock::now().time_since_epoch()).count();
}
