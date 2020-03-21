/* 
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

#ifndef TESTEXCEPTIONFILTER_HPP
#define TESTEXCEPTIONFILTER_HPP

#include "Filters.hpp"
#include "Ports.hpp"
#include "NexTPlugins.hpp"

using namespace nexxT;

class TestExceptionFilter : public Filter
{
    SharedInputPortPtr port;
public:
    TestExceptionFilter(BaseFilterEnvironment *env);
    ~TestExceptionFilter();

    NEXT_PLUGIN_DECLARE_FILTER(TestExceptionFilter)

    void onInit();
    void onStart();
    void onPortDataChanged(const InputPortInterface &inputPort);
    void onStop();
    void onDeinit();
};

#endif // TESTEXCEPTIONFILTER_HPP
