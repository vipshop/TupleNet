#                                               -*- Autoconf -*-
# Process this file with autoconf to produce a configure script.
AC_PREREQ([2.69])
AC_INIT([FULL-PACKAGE-NAME], [VERSION], [BUG-REPORT-ADDRESS])
AC_CONFIG_SRCDIR([ovs_side_func_dec.h])
AC_CONFIG_HEADERS([config.h])
AM_INIT_AUTOMAKE([-Wall -Werror foreign])
AC_USE_SYSTEM_EXTENSIONS
AC_PROG_RANLIB

# Checks for programs.
AC_PROG_CC

# Checks for libraries.
# FIXME: Replace `main' with a function in `-lcrypto':
AC_CHECK_LIB([crypto], [main])
# FIXME: Replace `main' with a function in `-lm':
AC_CHECK_LIB([m], [main])
# FIXME: Replace `main' with a function in ` -lofproto':
AC_CHECK_LIB([ofproto], [main], [], [AC_MSG_ERROR([cannot found libofproto])])
# FIXME: Replace `main' with a function in `-lopenvswitch':
AC_CHECK_LIB([openvswitch], [main], [], [AC_MSG_ERROR([cannot found libopenvswitch])])
# FIXME: Replace `main' with a function in `-lovsdb':
AC_CHECK_LIB([ovsdb], [main], [], [AC_MSG_ERROR([cannot found libovsdb])])
# FIXME: Replace `main' with a function in `-lpthread':
AC_CHECK_LIB([pthread], [pthread_rwlock_init])
# FIXME: Replace `main' with a function in `-lrt':
AC_CHECK_LIB([rt], [main])
# FIXME: Replace `main' with a function in `-lsflow':
AC_CHECK_LIB([sflow], [main], [], [AC_MSG_ERROR([cannot found libsflow])])
# FIXME: Replace `main' with a function in `-lssl':
AC_CHECK_LIB([ssl], [main])
# FIXME: Replace `main' with a function in `-lunbound':
AC_CHECK_LIB([unbound], [main])

# Checks for header files.
AC_CHECK_HEADERS([arpa/inet.h fcntl.h limits.h sys/time.h unistd.h])
AC_CHECK_HEADERS([openvswitch/ofp-packet.h openvswitch/ofp-switch.h openvswitch/rconn.h])

AC_CHECK_FUNCS([ofputil_encode_set_packet_in_format ofputil_encode_echo_reply])

# Checks for typedefs, structures, and compiler characteristics.
AC_CHECK_HEADER_STDBOOL
AC_C_INLINE
AC_TYPE_SIZE_T
AC_TYPE_UINT32_T
AC_TYPE_UINT64_T
AC_TYPE_UINT8_T

# Checks for library functions.
AC_FUNC_STRNLEN
AC_CHECK_FUNCS([gettimeofday memset mkfifo])

AC_CONFIG_FILES([Makefile])
AC_OUTPUT
