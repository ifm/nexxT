/* 
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

#include "DataSamples.hpp"
#include "Logger.hpp"
#include <chrono>
#include <atomic>

using namespace nexxT;

static constexpr double TIMESTAMP_RES_VALUE = 1e-6;
const double DataSample::TIMESTAMP_RES = TIMESTAMP_RES_VALUE;
static std::atomic_uint instanceCounter(0);
static std::atomic_size_t memoryHeld(0);

namespace nexxT
{
    struct DataSampleD
    {
        QByteArray content;
        QString datatype;
        int64_t timestamp;
    };
};

DataSample::DataSample(const QByteArray &content, const QString &datatype, int64_t timestamp) :
    d(new DataSampleD{content,datatype,timestamp})
{
    instanceCounter++;
    memoryHeld += d->content.size();
    NEXXT_LOG_INTERNAL(QString("DataSample::DataSample (numInstances=%1, memory=%2 MB)").arg(instanceCounter).arg(memoryHeld/(1024*1024)));
}

DataSample::~DataSample() 
{
    instanceCounter--;
    memoryHeld -= d->content.size();
    NEXXT_LOG_INTERNAL(QString("DataSample::~DataSample (numInstances=%1, memory=%2 MB)").arg(instanceCounter).arg(memoryHeld/(1024*1024)));
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
    qRegisterMetaType<QSharedPointer<const nexxT::DataSample> >();
}

int64_t DataSample::currentTime()
{
    using namespace std;
    static_assert(TIMESTAMP_RES_VALUE == 1e-6, "Assuming timestamps to be in microseconds.");
    return chrono::duration_cast<chrono::microseconds>(chrono::system_clock::now().time_since_epoch()).count();
}
