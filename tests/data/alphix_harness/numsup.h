/* Stub for the alphix test harness: error() prints "ERR ..." and exits. */
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
static void error(char *fmt, ...) { va_list a; va_start(a, fmt); printf("ERR "); vprintf(fmt, a); printf("\n"); va_end(a); exit(0);}
