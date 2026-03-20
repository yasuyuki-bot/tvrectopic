// CommRoutine.cpp
#include "CommRoutine.h"
#include <stdarg.h>
#include <stdio.h>

#ifdef _DEBUG
extern VOID DbgString(IN  LPCTSTR tracemsg, ...)
{
#ifdef _LINUX
    va_list ptr;
    va_start(ptr, tracemsg);
    vfprintf(stderr, tracemsg, ptr);
    va_end(ptr);
#else
    // Windows implementation omitted for now as this file was rewritten for Linux port
#endif
}
#endif

extern std::string GetHalfChar(std::string key)
{
    return key;
}
