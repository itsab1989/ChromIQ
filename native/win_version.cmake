# chromiq_add_win_version(<target> <description> <copyright>)
#
# Windows only: compiles native/win_version.rc.in into <target>, giving the
# .exe a VERSIONINFO (CompanyName, FileDescription, ProductName, versions from
# core/version.py, OriginalFilename). Does nothing on macOS and Linux.
set(_CHROMIQ_WIN_VERSION_DIR "${CMAKE_CURRENT_LIST_DIR}")  # 3.15: no CMAKE_CURRENT_FUNCTION_LIST_DIR
if(WIN32)
  enable_language(RC)  # file scope only, not inside the function
endif()

function(chromiq_add_win_version target description copyright)
  if(NOT WIN32)
    return()
  endif()
  set(_root "${_CHROMIQ_WIN_VERSION_DIR}/..")
  # Re-run the configure step when the version moves (local rebuilds).
  set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${_root}/core/version.py")
  file(STRINGS "${_root}/core/version.py" _line REGEX "^APP_VERSION *= *\"")
  string(REGEX REPLACE "^APP_VERSION *= *\"([^\"]+)\".*" "\\1" CHROMIQ_VER "${_line}")
  if(NOT CHROMIQ_VER)
    message(FATAL_ERROR "could not read APP_VERSION from core/version.py")
  endif()
  string(REGEX REPLACE "-.*$" "" _nums "${CHROMIQ_VER}")
  string(REPLACE "." ";" _parts "${_nums}")
  list(APPEND _parts 0 0 0 0)
  list(SUBLIST _parts 0 4 _parts)
  string(JOIN "," CHROMIQ_VER_COMMA ${_parts})
  set(CHROMIQ_RC_NAME "${target}")
  set(CHROMIQ_RC_DESCRIPTION "${description}")
  set(CHROMIQ_RC_COPYRIGHT "${copyright}")
  set(_rc "${CMAKE_CURRENT_BINARY_DIR}/${target}_version.rc")
  configure_file("${_CHROMIQ_WIN_VERSION_DIR}/win_version.rc.in" "${_rc}" @ONLY)
  target_sources(${target} PRIVATE "${_rc}")
endfunction()
