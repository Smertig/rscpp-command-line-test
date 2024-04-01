import utils

# WAT?
utils.update_file('lib/gmp/mini-gmp.c', lambda content: content.replace(b'\x0C', b''))
