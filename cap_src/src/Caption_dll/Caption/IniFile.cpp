//------------------------------------------------------------------------------
// IniFile.cpp
//------------------------------------------------------------------------------

#include "stdafx.h"

#include "CaptionDef.h"
#include "ColorDef.h"
#include "ARIB8CharDecode.h"
#include "IniFile.h"
#include "ARIBGaiji.h"

static const string iniFilename   = "cc_DRCS.ini";
static const string iniFilenameU  = "UNICODE_cc_DRCS.ini";
static const string iniFileARIB   = "cc_gaiji.ini";
static const string iniFileARIBU  = "UNICODE_cc_gaiji.ini";
static const string iniFileARIB2  = "cc_gaiji2.ini";
static const string iniFileARIB2U = "UNICODE_cc_gaiji2.ini";

BOOL IniFile::ReadIni(void)
{
    CARIB8CharDecode ARIB8CharDecode;
#ifdef _LINUX
    string separator = "";
    string dir_separator = "/";
#else
    string separator = "";
    string dir_separator = "\\";
#endif
    string tmpFilename = ARIB8CharDecode.GetAppPath() + separator + "Gaiji" + dir_separator + iniFilename;
    FILE *fpini = NULL;
    if (fopen_s(&fpini, tmpFilename.c_str(), "rt") || !fpini)
        return FALSE;
    string tmprl;
    CHAR strSJIS[STRING_BUFFER_SIZE] = { 0 };
    WCHAR wStr[STRING_BUFFER_SIZE] = { 0 };
    CHAR strUTF8[STRING_BUFFER_SIZE] = { 0 };

    do {
        if (!fgets(strSJIS, STRING_BUFFER_SIZE, fpini)) break;
#ifdef _LINUX
        MultiByteToWideChar(932, 0, strSJIS, -1, wStr, STRING_BUFFER_SIZE);
        WideCharToMultiByte(CP_UTF8, 0, wStr, -1, strUTF8, STRING_BUFFER_SIZE, NULL, NULL);
        tmprl = strUTF8;
#else
        tmprl = strSJIS;
#endif
        // Trim newline
        while (!tmprl.empty() && (tmprl.back() == '\n' || tmprl.back() == '\r')) {
            tmprl.pop_back();
        }
    } while ((tmprl != "[外字代用文字]") && (!feof(fpini)));

    do {
        if (!fgets(strSJIS, STRING_BUFFER_SIZE, fpini)) break;
#ifdef _LINUX
        MultiByteToWideChar(932, 0, strSJIS, -1, wStr, STRING_BUFFER_SIZE);
        WideCharToMultiByte(CP_UTF8, 0, wStr, -1, strUTF8, STRING_BUFFER_SIZE, NULL, NULL);
        tmprl = strUTF8;
#else
        tmprl = strSJIS;
#endif
        while (!tmprl.empty() && (tmprl.back() == '\n' || tmprl.back() == '\r')) {
            tmprl.pop_back();
        }

        size_t iPos = tmprl.find_first_of("=");
        if (iPos != string::npos)
            if (iPos == 32) {
                string tmpKey = tmprl.substr(0, iPos);
                string tmpArg = tmprl.substr(iPos + 1);
                ARIB8CharDecode.Add_dicHash_Char(tmpKey, tmpArg);
            }
    } while ((tmprl != "[外字分解]") && (!feof(fpini)));
    fclose(fpini);
    return TRUE;
}

