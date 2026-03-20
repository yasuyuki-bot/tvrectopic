//------------------------------------------------------------------------------
// ARIB8CharDecode.h
//------------------------------------------------------------------------------
#ifndef __ARIB8CHAR_DECODE_H__
#define __ARIB8CHAR_DECODE_H__

#include <string>
#include <vector>
#include <map>
using namespace std;

extern map<string, string> dicHash_Char_map;
extern map<WORD, string> dicCharcode_Char_map;

//譁・ｭ礼ｬｦ蜿ｷ髮・粋
//G繧ｻ繝・ヨ
#define MF_JIS_KANJI1   0x39    //JIS莠呈鋤貍｢蟄・髱｢
#define MF_JIS_KANJI2   0x3A    //JIS莠呈鋤貍｢蟄・髱｢
#define MF_KIGOU        0x3B    //霑ｽ蜉險伜捷
#define MF_ASCII        0x4A    //闍ｱ謨ｰ
#define MF_HIRA         0x30    //蟷ｳ莉ｮ蜷・
#define MF_KANA         0x31    //迚・ｻｮ蜷・
#define MF_KANJI        0x42    //貍｢蟄・
#define MF_MOSAIC_A     0x32    //繝｢繧ｶ繧､繧ｯA
#define MF_MOSAIC_B     0x33    //繝｢繧ｶ繧､繧ｯB
#define MF_MOSAIC_C     0x34    //繝｢繧ｶ繧､繧ｯC
#define MF_MOSAIC_D     0x35    //繝｢繧ｶ繧､繧ｯD
#define MF_PROP_ASCII   0x36    //繝励Ο繝昴・繧ｷ繝ｧ繝翫Ν闍ｱ謨ｰ
#define MF_PROP_HIRA    0x37    //繝励Ο繝昴・繧ｷ繝ｧ繝翫Ν蟷ｳ莉ｮ蜷・
#define MF_PROP_KANA    0x38    //繝励Ο繝昴・繧ｷ繝ｧ繝翫Ν迚・ｻｮ蜷・
#define MF_JISX_KANA    0x49    //JIX X0201迚・ｻｮ蜷・
//DRCS
#define MF_DRCS_0   0x40    //DRCS-0
#define MF_DRCS_1   0x41    //DRCS-1
#define MF_DRCS_2   0x42    //DRCS-2
#define MF_DRCS_3   0x43    //DRCS-3
#define MF_DRCS_4   0x44    //DRCS-4
#define MF_DRCS_5   0x45    //DRCS-5
#define MF_DRCS_6   0x46    //DRCS-6
#define MF_DRCS_7   0x47    //DRCS-7
#define MF_DRCS_8   0x48    //DRCS-8
#define MF_DRCS_9   0x49    //DRCS-9
#define MF_DRCS_10  0x4A    //DRCS-10
#define MF_DRCS_11  0x4B    //DRCS-11
#define MF_DRCS_12  0x4C    //DRCS-12
#define MF_DRCS_13  0x4D    //DRCS-13
#define MF_DRCS_14  0x4E    //DRCS-14
#define MF_DRCS_15  0x4F    //DRCS-15
#define MF_MACRO    0x70    //繝槭け繝ｭ

//隨ｦ蜿ｷ髮・粋縺ｮ蛻・｡・
#define MF_MODE_G       1   //G繧ｻ繝・ヨ
#define MF_MODE_DRCS    2   //DRCS
#define MF_MODE_OTHER   3   //縺昴・莉・

//譁・ｭ励し繧､繧ｺ
typedef enum{
    STR_SMALL = 0,  //SSZ
    STR_MEDIUM,     //MSZ
    STR_NORMAL,     //NSZ
    STR_MICRO,      //SZX 0x60
    STR_HIGH_W,     //SZX 0x41
    STR_WIDTH_W,    //SZX 0x44
    STR_W,          //SZX 0x45
    STR_SPECIAL_1,  //SZX 0x6B
    STR_SPECIAL_2,  //SZX 0x64
} STRING_SIZE;

