#!/bin/sh
export NEXT_DISABLE_CIMPL=1
if test -z "$1"; then
  PYLINT=pylint
else
  PYLINT="$1"
fi
"$PYLINT" --rcfile=pylint.rc nexxT.core nexxT.interface nexxT.services nexxT.filters nexxT.examples
