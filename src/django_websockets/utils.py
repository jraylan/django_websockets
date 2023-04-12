from reprlib import recursive_repr
from typing import Callable, Awaitable
from asyncio import iscoroutinefunction


class async_partial:
    """New async function with partial application of the given arguments
    and keywords.
    """

    __slots__ = "func", "args", "keywords", "__dict__", "__weakref__"

    def __new__(cls, func:Awaitable[Callable], /, *args, **keywords):
        if not iscoroutinefunction(func):
            raise TypeError("the first argument must be an awaitable callable")

        if hasattr(func, "func"):
            args = func.args + args
            keywords = {**func.keywords, **keywords}
            func = func.func

        self = super(async_partial, cls).__new__(cls)

        self.func = func
        self.args = args
        self.keywords = keywords
        return self

    async def __call__(self, /, *args, **keywords):
        keywords = {**self.keywords, **keywords}
        return await self.func(*self.args, *args, **keywords)

    @recursive_repr()
    def __repr__(self):
        qualname = type(self).__qualname__
        args = [repr(self.func)]
        args.extend(repr(x) for x in self.args)
        args.extend(f"{k}={v!r}" for (k, v) in self.keywords.items())
        if type(self).__module__ == "functools":
            return f"functools.{qualname}({', '.join(args)})"
        return f"{qualname}({', '.join(args)})"

    def __reduce__(self):
        return type(self), (self.func,), (self.func, self.args,
                                          self.keywords or None, self.__dict__ or None)

    def __setstate__(self, state):
        if not isinstance(state, tuple):
            raise TypeError("argument to __setstate__ must be a tuple")
        if len(state) != 4:
            raise TypeError(f"expected 4 items in state, got {len(state)}")
        func, args, kwds, namespace = state
        if (not callable(func) or not isinstance(args, tuple) or
           (kwds is not None and not isinstance(kwds, dict)) or
           (namespace is not None and not isinstance(namespace, dict))):
            raise TypeError("invalid partial state")

        args = tuple(args)  # just in case it's a subclass
        if kwds is None:
            kwds = {}
        elif type(kwds) is not dict:  # XXX does it need to be *exactly* dict?
            kwds = dict(kwds)
        if namespace is None:
            namespace = {}

        self.__dict__ = namespace
        self.func = func
        self.args = args
        self.keywords = kwds

class Atom:
    slots = ('value',)
    def __setattr__(self, attr, value):
        return

    def __init__(self, value):
        super().__setattr__('value', str(value))

    def __get__(self, __instance, __owner=None):
        return self.value

    def __eq__(self, other):
        if isinstance(other, str):
            return self.value == other
        return self is other

    def __req__(self, other):
        if isinstance(other, str):
            return self.value == other
        return self is other
    
    def __repr__(self) -> str:
        return f'<django_websockets.Atom {self.value} >'
