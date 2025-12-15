# Makefile for fbxaxisconvert
#
# Requires Autodesk FBX SDK installed at:
#   /Applications/Autodesk/FBX SDK/2020.3.7
#
# Build:
#   make           - Build release version
#   make debug     - Build debug version
#   make clean     - Remove built files

# FBX SDK configuration
FBX_SDK_VERSION = 2020.3.7
FBX_SDK_ROOT = /Applications/Autodesk/FBX SDK/$(FBX_SDK_VERSION)
FBX_SDK_INCLUDE = $(FBX_SDK_ROOT)/include
FBX_SDK_LIB_RELEASE = $(FBX_SDK_ROOT)/lib/clang/release
FBX_SDK_LIB_DEBUG = $(FBX_SDK_ROOT)/lib/clang/debug

# Compiler settings
CXX = clang++
CXXFLAGS = -std=c++11 -Wall -Wextra
CXXFLAGS += -I"$(FBX_SDK_INCLUDE)"
# Suppress warnings from FBX SDK headers
CXXFLAGS += -Wno-deprecated-declarations -Wno-deprecated-copy-with-user-provided-copy
CXXFLAGS += -Wno-unused-parameter -Wno-uninitialized

# macOS frameworks required by FBX SDK
FRAMEWORKS = -framework CoreFoundation -framework Carbon

# Linker flags
LDFLAGS_RELEASE = -L"$(FBX_SDK_LIB_RELEASE)" -lfbxsdk $(FRAMEWORKS)
LDFLAGS_DEBUG = -L"$(FBX_SDK_LIB_DEBUG)" -lfbxsdk $(FRAMEWORKS)

# For static linking (larger binary but no dylib dependency)
LDFLAGS_STATIC = "$(FBX_SDK_LIB_RELEASE)/libfbxsdk.a" $(FRAMEWORKS) -lz -lxml2 -liconv

# Default linker flags (static)
LDFLAGS = $(LDFLAGS_STATIC)

# Target
TARGET = fbxaxisconvert
SOURCES = fbxaxisconvert.cpp

# Default target: static build (no dylib dependency)
all: static

release: CXXFLAGS += -O2 -DNDEBUG
release: LDFLAGS = $(LDFLAGS_RELEASE)
release: $(TARGET)

debug: CXXFLAGS += -g -O0 -DDEBUG
debug: LDFLAGS = $(LDFLAGS_DEBUG)
debug: $(TARGET)

# Static build (no dylib dependency)
static: CXXFLAGS += -O2 -DNDEBUG
static: $(TARGET)

$(TARGET): $(SOURCES)
	$(CXX) $(CXXFLAGS) -o $@ $< $(LDFLAGS)

clean:
	rm -f $(TARGET)

# Install target (optional)
PREFIX ?= /usr/local
install: $(TARGET)
	install -d $(PREFIX)/bin
	install -m 755 $(TARGET) $(PREFIX)/bin/

uninstall:
	rm -f $(PREFIX)/bin/$(TARGET)

.PHONY: all release debug static clean install uninstall
