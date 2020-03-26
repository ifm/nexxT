/* 
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

#ifndef NEXT_LINKAGE_HPP
#define NEXT_LINKAGE_HPP

# ifdef __GNUC__
#  define FORCE_DLLEXPORT __attribute__ ((visibility("default")))
# else
#  define FORCE_DLLEXPORT  __declspec(dllexport)
# endif

#ifdef NEXT_LIBRARY_COMPILATION

# define DLLEXPORT FORCE_DLLEXPORT

#else

# ifdef __GNUC__
#  define DLLEXPORT 
# else
#  define DLLEXPORT __declspec(dllimport)
# endif

#endif

#endif
