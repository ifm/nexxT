/* 
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

/**
    \file Logger.hpp

    Macros for logging from the C++ world.
*/

#ifndef NEXXT_LOGGER_HPP
#define NEXXT_LOGGER_HPP

#include "Services.hpp"
#include "NexxTLinkage.hpp"
#include <QtCore/QMetaObject>

//! @cond Doxygen_Suppress
#define NEXXT_LOG_LEVEL_NOTSET 0
#define NEXXT_LOG_LEVEL_INTERNAL 5
#define NEXXT_LOG_LEVEL_DEBUG 10
#define NEXXT_LOG_LEVEL_INFO 20
#define NEXXT_LOG_LEVEL_WARN 30
#define NEXXT_LOG_LEVEL_ERROR 40
#define NEXXT_LOG_LEVEL_CRITICAL 50
//! @endcond

/*!
    Log msg using the nexxT mechanism with priority INTERNAL (lowest)

    \param msg QString instance
*/
#define NEXXT_LOG_INTERNAL(msg) nexxT::Logging::log(NEXXT_LOG_LEVEL_INTERNAL, msg, __FILE__, __LINE__)
/*!
    Log msg using the nexxT mechanism with priority DEBUG

    \param msg QString instance
*/
#define NEXXT_LOG_DEBUG(msg) nexxT::Logging::log(NEXXT_LOG_LEVEL_DEBUG, msg, __FILE__, __LINE__)
/*!
    Log msg using the nexxT mechanism with priority INFO

    \param msg QString instance
*/
#define NEXXT_LOG_INFO(msg) nexxT::Logging::log(NEXXT_LOG_LEVEL_INFO, msg, __FILE__, __LINE__)
/*!
    Log msg using the nexxT mechanism with priority WARNING

    \param msg QString instance
*/
#define NEXXT_LOG_WARN(msg) nexxT::Logging::log(NEXXT_LOG_LEVEL_WARN, msg, __FILE__, __LINE__)
/*!
    Log msg using the nexxT mechanism with priority ERROR

    \param msg QString instance
*/
#define NEXXT_LOG_ERROR(msg) nexxT::Logging::log(NEXXT_LOG_LEVEL_ERROR, msg, __FILE__, __LINE__)
/*!
    Log msg using the nexxT mechanism with priority CRITICAL (highest)

    \param msg QString instance
*/
#define NEXXT_LOG_CRITICAL(msg) nexxT::Logging::log(NEXXT_LOG_LEVEL_CRITICAL, msg, __FILE__, __LINE__)

//! @cond Doxygen_Suppress
namespace nexxT
{
    class DLLEXPORT Logging
    {
        static unsigned int loglevel;
        static void _log(unsigned int level, const QString &message, const QString &file, unsigned int line);
    public:
        static void setLogLevel(unsigned int level);
        static inline void log(unsigned int level, const QString &message, const QString &file, unsigned int line)
        {
            if( level >= loglevel )
            {
                _log(level, message, file, line);
            }
        }
    };
};
//! @endcond

#endif
