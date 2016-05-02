#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Created on Tue Apr 12 09:39:51 2016

@author: Administrator
"""
import logging
logging.basicConfig(level=logging.INFO)

import aiomysql, asyncio
from Fields import Field

def log(sql, args=[]):
    logging.info('SQL: [%s] args: %s' % (sql, str(args)))

async def create_pool(loop, **kw):
    # 该函数用于创建连接池
    global __pool
    __pool = await aiomysql.create_pool(
        host=kw.get('host', 'localhost'),  # 默认定义host名字为localhost
        port=kw.get('port', 3306),      # 默认定义mysql的默认端口是3306
        user=kw['user'],                # user是通过关键字参数传进来的
        password=kw['password'],        # 密码也是通过关键字参数传进来的
        db=kw['db'],                    # 数据库名字
        charset=kw.get('charset', 'utf8'),  # 默认数据库字符集是utf8
        autocommit=kw.get('autocommit', True),  # 默认自动提交事务
        maxsize=kw.get('maxsize', 10),      # 连接池最多同时处理10个请求
        minsize=kw.get('minsize', 1),       # 连接池最少1个请求
        loop=loop       # 传递消息循环对象loop用于异步执行
    )
# 用于SQL的SELECT语句
async def select(sql, args, size=None):
    log(sql, args)
    async with __pool.get() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(sql.replace('?', '%s'), args)
            if size:
                rs = await cur.fetchmany(size)
            else:
                rs = await cur.fetchall()
        logging.info('rows returned: %s' % len(rs))
        return rs

# 用于SQL的INSERT INTO，UPDATE，DELETE语句
async def execute(sql, args, autocommit=True):
    log(sql, args)
    async with __pool.get() as conn:
        if not autocommit:
            await conn.begin()
        try:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql.replace('?', '%s'), args)
                affected = cur.rowcount
            if not autocommit:
                await conn.commit()
        except BaseException as e:
            if not autocommit:
                await conn.rollback()
            raise e
        return affected

class ModelMetaclass(type):

    def __new__(cls, name, bases, attrs):
        # 忽略父类
        if name == 'Model':
            return type.__new__(cls, name, bases, attrs)
        # 找到表名
        table = attrs.get('__table__', name)
        logging.info('found model: %s (table: %s)' % (name, table))
        # 建立映射关系表和找到主键
        mappings = {}
        primary_key = None
        for key, val in attrs.copy().items():
            if isinstance(val, Field):
                # 把Field属性类保存在映射映射关系表，并从原属性列表中删除
                mappings[key] = attrs.pop(key)
                logging.info('found mapping: %s ==> %s' % (key, val))
                # 查找并检验主键是否唯一
                if val.primary_key:
                    if primary_key:
                        raise KeyError('Duplicate primary key for field: %s' % key)
                    primary_key = key
        if not primary_key:
            raise KeyError('Primary key not found.')
        # 创建新的类的属性
        attrs['__table__'] = table                   # 保存表名
        attrs['__mappings__'] = mappings             # 映射关系表
        attrs['__primary_key__'] = primary_key       # 主键属性名
        #-----------------------默认SQL语句--------------------------
        attrs['__select__'] = 'select * from `%s`' % (table)
        attrs['__insert__'] = 'insert into `%s` (%s) values (%s)' % (table, ', '.join('`%s`'%f for f in mappings), ', '.join(['?'] * len(mappings)))
        attrs['__update__'] = 'update `%s` set %s where `%s` = ?' % (table, ', '.join('`%s` = ?'%f for f in mappings), primary_key)
        attrs['__delete__'] = 'delete from `%s` where `%s`= ?' % (table, primary_key)

        return type.__new__(cls, name, bases, attrs)

class Model(dict, metaclass=ModelMetaclass):
    def __init__(self, **kw):
        super(Model, self).__init__(**kw)

    def __getattr__(self, attr):
        try:
            return self[attr]
        except KeyError:
            raise AttributeError(r"'Model' object has no attribute '%s'" % attr)

    def __setattr__(self, attr, value):
        self[attr] = value
    # 取值或取默认值
    def getValueOrDefault(self, key):
        value = getattr(self, key, None)
        if value is None:
            field = self.__mappings__[key]
            if field.default is not None:
                value = field.default() if callable(field.default) else field.default
                logging.debug('using default value for %s:%s' % (key, str(value)))
                setattr(self, key, value)
        return value
    # 查找所有合乎条件的信息
    @classmethod
    async def findAll(cls, where=None, args=None, **kw):
        ' find objects by where clause. '
        # 初始化SQL语句和参数列表
        sql = [cls.__select__]
        args = args or []
        # WHERE查找条件的关键字
        if where:
            sql.append('where %s' % (where))
        # ORDER BY是排序的关键字
        if kw.get('orderBy') is not None:
            sql.append('order by %s' % (kw['orderBy']))
        # LIMIT 是筛选结果集的关键字
        limit = kw.get('limit')
        if limit is not None:
            if isinstance(limit, int):
                sql.append('limit ?')
                args.append(limit)
            elif isinstance(limit, tuple) and len(limit) == 2:
                sql.append('limit ?, ?')
                args.extend(limit)
            else:
                raise ValueError('Invalid limit value: %s' % str(limit))
        rs = await select(' '.join(sql), args)
        return [cls(**r) for r in rs]
    # 根据列名和条件查看数据库有多少条信息
    @classmethod
    async def countRows(cls, selectField, where=None, args=None):
        ' find number by select and where. '
        sql = ['select count(%s) _num_ from `%s`' % (selectField, cls.__table__)]
        if where:
            sql.append('where %s' % (where))
        rs = await select(' '.join(sql), args or [], 1)
        if len(rs) == 0:
            return None
        return rs[0]['_num_']
    # 根据主键查找一个实例的信息
    @classmethod
    async def find(cls, pk):
        ' find object by primary key. '
        rs = await select('%s where `%s`= ?' % (cls.__select__, cls.__primary_key__), [pk], 1)
        return cls(**rs[0]) if len(rs) else None
    # 把一个实例保存到数据库
    async def save(self):
        args = list(map(self.getValueOrDefault, self.__mappings__))
        rows = await execute(self.__insert__, args) # 使用默认插入函数
        if rows != 1: # 插入失败就是rows!=1
            logging.warn('failed to insert record: affected rows: %s' % rows)
    # 更改一个实例在数据库的信息
    async def update(self):
        args = list(map(self.get, list(self.__mappings__) + [self.__primary_key__]))
        rows = await execute(self.__update__, args)
        if rows != 1:
            logging.warn('failed to update by primary key: affected rows: %s' % rows)
    # 把一个实例从数据库中删除
    async def remove(self):
        args = [self.get(self.__primary_key__)]
        rows = await execute(self.__delete__, args)
        if rows != 1:
            logging.warn('failed to remove by primary key: affected rows: %s' % rows)