# -*- coding: utf-8 -*-
"""
Created on Tue Apr 12 08:16:45 2016

@author: Administrator
"""

import logging
logging.basicConfig(level=logging.INFO)

from aiohttp import web
import asyncio

def index(request):
    return web.Response(body=b'<h1>hello world</h1>')

def other(request):
    return web.Response(body=b'<h1>hello, other world</h1>')

async def init(loop):
    app = web.Application(loop=loop)
    app.router.add_route('GET', '/', index)
    app.router.add_route('GET', '/other', other)
    srv = await loop.create_server(app.make_handler(), '127.0.0.1', 9000)
    logging.info('server started at http://127.0.0.1:9000...')
    return srv

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(init(loop))
    loop.run_forever()