//------------------------------------------------------------------------------
// cmdline.h
//------------------------------------------------------------------------------
#ifndef __CMD_LINE_H__
#define __CMD_LINE_H__

#include <stdlib.h>
#ifndef _LINUX
#include <tchar.h>
#endif

#include "Caption2Ass_PCR.h"

extern int ParseCmd(int argc, TCHAR **argv, CCaption2AssParameter *param);
#ifndef _LINUX
extern void _tMyPrintf(IN  LPCTSTR tracemsg, ...);
#endif

#endif // __CMD_LINE_H__