BOOL IniFile::ReadIniARIB(void)
{
    CARIB8CharDecode ARIB8CharDecode;
#ifdef _LINUX
    string separator = "";
    string dir_separator = "/";
#else
    string separator = "";
    string dir_separator = "\\";
#endif
    string tmpFilename = ARIB8CharDecode.GetAppPath() + separator + "Gaiji" + dir_separator + iniFileARIB;
    FILE *fpini = NULL;
    if (fopen_s(&fpini, tmpFilename.c_str(), "rt") || !fpini)
        return FALSE;
    string tmprl;
    CHAR strSJIS[STRING_BUFFER_SIZE] = { 0 };
    WCHAR wStr[STRING_BUFFER_SIZE] = { 0 };
    CHAR strUTF8[STRING_BUFFER_SIZE] = { 0 };

    do {
        if (!fgets(strSJIS, STRING_BUFFER_SIZE, fpini)) break;
#ifdef _LINUX
        MultiByteToWideChar(932, 0, strSJIS, -1, wStr, STRING_BUFFER_SIZE);
        WideCharToMultiByte(CP_UTF8, 0, wStr, -1, strUTF8, STRING_BUFFER_SIZE, NULL, NULL);
        tmprl = strUTF8;
#else
        tmprl = strSJIS;
#endif
        while (!tmprl.empty() && (tmprl.back() == '\n' || tmprl.back() == '\r')) {
            tmprl.pop_back();
        }
    } while ((tmprl != "[ARIB外字代用文字]") && (!feof(fpini)));
    int iGaijiCtr = 0;
    do {
        if (!fgets(strSJIS, STRING_BUFFER_SIZE, fpini)) break;
#ifdef _LINUX
        MultiByteToWideChar(932, 0, strSJIS, -1, wStr, STRING_BUFFER_SIZE);
        WideCharToMultiByte(CP_UTF8, 0, wStr, -1, strUTF8, STRING_BUFFER_SIZE, NULL, NULL);
        tmprl = strUTF8;
#else
        tmprl = strSJIS;
#endif
        while (!tmprl.empty() && (tmprl.back() == '\n' || tmprl.back() == '\r')) {
            tmprl.pop_back();
        }

        size_t iPos = tmprl.find_first_of("=");
        if (iPos != string::npos)
            if ((iPos == 4) && (iGaijiCtr < ARIB_MAX)) {
                GaijiTable[iGaijiCtr].usARIB8 = tmprl.substr(0, iPos);
                GaijiTable[iGaijiCtr].strChar = tmprl.substr(iPos + 1);
                iGaijiCtr += 1;
            }
    } while ((tmprl != "[ARIB外字分解]") && (!feof(fpini)));
    fclose(fpini);
    fpini = NULL;

    tmpFilename = ARIB8CharDecode.GetAppPath() + separator + "Gaiji" + dir_separator + iniFileARIB2;
    if (fopen_s(&fpini, tmpFilename.c_str(), "rt") || !fpini)
        return FALSE;
    do {
        if (!fgets(strSJIS, STRING_BUFFER_SIZE, fpini)) break;
#ifdef _LINUX
        MultiByteToWideChar(932, 0, strSJIS, -1, wStr, STRING_BUFFER_SIZE);
        WideCharToMultiByte(CP_UTF8, 0, wStr, -1, strUTF8, STRING_BUFFER_SIZE, NULL, NULL);
        tmprl = strUTF8;
#else
        tmprl = strSJIS;
#endif
        while (!tmprl.empty() && (tmprl.back() == '\n' || tmprl.back() == '\r')) {
            tmprl.pop_back();
        }
    } while ((tmprl != "[ARIB外字・代用文字]") && (!feof(fpini)));
    int iGaijiCtr2 = 0;
    do {
        if (!fgets(strSJIS, STRING_BUFFER_SIZE, fpini)) break;
#ifdef _LINUX
        MultiByteToWideChar(932, 0, strSJIS, -1, wStr, STRING_BUFFER_SIZE);
        WideCharToMultiByte(CP_UTF8, 0, wStr, -1, strUTF8, STRING_BUFFER_SIZE, NULL, NULL);
        tmprl = strUTF8;
#else
        tmprl = strSJIS;
#endif
        while (!tmprl.empty() && (tmprl.back() == '\n' || tmprl.back() == '\r')) {
            tmprl.pop_back();
        }

        size_t iPos = tmprl.find_first_of("=");
        if (iPos != string::npos)
            if ((iPos == 3) && (iGaijiCtr2 < ARIB_MAX2)) {
                GaijiTbl2[iGaijiCtr2].usARIB8 = tmprl.substr(0, iPos);
                GaijiTbl2[iGaijiCtr2].strChar = tmprl.substr(iPos + 1);
                iGaijiCtr2 += 1;
            }
    } while ((tmprl != "[ARIB外字・出力]") && (!feof(fpini)));
    fclose(fpini);
    return TRUE;
}

