/*
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

/**
    \file Compatibility.hpp
*/

#ifndef NEXXT_COMPATIBILITY_HPP
#define NEXXT_COMPATIBILITY_HPP

#include <QtGui/QAction>
#include <QtWidgets/QMenu>

#include "nexxT/NexxTLinkage.hpp"

//! @cond Doxygen_Suppress
namespace nexxT
{
    class DLLEXPORT Compatibility
    {
    public:
        // TODO: remove after https://bugreports.qt.io/browse/PYSIDE-1627 has been fixed
        static QMenu *getMenuFromAction(QAction *);
    };
};
//! @endcond

#endif
