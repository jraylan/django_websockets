from typing import Iterator


class RoundRobQueue(object):

    def __init__(self, iterator:Iterator):
        self._iterator = iterator
        self.idx = 0

    def next(self):
        return self.__next__()
    
    def __next__(self):
        try:
            return [
                *self._iterator
            ][self.idx % len(self._iterator)]
        finally:
            self.idx += 1

    def __len__(self):
        return len(self._iterator)

    def __iter__(self):
        return self

    def keys(self):
        return self._iterator.keys()

    def values(self):
        return self._iterator.values()

    def items(self):
        return self._iterator.items()

    def __getitem__(self, key):
        return self._iterator.__getitem__(key)
    
    def update(self, queue: 'RoundRobQueue'):
        self._iterator = queue._iterator
