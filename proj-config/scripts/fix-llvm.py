import utils

# R++ bug with visibility, i.e. 'Member is inaccessible' in clang::CXXConstructorDecl::getTrailingAllocKind
utils.update_file('llvm/include/llvm/Support/TrailingObjects.h',
                  lambda content: content.replace(b'class TrailingObjects : private trailing_objects_internal',
                                                  b'class TrailingObjects : public trailing_objects_internal'))

# Workaround for RSCPP-34288 STOFL on recursive object
utils.update_file('clang/lib/Format/Format.cpp',
                  lambda content: content.replace(b'static const ParseErrorCategory C{}',
                                                  b'static /*const*/ ParseErrorCategory C{}'))
