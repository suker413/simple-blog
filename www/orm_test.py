#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Date    : 2016-04-18 15:16:32
# @Author  : Your Name (you@example.org)
# @Link    : http://example.org
# @Version : $Id$
import asyncio
from orm import create_pool
from models import User


async def test():
    await create_pool(loop, user='simpleblog',
                            password='test', db='simpleblog')

    #--------------------测试insert into语句---------------------
    users = await User.findAll()
    if len(users) == 0:
        for i in range(5):
            u = User(name='test%s'%str(i), email='test%s@orm.org'%str(i),
                        password='pw', image='test.jpg')
            await u.save()

    #--------------------测试select语句--------------------------
    users = await User.findAll(orderBy='email desc')
    for user in users:
        print(user.name)

    #--------------------测试update语句--------------------------
    user = users[0]
    u = User(id = user.id, name='new ame', email='new@orm.org', admin=True,
            password='new pw', image='new.jpg', created_at=user.created_at)
    await u.update()
    new_user = await User.find(user.id)
    assert new_user.id == user.id, 'different id'
    print('new user: %s' % str(new_user))

    #--------------------测试delete语句-------------------------
    users = await User.findAll('email = ?', ['new@orm.org'])
    for user in users:
        await user.remove()

loop = asyncio.get_event_loop()
loop.run_until_complete(test())