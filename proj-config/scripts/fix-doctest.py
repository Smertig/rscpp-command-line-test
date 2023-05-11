import utils

# Remove hacky forward declarations
utils.update_file('./examples/all_features/stringification.cpp', lambda content: content.replace(b'#ifdef _MSC_VER', b'#if 0'))
