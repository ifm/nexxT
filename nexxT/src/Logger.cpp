/* 
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

#include "nexxT/Logger.hpp"

using namespace nexxT;

namespace nexxT
{
    unsigned int Logging::loglevel;
    SharedQObjectPtr Logging::loggingService;

    void Logging::setLogLevel(unsigned int level)
    {
        loglevel = level;
    }

    void Logging::setLoggingService(const SharedQObjectPtr &service)
    {
        loggingService = service;
    }

    void Logging::_log(unsigned int level, const QString &message, const QString &file, unsigned int line)
    { 
        SharedQObjectPtr logger = loggingService;
        if( !logger.isNull() )
        {
            bool res = QMetaObject::invokeMethod(logger.get(), "log", Qt::DirectConnection, Q_ARG(int, level), Q_ARG(const QString &, message), Q_ARG(const QString &, file), Q_ARG(int, line));
            if(!res)
            {
                fprintf(stderr, "WARNING: invokeMetod returned false!\n");
            }
        } else
        {
            if( level >= NEXXT_LOG_LEVEL_INFO )
            {
                fprintf(stderr, "LOG: level=%d msg=%s file=%s line=%d\n", level, message.toStdString().c_str(), file.toStdString().c_str(), line);
            }
        }
    }
};