BOOL IniFile::ReadIniUNICODE(void)
{
    CARIB8CharDecode ARIB8CharDecode;
#ifdef _LINUX
    string separator = "";
    string dir_separator = "/";
#else
    string separator = "";
    string dir_separator = "\\";
#endif
    string tmpFilename = ARIB8CharDecode.GetAppPath() + separator + "Gaiji" + dir_separator + iniFilenameU;
    FILE *fpini = NULL;
    if (fopen_s(&fpini, tmpFilename.c_str(), "rb") || !fpini)
        return FALSE;

    unsigned char utf16bom[2];
    utf16bom[0] = (char)fgetc(fpini);
    utf16bom[1] = (char)fgetc(fpini);
    if (utf16bom[0] == 0xFF && utf16bom[1] == 0xFE) {
    } else {
        int result = fseek(fpini, 0, SEEK_SET);
        if (result)
            return FALSE;
    }
    string tmprl;
    WCHAR str[STRING_BUFFER_SIZE]    = { 0 };
    CHAR strUTF8[STRING_BUFFER_SIZE] = { 0 };
    string tmpUTF8;
    do {
        if (!fgetws(str, STRING_BUFFER_SIZE, fpini)) break;
        size_t len = wcslen(str);
        if (len > 0 && str[len - 1] == L'\n') str[len - 1] = 0;
        if (len > 1 && str[len - 2] == L'\r') str[len - 2] = 0;
        
        WideCharToMultiByte(CP_UTF8, 0, str, -1, strUTF8, STRING_BUFFER_SIZE, NULL, NULL);
        tmprl = strUTF8;
    } while ((tmprl != "[外字代用文字]") && (!feof(fpini)));

    do {
        if (!fgetws(str, STRING_BUFFER_SIZE, fpini)) break;
        size_t len = wcslen(str);
        if (len > 0 && str[len - 1] == L'\n') str[len - 1] = 0;
        if (len > 1 && str[len - 2] == L'\r') str[len - 2] = 0;

        WideCharToMultiByte(CP_UTF8, 0, str, -1, strUTF8, STRING_BUFFER_SIZE, NULL, NULL);
        tmprl = strUTF8;
        tmpUTF8 = strUTF8;
        size_t iPos = tmpUTF8.find_first_of("=");
        if (iPos != string::npos)
            if (iPos == 32) {
                string tmpKey = tmpUTF8.substr(0, iPos);
                string tmpArg = tmpUTF8.substr(iPos + 1);
                ARIB8CharDecode.Add_dicHash_Char(tmpKey,  tmpArg);
            }
    } while ((tmprl != "[外字分解]") && (!feof(fpini)));
    fclose(fpini);
    return TRUE;
}

