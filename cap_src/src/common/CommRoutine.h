//------------------------------------------------------------------------------
// CommRoutine.h
//------------------------------------------------------------------------------
#ifndef __COMM_ROUTINE_H__
#define __COMM_ROUTINE_H__

#ifdef _LINUX
#include "WinCompat.h"
#else
#include <windows.h>
#include <tchar.h>
#endif
#include <string>

#define MAX_DEBUG_OUTPUT_LENGTH     2048

#define DBG_PREFIX      _T("TC!") _T(__FUNCTION__) _T(":")

#ifdef _DEBUG
extern VOID DbgString(IN  LPCTSTR tracemsg, ...);
#else
#define DbgString(x, ...)
#endif

extern std::string GetHalfChar(std::string key);

#endif // __COMM_ROUTINE_H__
