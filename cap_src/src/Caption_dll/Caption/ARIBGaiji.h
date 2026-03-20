//------------------------------------------------------------------------------
// ARIBGaiji.h
//------------------------------------------------------------------------------
#ifndef __ARIB_GAIJI_H__
#define __ARIB_GAIJI_H__

#include <string>

#ifdef GLOBAL
#define EXTERN
#else
#define EXTERN extern
#endif

// ARIB縺ｮ霑ｽ蜉險伜捷 ・・霑ｽ蜉貍｢蟄励・繝・・繝悶Ν螳夂ｾｩ
// 螳滉ｽ薙・縲√靴aptionMain.cpp縲阪〒螳｣險

#define ARIB_MAX        495
#define ARIB_MAX2       137

typedef struct _GAIJI_TABLE {
    string usARIB8;
    string strChar;
} GAIJI_TABLE;

EXTERN GAIJI_TABLE GaijiTable[ARIB_MAX];

EXTERN GAIJI_TABLE GaijiTbl2[ARIB_MAX2];

EXTERN BOOL m_bUnicode;

#endif // __ARIB_GAIJI_H__
