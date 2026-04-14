#!/usr/bin/env sh
set -eu

DM_HOME_PATH="${DM_HOME:-${1:-}}"
PYTHON_SOURCE_ROOT="${DM_PYTHON_SOURCE_ROOT:-${2:-}}"

if [ -z "$DM_HOME_PATH" ]; then
  echo "DM_HOME is not set. Export DM_HOME or pass the DM8 installation directory as the first argument." >&2
  exit 1
fi

if [ -z "$PYTHON_SOURCE_ROOT" ]; then
  PYTHON_SOURCE_ROOT="$DM_HOME_PATH/drivers/python"
fi

if [ -d "$PYTHON_SOURCE_ROOT/python" ]; then
  PYTHON_SOURCE_ROOT="$PYTHON_SOURCE_ROOT/python"
fi

runtime_found=0
for runtime_lib in \
  "$DM_HOME_PATH/libdmdpi.so" \
  "$DM_HOME_PATH/bin/libdmdpi.so" \
  "$DM_HOME_PATH/dpi/libdmdpi.so" \
  "$DM_HOME_PATH/drivers/dpi/libdmdpi.so"
do
  if [ -f "$runtime_lib" ]; then
    runtime_found=1
    break
  fi
done

if [ "$runtime_found" -ne 1 ]; then
  echo "DM runtime library libdmdpi.so not found under $DM_HOME_PATH. Place the Linux DM8 runtime/client files under backend/vendor/dm or set DM_HOME correctly." >&2
  exit 1
fi

include_found=0
for include_dir in \
  "$DM_HOME_PATH/include" \
  "$DM_HOME_PATH/dpi/include" \
  "$DM_HOME_PATH/dpi/src/include" \
  "$DM_HOME_PATH/drivers/python/dmPython"
do
  if [ -d "$include_dir" ]; then
    include_found=1
    break
  fi
done

if [ "$include_found" -ne 1 ]; then
  echo "DM include headers not found under $DM_HOME_PATH. dmPython requires include or dpi/include headers during build." >&2
  exit 1
fi

for package in \
  "$PYTHON_SOURCE_ROOT/dmPython" \
  "$PYTHON_SOURCE_ROOT/dmAsync" \
  "$PYTHON_SOURCE_ROOT/dmSQLAlchemy/dmSQLAlchemy2.0"
do
  if [ ! -d "$package" ]; then
    echo "Driver package not found: $package" >&2
    exit 1
  fi

  echo "Installing $package"
  python -m pip install "$package"
done
