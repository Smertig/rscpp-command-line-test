def update_file(path, callback):
    with open(path, 'rb') as f:
        content = f.read()
    content = callback(content)
    with open(path, 'wb') as f:
        f.write(content)


def insert_before(path, needle: bytes, new_content: bytes):
    def callback(content: bytes):
        pos = content.index(needle)
        return content[:pos] + new_content + content[pos:]

    update_file(path, callback)


def insert_after(path, needle: bytes, new_content: bytes):
    def callback(content: bytes):
        pos = content.index(needle) + len(needle)
        return content[:pos] + new_content + content[pos:]

    update_file(path, callback)
