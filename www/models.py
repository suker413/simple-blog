# -*- coding: utf-8 -*-
"""
Created on Tue Apr 12 09:40:51 2016

@author: Administrator
"""
import time, uuid
from Fields import *
from orm import Model

# import functools
# StringField = functools.partial(StringField, ddl='varchar(50)')

def next_id():
    return '%015d%s000' % (int(time.time() * 1000), uuid.uuid4().hex)

class User(Model):
    __table__ = 'users'

    id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    email = StringField(ddl='varchar(50)')
    password = StringField(ddl='varchar(50)')
    admin = BooleanField()
    name = StringField(ddl='varchar(50)')
    image = StringField(ddl='varchar(500)')
    created_at = FloatField(default=time.time)

# class Blog(Model):
#     __table__ = 'blogs'

#     id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
#     user_id = StringField(ddl='varchar(50)')
#     user_name = StringField(ddl='varchar(50)')
#     user_image = StringField(ddl='varchar(500)')
#     name = StringField(ddl='varchar(50)')
#     summary = StringField(ddl='varchar(200)')
#     content = TextField()
#     created_at = FloatField(default=time.time)

# class Comment(Model):
#     __table__ = 'comments'

#     id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
#     blog_id = StringField(ddl='varchar(50)')
#     user_id = StringField(ddl='varchar(50)')
#     user_name = StringField(ddl='varchar(50)')
#     user_image = StringField(ddl='varchar(500)')
#     content = TextField()
#     created_at = FloatField(default=time.time)

if __name__ == '__main__':
    # 创建一个实例：
    u = User(name='Moling', email='test@orm.org', password='pw')
    print(u)
    # 保存到数据库：
    u.save()
