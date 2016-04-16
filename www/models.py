# -*- coding: utf-8 -*-
"""
Created on Tue Apr 12 09:40:51 2016

@author: Administrator
"""
import time, uuid
from Fields import *
from orm import Model

import functools
StringField = functools.partial(StringField, ddl='varchar(50)')

def next_id():
    return '%015d%s000' % (int(time.time() * 1000), uuid.uuid4().hex)

# 定义用户类
class User(Model):
    __table__ = 'users'

    id = StringField(primary_key=True, default=next_id)
    email = StringField()
    password = StringField()
    admin = BooleanField()
    name = StringField()
    image = StringField(ddl='varchar(500)')
    created_at = FloatField(default=time.time)

# 定义博客类
class Blog(Model):
    __table__ = 'blogs'

    id = StringField(primary_key=True, default=next_id)
    user_id = StringField()
    user_name = StringField()
    user_image = StringField(ddl='varchar(500)')
    name = StringField()
    summary = StringField(ddl='varchar(200)')
    content = TextField()
    created_at = FloatField(default=time.time)

# 定义评论类
class Comment(Model):
    __table__ = 'comments'

    id = StringField(primary_key=True, default=next_id)
    blog_id = StringField()
    user_id = StringField()
    user_name = StringField()
    user_image = StringField(ddl='varchar(500)')
    content = TextField()
    created_at = FloatField(default=time.time)

if __name__ == '__main__':
    import aiomysql, asyncio, orm
    loop = asyncio.get_event_loop()


    async def orm_test():

        pool = await orm.create_pool(loop, user='simpleblog',
                                        password='test', db='simpleblog')
        #--------------------测试insert into语句---------------------
        for i in range(10):
            u = User(name='test%s'%str(i), email='test%s@orm.org'%str(i),
                        password='pw', image='test.jpg')
            await u.save(pool)
        #--------------------测试select语句--------------------------
        users = await User.findAll(pool, orderBy='email desc', limit=(0,5))
        for user in users:
            print(user.name)
        #--------------------测试update语句--------------------------
        user = users[0]
        user.name = 'new name'
        await user.update(pool)
        pk = user[User.__primary_key__]
        test_user = await User.find(pool, pk)
        assert test_user[User.__primary_key__] == pk, 'found a wrong guy'
        assert user.name == test_user.name, 'Update was failed'
        #--------------------测试delete语句-------------------------
        users = await User.findAll(pool, orderBy='name desc', limit=(0,10))
        for user in users:
            await user.remove(pool)

    loop.run_until_complete(orm_test())


