//------------------------------------------------------------------------------
// IniFile.h
//------------------------------------------------------------------------------
#ifndef __INI_FILE_H__
#define __INI_FILE_H__

//ref class IniFile
class IniFile
{

public:
    BOOL ReadIni(void);
    BOOL ReadIniARIB(void);
    BOOL ReadIniUNICODE(void);
    BOOL ReadIniARIBUNICODE(void);

};

#endif // __INI_FILE_H__
