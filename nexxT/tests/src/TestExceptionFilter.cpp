/* 
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

#include "TestExceptionFilter.hpp"
#include "PropertyCollection.hpp"

TestExceptionFilter::TestExceptionFilter(BaseFilterEnvironment *env)
    : Filter(false, false, env)
{
    propertyCollection()->defineProperty("whereToThrow", "nowhere", "one of nowhere,constructor,init,start,port,stop,deinit");
    if( propertyCollection()->getProperty("whereToThrow") == "constructor" )
    {
        throw std::runtime_error("exception in constructor");
    }
    port = SharedInputPortPtr(new InputPortInterface(false, "port", env, 1, -1.));
    addStaticPort(port);
}

TestExceptionFilter::~TestExceptionFilter()
{
    /*
     * c++11 has the convention to terminate() when destructors throw exceptions
     * we stick to this and do not support throwing exceptions in filter destructors.
     */
}


void TestExceptionFilter::onInit()
{
    if( propertyCollection()->getProperty("whereToThrow") == "init" )
    {
        throw std::runtime_error("exception in init");
    }
}

void TestExceptionFilter::onOpen()
{
    if( propertyCollection()->getProperty("whereToThrow") == "open" )
    {
        throw std::runtime_error("exception in open");
    }
}

void TestExceptionFilter::onStart()
{
    if( propertyCollection()->getProperty("whereToThrow") == "start" )
    {
        throw std::runtime_error("exception in start");
    }
}

void TestExceptionFilter::onPortDataChanged(const InputPortInterface &)
{
    if( propertyCollection()->getProperty("whereToThrow") == "port" )
    {
        throw std::runtime_error("exception in port");
    }
}

void TestExceptionFilter::onStop()
{
    if( propertyCollection()->getProperty("whereToThrow") == "stop" )
    {
        throw std::runtime_error("exception in stop");
    }
}

void TestExceptionFilter::onClose()
{
    if( propertyCollection()->getProperty("whereToThrow") == "close" )
    {
        throw std::runtime_error("exception in close");
    }
}

void TestExceptionFilter::onDeinit()
{
    if( propertyCollection()->getProperty("whereToThrow") == "deinit" )
    {
        throw std::runtime_error("exception in deinit");
    }
}

