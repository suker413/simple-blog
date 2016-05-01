# -*- coding: utf-8 -*-
"""
Created on Tue Apr 12 08:16:45 2016

@author: Administrator
"""

import logging
logging.basicConfig(level=logging.INFO)

import asyncio, json, time, os


from aiohttp import web
from datetime import datetime
from urllib import parse
from jinja2 import Environment, FileSystemLoader

from orm import create_pool
from web_frame import add_routes, add_static
from handlers import COOKIE_NAME, cookie2user
from config import configs

 # 初始化jinja2
def init_jinja2(app, **kw):
    logging.info('init jinja2...')
    options = dict(
        autoescape = kw.get('autoescape', True),
        block_start_string = kw.get('block_start_string', '{%'),
        block_end_string = kw.get('block_end_string', '%}'),
        variable_start_string = kw.get('variable_start_string', '{{'),
        variable_end_string = kw.get('variable_end_string', '}}'),
        auto_reload = kw.get('auto_reload', True)
    )
    path = kw.get('path', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates'))
    logging.info('set jinja2 template path: %s' % path)
    env = Environment(loader=FileSystemLoader(path), **options)
    filters = kw.get('filters')
    if filters is not None:
        for name, ftr in filters.items():
            env.filters[name] = ftr
    app['__templating__'] = env

#--------------------------工厂函数------------------------------------
# 在每个响应之前打印日志
async def logger_factory(app, handler):
    async def logger(request):
        print()
        logging.info('Response: %s %s' %(request.method, request.path))
        return await handler(request)
    return logger

# 通过cookie找到当前用户信息，把用户绑定在request.__user__
async def auth_factory(app, handler):
    async def auth(request):
        logging.info('check user: %s %s' % (request.method, request.path))
        request.__user__ = None
        cookie_str = request.cookies.get(COOKIE_NAME)
        if cookie_str:
            user = await cookie2user(cookie_str)
            if user:
                logging.info('set current user: %s' % user.email)
                request.__user__ = user
        if request.path.startswith('/manage/') and (request.__user__ is None or not request.__user__.admin):
            return web.HTTPFound('/')
        return await handler(request)
    return auth

# 把任何返回值封装成浏览器可正确显示的Response对象
async def response_factory(app, handler):
    async def response(request):
        logging.info('Response handler...')
        r = await handler(request)
        if  isinstance(r, web.StreamResponse):
            return r
        if isinstance(r, bytes):
            resp = web.Response(body=r)
            resp.content_type = 'application/octet-stream'
            return resp
        if isinstance(r, str):
            if r.startswith('redirect:'):
                return web.HTTPFound(r[9:])
            resp = web.Response(body=r.encode('utf-8'))
            resp.content_type = 'text/html;charset=utf-8'
            return resp
        if isinstance(r, dict):
            template = r.get('__template__')
            if template is None:
                resp = web.Response(body=json.dumps(r, ensure_ascii=False,
                        default=lambda o: o.__dict__).encode('utf-8'))
                resp.content_type = 'application/json;charset=utf-8'
                return resp
            else:
                # 如果用jinja2渲染，绑定已验证过的用户
                r['__user__'] = request.__user__
                resp = web.Response(body=app['__templating__'].get_template(template).render(**r).encode('utf-8'))
                resp.content_type = 'text/html;charset=utf-8'
                return resp
        if isinstance(r, int) and 100 <= r < 600:
            return web.Response(status=r)
        if isinstance(r, tuple) and len(r) == 2:
            status, message = r
            if isinstance(status, int) and 100 <= status < 600:
                return web.Response(status=status, text=str(message))
        # default
        resp = web.Response(body=str(r).encode('utf-8'))
        resp.content_type = 'text/plain;charset=utf-8'
        return resp
    return response

# 把GET和POST返回的数据绑定在request.__data__
# 以便在ResponseHandler函数内部使用
async def data_factory(app, handler):
    async def  parse_data(request):
        # 把数据封装为一个字典
        request.__data__ = dict()
        # 从POST方法截取数据
        if request.method == 'POST':
            if request.content_type.startswith('application/json'):
                request.__data__ = await request.json()
            elif request.content_type.startswith('application/x-www-form-urlencoded'):
                request.__data__ = await request.post()
        # 从GET方法截取数据
        elif request.method == 'GET':
            qs = request.query_string
            request.__data__ = {k: v[0] for k, v in parse.parse_qs(qs, True).items()}
        logging.info('parsed data: %s' % str(request.__data__))
        return await handler(request)
    return parse_data

def datetime_filter(t):
    delta = int(time.time() - t)
    if delta < 60:
        return u'1分钟前'
    if delta < 3600:
        return u'%s分钟前' % (delta // 60)
    if delta < 86400:
        return u'%s小时前' % (delta // 3600)
    if delta < 604800:
        return u'%s天前' % (delta // 86400)
    dt = datetime.fromtimestamp(t)
    return u'%s年%s月%s日' % (dt.year, dt.month, dt.day)

async def init(loop):
    await create_pool(loop, **configs.db)
    app = web.Application(loop=loop, middlewares=[
        logger_factory, auth_factory, response_factory, data_factory])
    init_jinja2(app, filters=dict(datetime=datetime_filter))

    add_static(app)
    add_routes(app, 'handlers')

    srv = await loop.create_server(app.make_handler(), '127.0.0.1', 9000)
    logging.info('server started at http://127.0.0.1:9000...')
    return srv

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(init(loop))
    loop.run_forever()