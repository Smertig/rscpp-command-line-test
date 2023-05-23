import utils

# enable tests even with missing perl
utils.update_file('CMakeLists.txt', lambda content: content.replace(b'if(BUILD_TESTING)', b'if(TRUE)'))
