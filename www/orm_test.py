#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio, logging
from orm import create_pool
from models import User, Comment

async def test():
    await create_pool(loop, user='simpleblog',
                            password='test', db='simpleblog')

    #--------------------测试count rows语句---------------------
    rows = await User.countRows('id')
    logging.info('rows is: %s' % rows)

    #-------------------测试insert into语句---------------------
    if rows < 3:
        for idx in range(1, 4):
            u = User(name='test%s'%(idx), email='test%s@orm.org'%(idx),
                        password='pw', image='test.jpg')
            await u.save()

    #--------------------测试select语句--------------------------
    users = await User.findAll(orderBy='created_at')
    for user in users:
        logging.info('name: %s, email: %s' %(user.name, user.email))

    #--------------------测试update语句--------------------------
    user = users[2]
    user.email = 'updated@sina.com'
    await user.update()

    #--------------------测试查找指定用户-------------------------
    test_user = await User.find(user.id)
    logging.info('name: %s, email: %s' %(user.name, user.email))

    #--------------------测试delete语句-------------------------
    users = await User.findAll(orderBy='created_at', limit=(2, 1))
    for user in users:
        await user.remove()


loop = asyncio.get_event_loop()
loop.run_until_complete(test())