import utils

# Workaround for RSCPP-34288 STOFL on recursive object
utils.update_file('src/google/protobuf/arena.cc',
                  lambda content: content.replace(b'static const ArenaBlock kSentryArenaBlock;',
                                                  b'static constexpr ArenaBlock kSentryArenaBlock;'))

# Workaround for non-conformant offsetof implementation
utils.update_file('src/google/protobuf/port_def.inc',
                  lambda content: content.replace(b'#ifdef PROTOBUF_EXPORT',
                                                  b'#define PROTOBUF_FIELD_OFFSET(TYPE, FIELD) 0\n#ifdef PROTOBUF_EXPORT'))

utils.update_file('third_party/abseil-cpp/absl/base/config.h',
                  lambda content: content.replace(b'#elif defined(__clang__) && (__clang_major__ >= 15)', b'#else'))
