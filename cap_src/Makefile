CXX = g++
CXXFLAGS = -std=c++11 -O2 -D_LINUX -I./src -I./src/common -I./src/Caption_dll/Caption -I./src/Caption2Ass_PCR
LDFLAGS =

SRCS = src/Caption2Ass_PCR/Caption2Ass_PCR.cpp \
       src/Caption2Ass_PCR/Caption2AssParameter.cpp \
       src/Caption2Ass_PCR/CaptionDllUtil.cpp \
       src/Caption2Ass_PCR/cmdline.cpp \
       src/Caption2Ass_PCR/tslUtil.cpp \
       src/Caption2Ass_PCR/ass_header.cpp \
       src/Caption_dll/Caption/CaptionMain.cpp \
       src/Caption_dll/Caption/ARIB8CharDecode.cpp \
       src/Caption_dll/Caption/CalcMD5.cpp \
       src/Caption_dll/Caption/Caption.cpp \
       src/common/CommRoutine.cpp \

# Simple object mapping for non-conflicting names
OBJS = src/Caption2Ass_PCR/Caption2Ass_PCR.o \
       src/Caption2Ass_PCR/Caption2AssParameter.o \
       src/Caption2Ass_PCR/CaptionDllUtil.o \
       src/Caption2Ass_PCR/cmdline.o \
       src/Caption2Ass_PCR/tslUtil.o \
       src/Caption2Ass_PCR/ass_header.o \
       src/Caption_dll/Caption/CaptionMain.o \
       src/Caption_dll/Caption/ARIB8CharDecode.o \
       src/Caption_dll/Caption/CalcMD5.o \
       src/Caption_dll/Caption/Caption.o \
       src/common/CommRoutine.o \
       src/Caption2Ass_PCR/IniFile_PCR.o \
       src/Caption_dll/Caption/IniFile_DLL.o

TARGET = Caption2Ass

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CXX) $(CXXFLAGS) -o $@ $^ $(LDFLAGS)

%.o: %.cpp
	$(CXX) $(CXXFLAGS) -c -o $@ $<

src/Caption2Ass_PCR/IniFile_PCR.o: src/Caption2Ass_PCR/IniFile.cpp
	$(CXX) $(CXXFLAGS) -c -o $@ $<

src/Caption_dll/Caption/IniFile_DLL.o: src/Caption_dll/Caption/IniFile.cpp
	$(CXX) $(CXXFLAGS) -c -o $@ $<

clean:
	rm -f $(OBJS) $(TARGET)