typedef struct _CAPTION_CHAR_DATA {
    string strDecode;
    STRING_SIZE emCharSizeMode;

    CLUT_DAT stCharColor;
    CLUT_DAT stBackColor;
    CLUT_DAT stRasterColor;

    BOOL bUnderLine;
    BOOL bShadow;
    BOOL bBold;
    BOOL bItalic;
    BYTE bFlushMode;
    BYTE bHLC; //must ignore low 4bits

    WORD wCharW;
    WORD wCharH;
    WORD wCharHInterval;
    WORD wCharVInterval;
    //=繧ｪ繝壹Ξ繝ｼ繧ｿ繝ｼ縺ｮ蜃ｦ逅・
    _CAPTION_CHAR_DATA & operator= (const _CAPTION_CHAR_DATA & o) {
        strDecode = o.strDecode;
        emCharSizeMode = o.emCharSizeMode;
        stCharColor = o.stCharColor;
        stBackColor = o.stBackColor;
        stRasterColor = o.stRasterColor;
        bUnderLine = o.bUnderLine;
        bShadow = o.bShadow;
        bBold = o.bBold;
        bItalic = o.bItalic;
        bFlushMode = o.bFlushMode;
        bHLC = o.bHLC;
        wCharW = o.wCharH;
        wCharHInterval = o.wCharHInterval;
        wCharVInterval = o.wCharVInterval;
        return *this;
    };
} CAPTION_CHAR_DATA;

typedef struct _CAPTION_DATA {
    BOOL bClear;
    WORD wSWFMode;
    WORD wClientX;
    WORD wClientY;
    WORD wClientW;
    WORD wClientH;
    WORD wPosX;
    WORD wPosY;
    vector<CAPTION_CHAR_DATA> CharList;
    DWORD dwWaitTime;
    //=繧ｪ繝壹Ξ繝ｼ繧ｿ繝ｼ縺ｮ蜃ｦ逅・
    _CAPTION_DATA & operator= (const _CAPTION_DATA & o) {
        bClear = o.bClear;
        wSWFMode = o.wSWFMode;
        wClientX = o.wClientX;
        wClientY = o.wClientY;
        wClientW = o.wClientW;
        wClientH = o.wClientH;
        wPosX = o.wPosX;
        wPosY = o.wPosY;
        CharList = o.CharList;
        dwWaitTime = o.dwWaitTime;
        return *this;
    };
} CAPTION_DATA;
//DRCS蝗ｳ蠖｢縺ｮ邵ｦ讓ｪ譛螟ｧ繧ｵ繧､繧ｺ(驕狗畑隕丞ｮ壹ｈ繧・
#define DRCS_SIZE_MAX 36

struct DRCS_PATTERN {
    WORD wDRCCode;
    WORD wGradation;
    BITMAPINFOHEADER bmiHeader;
    BYTE bBitmap[(DRCS_SIZE_MAX * 4 + 31) / 32 * 4 * DRCS_SIZE_MAX];
    DRCS_PATTERN() {}
};

class CARIB8CharDecode
{
public:
    CARIB8CharDecode(void);
    ~CARIB8CharDecode(void);

    //蟄怜ｹ輔ｒ諠ｳ螳壹＠縺欖JIS縺ｸ縺ｮ螟画鋤
    BOOL Caption(const BYTE *pbSrc, DWORD dwSrcSize, vector<CAPTION_DATA> *pCaptionList);
    //dll縺ｮ繝代せ縺ｮ蜿門ｾ・
    string GetAppPath(void)
    {
        CHAR wkPath[_MAX_PATH], wkDrive[_MAX_DRIVE], wkDir[_MAX_DIR], wkFileName[_MAX_FNAME], wkExt[_MAX_EXT];
        DWORD dwRet = GetModuleFileNameA(NULL, wkPath, sizeof(wkPath));
        if (dwRet == 0) {
            //繧ｨ繝ｩ繝ｼ蜃ｦ逅・↑縺ｩ(逵∫払)
        }
        _splitpath_s(wkPath, wkDrive, _MAX_DRIVE, wkDir, _MAX_DIR, wkFileName, _MAX_FNAME, wkExt, _MAX_EXT);
        string strAppPath = "";
        strAppPath += wkDrive;
        strAppPath += wkDir;
        return strAppPath;
    }
    BOOL DRCSHeaderparse(const BYTE *pbSrc, DWORD dwSrcSize, BOOL bDRCS_0);

protected:
    typedef struct _MF_MODE {
        int iMF; //譁・ｭ礼ｬｦ蜿ｷ髮・粋
        int iMode; //隨ｦ蜿ｷ髮・粋縺ｮ蛻・｡・
        int iByte; //隱ｭ縺ｿ霎ｼ縺ｿ繝舌う繝域焚
        //=繧ｪ繝壹Ξ繝ｼ繧ｿ繝ｼ縺ｮ蜃ｦ逅・
        _MF_MODE & operator= (const _MF_MODE & o) {
            iMF = o.iMF;
            iMode = o.iMode;
            iByte = o.iByte;
            return *this;
        }
    } MF_MODE;

    BOOL m_bPSI;

    MF_MODE  m_G0;
    MF_MODE  m_G1;
    MF_MODE  m_G2;
    MF_MODE  m_G3;
    MF_MODE *m_GL;
    MF_MODE *m_GR;

