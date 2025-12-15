/**
 * fbxsdk_fix.h - Workaround for FBX SDK typos
 *
 * The FBX SDK 2020.3.x has a typo in fbxredblacktree.h where
 * "mLefttChild" is used instead of "mLeftChild". This header
 * includes the SDK and applies a macro workaround.
 */

#ifndef FBXSDK_FIX_H
#define FBXSDK_FIX_H

// Fix typo in FBX SDK 2020.3.x
#define mLefttChild mLeftChild

#include <fbxsdk.h>

#undef mLefttChild

#endif // FBXSDK_FIX_H
