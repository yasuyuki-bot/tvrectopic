//------------------------------------------------------------------------------
// Caption.h
//------------------------------------------------------------------------------
#ifndef __CAPTION_H__
#define __CAPTION_H__

#include "CaptionDef.h"

#ifdef __cplusplus
extern "C" {
#endif

#ifdef _LINUX

DWORD WINAPI InitializeCP(void);
DWORD WINAPI InitializeUNICODE(void);
DWORD WINAPI UnInitializeCP(void);
DWORD WINAPI AddTSPacketCP(BYTE *pbPacket);
DWORD WINAPI ClearCP(void);
DWORD WINAPI GetTagInfoCP(LANG_TAG_INFO_DLL **ppList, DWORD *pdwListCount);
DWORD WINAPI GetCaptionDataCP(unsigned char ucLangTag, CAPTION_DATA_DLL **ppList, DWORD *pdwListCount);

#else // Windows

#ifdef CAPTION_EXPORTS

__declspec(dllexport)
DWORD WINAPI InitializeCP(void);

__declspec(dllexport)
DWORD WINAPI InitializeUNICODE(void);

__declspec(dllexport)
DWORD WINAPI UnInitializeCP(void);

__declspec(dllexport)
DWORD WINAPI AddTSPacketCP(BYTE *pbPacket);

__declspec(dllexport)
DWORD WINAPI ClearCP(void);

__declspec(dllexport)
DWORD WINAPI GetTagInfoCP(LANG_TAG_INFO_DLL **ppList, DWORD *pdwListCount);

__declspec(dllexport)
DWORD WINAPI GetCaptionDataCP(unsigned char ucLangTag, CAPTION_DATA_DLL **ppList, DWORD *pdwListCount);

#else /* CAPTION_EXPORTS */

typedef DWORD (WINAPI *InitializeCP)(void);
typedef DWORD (WINAPI *InitializeUNICODECP)(void);
typedef DWORD (WINAPI *UnInitializeCP)(void);
typedef DWORD (WINAPI *AddTSPacketCP)(BYTE *pbPacket);
typedef DWORD (WINAPI *ClearCP)(void);
typedef DWORD (WINAPI *GetTagInfoCP)(LANG_TAG_INFO_DLL **ppList, DWORD *pdwListCount);
typedef DWORD (WINAPI *GetCaptionDataCP)(unsigned char ucLangTag, CAPTION_DATA_DLL **ppList, DWORD *pdwListCount);

#endif /* CAPTION_EXPORTS */

#endif // _LINUX

#ifdef __cplusplus
}
#endif

#endif // __CAPTION_H__
