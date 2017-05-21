_registry = {}

def publish(event, data):
    fns = _registry.get(event, [])
    for fn in fns:
        fn(data)

def subscribe(event):
    def wrap(f):
        _registry.setdefault(event, [])
        _registry[event].append(f)
        return f
    return wrap
