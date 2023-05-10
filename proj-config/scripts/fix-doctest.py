PATH = './examples/all_features/stringification.cpp'

with open(PATH, 'rb') as f:
    content = f.read()

# Remove hacky forward declarations
content = content.replace(b'#ifdef _MSC_VER', b'#if 0')

with open(PATH, 'wb') as f:
    f.write(content)
