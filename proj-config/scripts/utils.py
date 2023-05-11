def update_file(path, callback):
    with open(path, 'rb') as f:
        content = f.read()
    content = callback(content)
    with open(path, 'wb') as f:
        f.write(content)