BOOL IniFile::ReadIniARIBUNICODE(void)
{
    CARIB8CharDecode ARIB8CharDecode;
#ifdef _LINUX
    string separator = "";
    string dir_separator = "/";
#else
    string separator = "";
    string dir_separator = "\\";
#endif
    string tmpFilename = ARIB8CharDecode.GetAppPath() + separator + "Gaiji" + dir_separator + iniFileARIBU;
    FILE *fpini = NULL;
    if (fopen_s(&fpini, tmpFilename.c_str(), "rb") || !fpini)
        return FALSE;

    unsigned char utf16bom[2];
    utf16bom[0] = (char)fgetc(fpini);
    utf16bom[1] = (char)fgetc(fpini);
    if (utf16bom[0] == 0xFF && utf16bom[1] == 0xFE) {
    } else {
        int result = fseek(fpini, 0, SEEK_SET);
        if (result)
            return FALSE;
    }
    string tmprl;
    WCHAR str[STRING_BUFFER_SIZE]    = { 0 };
    CHAR strUTF8[STRING_BUFFER_SIZE] = { 0 };
    string tmpUTF8;
    do {
        if (!fgetws(str, STRING_BUFFER_SIZE, fpini)) break;
        size_t len = wcslen(str);
        if (len > 0 && str[len - 1] == L'\n') str[len - 1] = 0;
        if (len > 1 && str[len - 2] == L'\r') str[len - 2] = 0;

        WideCharToMultiByte(CP_UTF8, 0, str, -1, strUTF8, STRING_BUFFER_SIZE, NULL, NULL);
        tmprl = strUTF8;
    } while ((tmprl != "[ARIB外字代用文字]") && (!feof(fpini)));
    int iGaijiCtr = 0;
    do {
        if (!fgetws(str, STRING_BUFFER_SIZE, fpini)) break;
        size_t len = wcslen(str);
        if (len > 0 && str[len - 1] == L'\n') str[len - 1] = 0;
        if (len > 1 && str[len - 2] == L'\r') str[len - 2] = 0;

        WideCharToMultiByte(CP_UTF8, 0, str, -1, strUTF8, STRING_BUFFER_SIZE, NULL, NULL);
        tmprl = strUTF8;
        tmpUTF8 = strUTF8;
        size_t iPos = tmpUTF8.find_first_of("=");
        if (iPos != string::npos)
            if ((iPos == 4) && (iGaijiCtr < ARIB_MAX)) {
                GaijiTable[iGaijiCtr].usARIB8 = tmpUTF8.substr(0, iPos);
                GaijiTable[iGaijiCtr].strChar = tmpUTF8.substr(iPos + 1);
                iGaijiCtr += 1;
            }
    } while ((tmprl != "[ARIB外字分解]") && (!feof(fpini)));
    fclose(fpini);
    fpini = NULL;

    tmpFilename = ARIB8CharDecode.GetAppPath() + separator + "Gaiji" + dir_separator + iniFileARIB2U;
    if (fopen_s(&fpini, tmpFilename.c_str(), "rb") || !fpini)
        return FALSE;

    utf16bom[0] = (char)fgetc(fpini);
    utf16bom[1] = (char)fgetc(fpini);
    if (utf16bom[0] == 0xFF && utf16bom[1] == 0xFE) {
    } else {
        int result = fseek(fpini, 0, SEEK_SET);
        if (result)
            return FALSE;
    }
    do {
        if (!fgetws(str, STRING_BUFFER_SIZE, fpini)) break;
        size_t len = wcslen(str);
        if (len > 0 && str[len - 1] == L'\n') str[len - 1] = 0;
        if (len > 1 && str[len - 2] == L'\r') str[len - 2] = 0;

        WideCharToMultiByte(CP_UTF8, 0, str, -1, strUTF8, STRING_BUFFER_SIZE, NULL, NULL);
        tmprl = strUTF8;
    } while ((tmprl != "[ARIB外字・代用文字]") && (!feof(fpini)));
    int iGaijiCtr2 = 0;
    do {
        if (!fgetws(str, STRING_BUFFER_SIZE, fpini)) break;
        size_t len = wcslen(str);
        if (len > 0 && str[len - 1] == L'\n') str[len - 1] = 0;
        if (len > 1 && str[len - 2] == L'\r') str[len - 2] = 0;

        WideCharToMultiByte(CP_UTF8, 0, str, -1, strUTF8, STRING_BUFFER_SIZE, NULL, NULL);
        tmprl = strUTF8;
        tmpUTF8 = strUTF8;
        size_t iPos = tmpUTF8.find_first_of("=");
        if (iPos != string::npos)
            if ((iPos == 3) && (iGaijiCtr2 < ARIB_MAX2)) {
                GaijiTbl2[iGaijiCtr2].usARIB8 = tmpUTF8.substr(0, iPos);
                GaijiTbl2[iGaijiCtr2].strChar = tmpUTF8.substr(iPos + 1);
                iGaijiCtr2 += 1;
            }
    } while ((tmprl != "[ARIB外字・出力]") && (!feof(fpini)));
    fclose(fpini);
    return TRUE;
}
