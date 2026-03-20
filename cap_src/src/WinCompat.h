#ifndef WINCOMPAT_H
#define WINCOMPAT_H

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <stdint.h>
#include <wchar.h>
#include <iconv.h>
#include <errno.h>
#include <unistd.h>

typedef uint8_t BYTE;
typedef uint16_t WORD;
typedef uint32_t DWORD;
typedef int BOOL;
typedef wchar_t WCHAR;
typedef char CHAR;
typedef char TCHAR;
typedef const char* LPCTSTR;
typedef const char* LPCSTR;
typedef char* LPSTR;
typedef unsigned int UINT;
typedef unsigned int* PUINT;
typedef unsigned short USHORT;
typedef unsigned long ULONG;
typedef long LONG;
typedef int INT;
typedef void* HMODULE;
typedef void* LPVOID;
typedef int64_t __int64;

#define TRUE 1
#define FALSE 0

typedef struct tagBITMAPINFOHEADER {
  DWORD biSize;
  LONG  biWidth;
  LONG  biHeight;
  WORD  biPlanes;
  WORD  biBitCount;
  DWORD biCompression;
  DWORD biSizeImage;
  LONG  biXPelsPerMeter;
  LONG  biYPelsPerMeter;
  DWORD biClrUsed;
  DWORD biClrImportant;
} BITMAPINFOHEADER, *PBITMAPINFOHEADER;

typedef struct tagRGBQUAD {
  BYTE rgbBlue;
  BYTE rgbGreen;
  BYTE rgbRed;
  BYTE rgbReserved;
} RGBQUAD;

#pragma pack(push, 2)
typedef struct tagBITMAPFILEHEADER {
  WORD  bfType;
  DWORD bfSize;
  WORD  bfReserved1;
  WORD  bfReserved2;
  DWORD bfOffBits;
} BITMAPFILEHEADER, *PBITMAPFILEHEADER;
#pragma pack(pop)

typedef void *HANDLE;
#define INVALID_HANDLE_VALUE ((HANDLE)-1)
#define GENERIC_WRITE 0x40000000
#define CREATE_NEW 1
#define FILE_ATTRIBUTE_NORMAL 0x80
#define BI_RGB 0

inline HANDLE CreateFile(const void* lpFileName, DWORD dwDesiredAccess, DWORD dwShareMode, void* lpSecurityAttributes, DWORD dwCreationDisposition, DWORD dwFlagsAndAttributes, void* hTemplateFile) {
    return INVALID_HANDLE_VALUE;
}

inline BOOL WriteFile(HANDLE hFile, const void* lpBuffer, DWORD nNumberOfBytesToWrite, DWORD* lpNumberOfBytesWritten, void* lpOverlapped) {
    if (lpNumberOfBytesWritten) *lpNumberOfBytesWritten = 0;
    return FALSE;
}

inline BOOL CloseHandle(HANDLE hObject) {
    return TRUE;
}

#define IN


#define _fseeki64 fseeko
#define _ftelli64 ftello

#define _T(x) x
#define _tmain main
#define _TCHAR char
#define LPWSTR wchar_t*
#define LPCWSTR const wchar_t*

#define CP_ACP 0
#define CP_OEMCP 1
#define CP_THREAD_ACP 3
#define CP_UTF8 65001

inline int MultiByteToWideChar(UINT CodePage, DWORD dwFlags, LPCSTR lpMultiByteStr, int cbMultiByte, LPWSTR lpWideCharStr, int cchWideChar) {
    if (!lpMultiByteStr) return 0;
    
    static iconv_t cd_cp932 = (iconv_t)-1;
    static iconv_t cd_utf8 = (iconv_t)-1;
    static iconv_t cd_ascii = (iconv_t)-1;
    
    iconv_t cd = (iconv_t)-1;
    
    if (CodePage == 932 || CodePage == 3) {
        if (cd_cp932 == (iconv_t)-1) cd_cp932 = iconv_open("WCHAR_T", "CP932");
        cd = cd_cp932;
    } else if (CodePage == CP_UTF8) {
        if (cd_utf8 == (iconv_t)-1) cd_utf8 = iconv_open("WCHAR_T", "UTF-8");
        cd = cd_utf8;
    } else {
        if (cd_ascii == (iconv_t)-1) cd_ascii = iconv_open("WCHAR_T", "ASCII");
        cd = cd_ascii;
    }

    if (cd == (iconv_t)-1) return 0;
    
    // Reset state
    iconv(cd, NULL, NULL, NULL, NULL);

    size_t inbytesleft = (cbMultiByte == -1) ? strlen(lpMultiByteStr) : cbMultiByte;
    size_t outbytesleft = cchWideChar * sizeof(wchar_t);
    char* inptr = (char*)lpMultiByteStr;
    char* outptr = (char*)lpWideCharStr;

    size_t res = iconv(cd, &inptr, &inbytesleft, &outptr, &outbytesleft);

    if (res == (size_t)-1) return 0;
    // Return number of wide characters written
    return cchWideChar - (outbytesleft / sizeof(wchar_t));
}

