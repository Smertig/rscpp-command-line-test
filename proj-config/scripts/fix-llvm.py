import utils

# R++ bug with visibility, i.e. 'Member is inaccessible' in clang::CXXConstructorDecl::getTrailingAllocKind
utils.update_file('llvm/include/llvm/Support/TrailingObjects.h',
                  lambda content: content.replace(b'class TrailingObjects : private trailing_objects_internal',
                                                  b'class TrailingObjects : public trailing_objects_internal'))