    BOOL m_bModGL;

    //繝・さ繝ｼ繝峨＠縺滓枚蟄怜・
    string m_strDecode;
    //譁・ｭ励し繧､繧ｺ
    STRING_SIZE m_emStrSize;

    //CLUT縺ｮ繧､繝ｳ繝・ャ繧ｯ繧ｹ
    BYTE m_bCharColorIndex;
    BYTE m_bBackColorIndex;
    BYTE m_bRasterColorIndex;
    BYTE m_bDefPalette;

    BOOL m_bUnderLine;
    BOOL m_bShadow;
    BOOL m_bBold;
    BOOL m_bItalic;
    BYTE m_bFlushMode;
    BYTE m_bHLC;
    //map<string, string> dicHash_Char_map;
    //map<int, string> dicCharcode_Char_map;
    WORD m_wMaxPosX;
    WORD m_wTmpPosX;
    // RPC蟇ｾ蠢・
    BOOL m_bRPC;
    WORD m_wRPC;
    // DRCS縺ｨARIB縺ｮ莉｣逕ｨ譁・ｭ礼畑ini繝輔ぃ繧｣繝ｫ縺ｮUnicode
//  BOOL m_bUnicode;
    BOOL m_bGaiji;

    //陦ｨ遉ｺ譖ｸ蠑・
    WORD m_wSWFMode;
    WORD m_wClientX;
    WORD m_wClientY;
    WORD m_wClientW;
    WORD m_wClientH;
    WORD m_wPosX;
    WORD m_wPosY;
    WORD m_wCharW;
    WORD m_wCharH;
    WORD m_wCharHInterval;
    WORD m_wCharVInterval;
    WORD m_wMaxChar;

    DWORD m_dwWaitTime;

    vector<CAPTION_DATA> *m_pCaptionList;
protected:
    void InitCaption(void);
    BOOL Analyze(const BYTE *pbSrc, DWORD dwSrcSize, DWORD *pdwReadSize);

    BOOL IsSmallCharMode(void);
    BOOL IsChgPos(void);
    void CreateCaptionData(CAPTION_DATA *pItem);
    void CreateCaptionCharData(CAPTION_CHAR_DATA *pItem);
    void CheckModify(void);

    //蛻ｶ蠕｡隨ｦ蜿ｷ
    BOOL C0(const BYTE *pbSrc, DWORD *pdwReadSize);
    BOOL C1(const BYTE *pbSrc, DWORD *pdwReadSize);
    BOOL GL(const BYTE *pbSrc, DWORD *pdwReadSize);
    BOOL GR(const BYTE *pbSrc, DWORD *pdwReadSize);
    //繧ｷ繝ｳ繧ｰ繝ｫ繧ｷ繝輔ヨ
    BOOL SS2(const BYTE *pbSrc, DWORD *pdwReadSize);
    BOOL SS3(const BYTE *pbSrc, DWORD *pdwReadSize);
    //繧ｨ繧ｹ繧ｱ繝ｼ繝励す繝ｼ繧ｱ繝ｳ繧ｹ
    BOOL ESC(const BYTE *pbSrc, DWORD *pdwReadSize);
    //・偵ヰ繧､繝域枚蟄怜､画鋤
    BOOL ToSJIS(const BYTE bFirst, const BYTE bSecond);
    BOOL ToCustomFont(const BYTE bFirst, const BYTE bSecond);

    BOOL CSI(const BYTE *pbSrc, DWORD *pdwReadSize);

    BOOL AddToString(const char *cDec, BOOL m_bGaiji);

public:
    string Get_dicCharcode_Char(WORD DRCSCharCode)
    {
        string strRet = "NF";
        map<WORD, string>::iterator iter = dicCharcode_Char_map.find(DRCSCharCode);
        if (iter != dicCharcode_Char_map.end()) {
            strRet = iter->second;
        }
        return strRet;
    }
    void Add_dicCharcode_Char(WORD DRCSCharCode, string gaijichar)
    {
        dicCharcode_Char_map.insert(std::make_pair(DRCSCharCode, map<WORD, string>::mapped_type())).first->second = gaijichar;
    }
    string Get_dicHash_Char(string hash)
    {
        string strRet = "NF";
        map<string, string>::iterator iter = dicHash_Char_map.find(hash);
        if (iter != dicHash_Char_map.end()) {
            strRet = iter->second;
        }
        return strRet;
    }
    void Add_dicHash_Char(string hash, string gaijichar)
    {
        dicHash_Char_map.insert(map<string, string>::value_type(hash, gaijichar));
    }
};

#endif // __ARIB8CHAR_DECODE_H__
