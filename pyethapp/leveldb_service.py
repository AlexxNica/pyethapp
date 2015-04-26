import os
from devp2p.service import BaseService
from gevent.event import Event
import leveldb
from ethereum import slogging

slogging.set_level('db', 'debug')
log = slogging.get_logger('db')

compress = decompress = lambda x: x


class LevelDB(object):

    def __init__(self, dbfile):
        self.uncommitted = dict()
        log.info('opening LevelDB', path=dbfile)
        self.db = leveldb.LevelDB(dbfile)

    def get(self, key):
        log.trace('getting entry', key=key.encode('hex')[:8])
        if key in self.uncommitted:
            if self.uncommitted[key] is None:
                raise KeyError("key not in db")
            log.trace('from uncommitted')
            return self.uncommitted[key]
        log.trace('from db')
        o = decompress(self.db.Get(key))
        self.uncommitted[key] = o
        return o

    def put(self, key, value):
        log.trace('putting entry', key=key.encode('hex')[:8], len=len(value))
        self.uncommitted[key] = value

    def commit(self):
        log.debug('committing', db=self)
        batch = leveldb.WriteBatch()
        for k, v in self.uncommitted.items():
            if v is None:
                batch.Delete(k)
            else:
                batch.Put(k, compress(v))
        self.db.Write(batch, sync=False)
        self.uncommitted.clear()

    def delete(self, key):
        log.trace('deleting entry', key=key)
        self.uncommitted[key] = None

    def _has_key(self, key):
        try:
            self.get(key)
            return True
        except KeyError:
            return False

    def __contains__(self, key):
        return self._has_key(key)

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.db == other.db

    def __repr__(self):
        return '<DB at %d uncommitted=%d>' % (id(self.db), len(self.uncommitted))


class LevelDBService(LevelDB, BaseService):

    """A service providing an interface to a level db."""

    name = 'db'
    default_config = dict(data_dir='')

    def __init__(self, app):
        BaseService.__init__(self, app)
        assert self.app.config['data_dir']
        self.uncommitted = dict()
        self.stop_event = Event()
        dbfile = os.path.join(self.app.config['data_dir'], 'leveldb')
        LevelDB.__init__(self, dbfile)

    def _run(self):
        self.stop_event.wait()

    def stop(self):
        self.stop_event.set()
        # commit?
        log.info('closing db')
