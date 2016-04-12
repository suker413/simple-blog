# -*- coding: utf-8 -*-
"""
Created on Tue Apr 12 09:39:51 2016

@author: Administrator
"""
import logging
logging.basicConfig(level=logging.INFO)
from Fields import *

class ModelMetaclass(type):

    def __new__(cls, name, bases, attrs):

        if name == 'Model':
            return type.__new__(cls, name, bases, attrs)

        table = attrs.get('__table__', name)
        logging.info('found model: %s (table: %s)' % (name, table))

        mappings = {}
        fields = []
        primary_key = None
        for key, val in attrs.copy().items():
            if isinstance(val, Field):
                # print("field: %s, pk: %s" %(key, val.primary_key))
                logging.info('found mapping: %s ==> %s' % (key, val))
                mappings[key] = attrs.pop(key)
                if val.primary_key:
                    if primary_key:
                        raise KeyError('Duplicate primary key for field: %s' % key)
                    primary_key = key
                else:
                    fields.append(key)

        if not primary_key:
            raise KeyError('Primary key not found.')

        escaped_fields = ['`%s`' % field for field in fields]
        # print(escaped_fields)
        # print("primary_key: %s" % str(primary_key))
        # print("fields: %s" % str(fields))
        print("mappings: %s" % str(mappings))
        attrs['__table__'] = table                   # 保存表名
        attrs['__mappings__'] = mappings             # 保存属性和列的映射关系
        attrs['__primary_key__'] = primary_key       # 主键属性名
        attrs['__fields__'] = fields                 # 非主键属性名的列表
        attrs['__select__'] = ''
        attrs['__insert__'] = 'insert into `%s` (%s, `%s`) values (%s)' % (table, ', '.join(escaped_fields), primary_key, ', '.join(['?'] * len(mappings)))
        attrs['__update__'] = ''
        attrs['__delete__'] = ''

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

    def getValue(self, key):
        return getattr(self, key, None)

    def getValueOrDefault(self, key):
        value = getattr(self, key, None)
        if value is None:
            field = self.__mappings__[key]
            if field.default is not None:
                value = field.default() if callable(field.default) else field.default
                logging.debug('using default value for %s:%s' % (key, str(value)))
                setattr(self, key, value)
        return value


    def save(self):
        args = list(map(self.getValueOrDefault, self.__fields__ + []))

        print('SQL: %s' %self.__insert__)
        print('args: %s' %str(args))

        # rows = await execute(self.__insert__, args)  # 使用默认插入函数
        # if rows != 1: # 插入失败就是rows!=1
        #     logging.warn('failed to insert record: affected rows: %s' % rows)

    # @classmethod
    # async def findALL(cls, where=None, args=None, **kw):
    #     sql = cls.[__select__]
    #     if where:
    #         sql.append('where')
    #         sql.append(where)