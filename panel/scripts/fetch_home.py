import urllib.request
try:
    r = urllib.request.urlopen('http://127.0.0.1:8000/')
    print('status', r.getcode())
    data = r.read()
    print('len', len(data))
    print(data[:1000].decode('utf-8', errors='replace'))
except Exception as e:
    import traceback; traceback.print_exc()
