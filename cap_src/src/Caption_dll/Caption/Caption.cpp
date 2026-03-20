//------------------------------------------------------------------------------
// Caption.cpp : DLL 繧｢繝励Μ繧ｱ繝ｼ繧ｷ繝ｧ繝ｳ逕ｨ縺ｫ繧ｨ繧ｯ繧ｹ繝昴・繝医＆繧後ｋ髢｢謨ｰ繧貞ｮ夂ｾｩ縺励∪縺吶€・
//------------------------------------------------------------------------------
#pragma warning(disable: 4100)

#include "stdafx.h"

#include "CaptionDef.h"
#include "ColorDef.h"
#include "ARIB8CharDecode.h"
#include "CaptionMain.h"
#include "Caption.h"

static CCaptionMain *g_sys = NULL;

static __inline DWORD initialize(BOOL bUNICODE)
{
    if (g_sys || (g_sys = new CCaptionMain(bUNICODE)) == NULL)
        return ERR_INIT;
    return NO_ERR;
}

static __inline void uninitialize(void)
{
    if (!g_sys)
        return;
    delete g_sys;
    g_sys = NULL;
}

#ifndef _LINUX
BOOL APIENTRY DllMain(HMODULE hModule, DWORD ul_reason_for_call, LPVOID lpReserved)
{
    switch (ul_reason_for_call)
    {
    case DLL_PROCESS_ATTACH:
        g_sys = NULL;
        break;
    case DLL_PROCESS_DETACH:
        uninitialize();
        break;
    case DLL_THREAD_ATTACH:
    case DLL_THREAD_DETACH:
    default:
        break;
    }
    return TRUE;
}
#endif

//DLL縺ｮ蛻晄悄蛹・
//謌ｻ繧雁€､・壹お繝ｩ繝ｼ繧ｳ繝ｼ繝・
DWORD WINAPI InitializeCP(void)
{
    return initialize(FALSE);
}

//DLL縺ｮ蛻晄悄蛹・UNICODE蟇ｾ蠢・
//謌ｻ繧雁€､・壹お繝ｩ繝ｼ繧ｳ繝ｼ繝・
DWORD WINAPI InitializeUNICODE(void)
{
    return initialize(TRUE);
}

//DLL縺ｮ髢区叛
//謌ｻ繧雁€､・壹お繝ｩ繝ｼ繧ｳ繝ｼ繝・
DWORD WINAPI UnInitializeCP(void)
{
    uninitialize();
    return NO_ERR;
}

DWORD WINAPI AddTSPacketCP(BYTE *pbPacket)
{
    if (!g_sys)
        return ERR_NOT_INIT;
    return g_sys->AddTSPacket(pbPacket);
}

DWORD WINAPI ClearCP(void)
{
    if (!g_sys)
        return ERR_NOT_INIT;
    return g_sys->Clear();
}

DWORD WINAPI GetTagInfoCP(LANG_TAG_INFO_DLL **ppList, DWORD *pdwListCount)
{
    if (!g_sys)
        return ERR_NOT_INIT;
    return g_sys->GetTagInfo(ppList, pdwListCount);
}

DWORD WINAPI GetCaptionDataCP(unsigned char ucLangTag, CAPTION_DATA_DLL **ppList, DWORD *pdwListCount)
{
    if (!g_sys)
        return ERR_NOT_INIT;
    return g_sys->GetCaptionData(ucLangTag, ppList, pdwListCount);
}
