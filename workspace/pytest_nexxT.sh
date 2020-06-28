#!/bin/sh
if test -z "$1"; then
  PYTEST=pytest
else
  PYTEST="$1"
fi

ADD_FLAGS=""

                      "$PYTEST" $ADD_FLAGS              --cov=nexxT.core --cov=nexxT.interface --cov=nexxT.services --cov=nexxT.filters --cov-report html ../nexxT/tests
NEXXT_VARIANT=nonopt  "$PYTEST" $ADD_FLAGS --cov-append --cov=nexxT.core --cov=nexxT.interface --cov=nexxT.services --cov=nexxT.filters --cov-report html ../nexxT/tests
NEXXT_DISABLE_CIMPL=1 "$PYTEST" $ADD_FLAGS --cov-append --cov=nexxT.core --cov=nexxT.interface --cov=nexxT.services --cov=nexxT.filters --cov-report html ../nexxT/tests
