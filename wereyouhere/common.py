from collections.abc import Sized
from datetime import datetime
import re
from typing import NamedTuple, Set, Iterable, Dict, TypeVar, Callable, List, Optional, Union
from pathlib import Path
import logging
from functools import lru_cache

import pytz

from .normalise import normalise_url

Url = str
Tag = str
DatetimeIsh = Union[datetime, str]
Context = str

class PreVisit(NamedTuple):
    url: Url
    dt: DatetimeIsh
    context: Optional[Context] = None
    tag: Optional[Tag] = None


class Visit(NamedTuple):
    dt: datetime
    tag: Optional[Tag] = None
    context: Optional[Context] = None

class Entry(NamedTuple):
    url: Url
    visits: Set[Visit]
    # TODO compare urls?

Filter = Callable[[Url], bool]

def make_filter(thing) -> Filter:
    if isinstance(thing, str):
        rc = re.compile(thing)
        def filter_(u: str) -> bool:
            return rc.search(u) is not None
        return filter_
    else: # must be predicate
        return thing

# TODO do i really need to inherit this??
class History(Sized):
    FILTERS: List[Filter] = [
        make_filter(f) for f in
        [
            r'^chrome-devtools://',
            r'^chrome-extension://',
            r'^chrome-error://',
            r'^chrome-native://',
            r'^chrome-search://',

            r'chrome://newtab',
            r'chrome://apps',
            r'chrome://history',

            r'^about:',
            r'^blob:',
            r'^view-source:',

            r'^content:',

            # TODO maybe file:// too?
            # chrome-search:
        ]
    ]

    @classmethod
    def add_filter(cls, filterish):
        cls.FILTERS.append(make_filter(filterish))

    def __init__(self):
        self.urls: Dict[Url, Entry] = {}

    @classmethod
    def from_urls(cls, urls: Dict[Url, Entry], filters: List[Filter] = None) -> 'History':
        hist = cls()
        hist.urls = urls
        return hist

    # TODO mm. maybe history should get filters from some global config?
    # wonder how okay is it to set class attribute..

    @classmethod
    def filtered(cls, url: Url) -> bool:
        for f in cls.FILTERS:
            if f(url):
                return True
        return False

    def register(self, url: Url, v: Visit) -> None:
        if History.filtered(url):
            return
        if v.dt.tzinfo is None:
            # TODO log that?...
            pass
        # TODO replace dt i

        # TODO hmm some filters make sense before stripping off protocol...
        # TODO is it a good place to normalise?
        url = normalise_url(url)

        e = self.urls.get(url, None)
        if e is None:
            e = Entry(url=url, visits=set())
        e.visits.add(v)
        self.urls[url] = e

    def __len__(self) -> int:
        return len(self.urls)

    def __getitem__(self, url: Url) -> Entry:
        return self.urls[url]

    def items(self):
        return self.urls.items()

    def __repr__(self):
        return 'History{' + repr(self.urls) + '}'

# f is value merger function
_K = TypeVar("_K")
_V = TypeVar("_V")

def merge_dicts(f: Callable[[_V, _V], _V], dicts: Iterable[Dict[_K, _V]]):
    res: Dict[_K, _V] = {}
    for d in dicts:
        for k, v in d.items():
            if k not in res:
                res[k] = v
            else:
                res[k] = f(res[k], v)
    return res

def entry_merger(a: Entry, b: Entry):
    a.visits.update(b.visits)
    return a

def merge_histories(hists: Iterable[History]) -> History:
    return History.from_urls(merge_dicts(entry_merger, [h.urls for h in hists]))

def get_logger():
    return logging.getLogger("WereYouHere")


# kinda singleton
@lru_cache()
def get_tmpdir():
    import tempfile
    tdir = tempfile.TemporaryDirectory(suffix="wereyouhere")
    return tdir

PathIsh = Union[Path, str]
