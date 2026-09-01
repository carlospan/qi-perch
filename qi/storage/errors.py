"""存储层异常。"""


class StorageWriteError(Exception):
    """SQLite 写入失败（磁盘满、锁库等）。"""
