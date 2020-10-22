/* 
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

#ifndef NEXXT_LINKAGE_HPP
#define NEXXT_LINKAGE_HPP

# ifdef __GNUC__
#  define FORCE_DLLEXPORT __attribute__ ((visibility("default")))
# else
#  define FORCE_DLLEXPORT  __declspec(dllexport)
# endif

#ifdef NEXXT_LIBRARY_COMPILATION

# define DLLEXPORT FORCE_DLLEXPORT

#else

# ifdef __GNUC__
#  define DLLEXPORT 
# else
#  define DLLEXPORT __declspec(dllimport)
# endif

#endif

#endif