inline int WideCharToMultiByte(UINT CodePage, DWORD dwFlags, LPCWSTR lpWideCharStr, int cchWideChar, LPSTR lpMultiByteStr, int cbMultiByte, LPCSTR lpDefaultChar, BOOL* lpUsedDefaultChar) {
    if (!lpWideCharStr) return 0;

    static iconv_t cd_cp932 = (iconv_t)-1;
    static iconv_t cd_utf8 = (iconv_t)-1;
    static iconv_t cd_ascii = (iconv_t)-1;
    
    iconv_t cd = (iconv_t)-1;

    if (CodePage == 932 || CodePage == 3) {
        if (cd_cp932 == (iconv_t)-1) cd_cp932 = iconv_open("CP932", "WCHAR_T");
        cd = cd_cp932;
    } else if (CodePage == CP_UTF8) {
        if (cd_utf8 == (iconv_t)-1) cd_utf8 = iconv_open("UTF-8", "WCHAR_T");
        cd = cd_utf8;
    } else {
        if (cd_ascii == (iconv_t)-1) cd_ascii = iconv_open("ASCII", "WCHAR_T");
        cd = cd_ascii;
    }

    if (cd == (iconv_t)-1) return 0;

    // Reset state
    iconv(cd, NULL, NULL, NULL, NULL);

    size_t inbytesleft = (cchWideChar == -1) ? wcslen(lpWideCharStr) * sizeof(wchar_t) : cchWideChar * sizeof(wchar_t);
    size_t outbytesleft = cbMultiByte;
    char* inptr = (char*)lpWideCharStr;
    char* outptr = (char*)lpMultiByteStr;

    size_t res = iconv(cd, &inptr, &inbytesleft, &outptr, &outbytesleft);
    
    if (res == (size_t)-1) return 0;
    // Return number of bytes written
    return cbMultiByte - outbytesleft;
}

#define strcpy_s(dest, size, src) strncpy(dest, src, (size) - 1); (dest)[(size) - 1] = '\0'
#define _tcscpy_s strcpy_s
#define _tcscat_s(dest, size, src) strncat(dest, src, (size) - strlen(dest) - 1)
#define _tcsicmp strcasecmp
#define _tremove remove
typedef int errno_t;
inline errno_t fopen_s(FILE** pFile, const char *filename, const char *mode) {
    if(!pFile) return EINVAL;
    *pFile = fopen(filename, mode);
    return (*pFile != NULL) ? 0 : errno;
}
#define _tfopen_s(fp, name, mode) fopen_s(fp, name, mode)
#define _vftprintf vfprintf
#define _tMyPrintf printf
#define Sleep(ms) usleep((ms) * 1000)

#define _stscanf_s sscanf
#define _ftscanf_s fscanf
#define _stprintf_s snprintf
#define _ftprintf_s fprintf

#define SAFE_DELETE(p) { if(p) { delete (p); (p)=NULL; } }
#define SAFE_DELETE_ARRAY(p) { if(p) { delete[] (p); (p)=NULL; } }
#define ZeroMemory(p, s) memset(p, 0, s)
#define memcpy_s(dest, destsz, src, count) memcpy(dest, src, count)

#define _MAX_PATH 260
#define _MAX_DRIVE 3
#define _MAX_DIR 256
#define _MAX_FNAME 256
#define _MAX_EXT 256
#define MAX_PATH 260

inline void _tsplitpath(const char* path, char* drive, char* dir, char* fname, char* ext) {
    if (drive) drive[0] = '\0';
    if (dir) dir[0] = '\0';
    const char* last_slash = strrchr(path, '/');
    const char* last_dot = strrchr(path, '.');
    const char* start = last_slash ? last_slash + 1 : path;
    if (fname) {
        size_t len = last_dot && last_dot > start ? last_dot - start : strlen(start);
        strncpy(fname, start, len);
        fname[len] = '\0';
    }
    if (ext) {
        if (last_dot && last_dot > start) strcpy(ext, last_dot);
        else ext[0] = '\0';
    }
}

inline void _tmakepath(char* path, const char* drive, const char* dir, const char* fname, const char* ext) {
    sprintf(path, "%s%s", fname, ext);
}

inline char* PathFindExtension(char* path) {
    if (!path) return NULL;
    char* last_period = strrchr(path, '.');
    char* last_slash = strrchr(path, '/');
    if (last_period && (!last_slash || last_period > last_slash)) return last_period;
    return path + strlen(path);
}

#define _trename rename
#define _doserrno errno
#define _tcscmp strcmp
#define _tcsstr strstr
#define _tcscpy strcpy
#define _tcslen strlen
#define _tcscat strcat
#define _tcsncpy strncpy
#define _tcslen strlen

#define strcat_s(dest, size, src) strncat(dest, src, (size) - strlen(dest) - 1)
#define strncat_s(dest, size, src, count) strncat(dest, src, count)
#define _tsetlocale(a, b) setlocale(a, "ja_JP.UTF-8")
#define _tprintf printf

// Stub for __stdcall, etc.
#define WINAPI
#define CALLBACK
#define __stdcall
#define __cdecl

inline DWORD GetModuleFileName(HMODULE hModule, TCHAR* lpFilename, DWORD nSize) {
    ssize_t len = readlink("/proc/self/exe", lpFilename, nSize - 1);
    if (len != -1) {
        lpFilename[len] = '\0';
        return (DWORD)len;
    }
    return 0;
}
#define GetModuleFileNameA GetModuleFileName

#define _ftprintf fprintf
#define _ftprintf_s fprintf

inline UINT GetPrivateProfileInt(LPCTSTR lpAppName, LPCTSTR lpKeyName, INT nDefault, LPCTSTR lpFileName) {
    return nDefault;
}

inline DWORD GetPrivateProfileString(LPCTSTR lpAppName, LPCTSTR lpKeyName, LPCTSTR lpDefault, LPSTR lpReturnedString, DWORD nSize, LPCTSTR lpFileName) {
    if (lpDefault) {
        strncpy(lpReturnedString, lpDefault, nSize - 1);
        lpReturnedString[nSize - 1] = 0;
        return strlen(lpReturnedString);
    }
    return 0;
}
#define GetPrivateProfileStringA GetPrivateProfileString

#define _splitpath_s(path, drive, dlen, dir, dirLen, fname, fnameLen, ext, extLen) _tsplitpath(path, drive, dir, fname, ext)

#endif
