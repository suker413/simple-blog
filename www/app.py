# -*- coding: utf-8 -*-
"""
Created on Tue Apr 12 08:16:45 2016

@author: Administrator
"""

import logging
logging.basicConfig(level=logging.INFO)

import asyncio, os, json, time, datetime

from aiohttp import web
from jinja2 import Environment, FileSystemLoader

from orm import create_pool
from web_frame import add_static, add_routes
from handlers import COOKIE_NAME, cookie2user



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
    path = kw.get('path', None)
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    logging.info('set jinja2 templates path: %s' % path)
    env = Environment(loader=FileSystemLoader(path), **options)
    filters = kw.get('filters', None)
    if filters is not None:
        for key, val in filters.items():
            env.filters[key] = val
    app['__templating__'] = env

async def logger_factory(app, handler):
    async def logger(request):
        logging.info('Request: %s, %s' % (request.method, request.path))
        return (await handler(request))
    return logger



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
        return (await handler(request))
    return auth

async def data_factory(app, handler):
    async def parse_data(request):
        if request.method == 'POST':
            if request.content_type.startswith('application/json'):
                request.__data__ = await request.json()
                logging.info('request json: %s' % str(request.__data__))
            elif request.content_type.startswith('application/x-www-form-urlencoded'):
                request.__data__ = await request.post()
                logging.info('request form: %s' % str(request.__data__))
        return (await handler(request))
    return parse_data

# 响应处理
# 总结下来一个请求在服务端收到后的方法调用顺序是:
#       logger_factory->response_factory->RequestHandler().__call__->get或post->handler
# 那么结果处理的情况就是:
#       由handler构造出要返回的具体对象
#       然后在这个返回的对象上加上'__method__'和'__route__'属性，以标识别这个对象并使接下来的程序容易处理
#       RequestHandler目的就是从URL函数中分析其需要接收的参数，从request中获取必要的参数，调用URL函数,然后把结果返回给response_factory
#       response_factory在拿到经过处理后的对象，经过一系列对象类型和格式的判断，构造出正确web.Response对象，以正确的方式返回给客户端
# 在这个过程中，我们只用关心我们的handler的处理就好了，其他的都走统一的通道，如果需要差异化处理，就在通道中选择适合的地方添加处理代码。
# 在response_factory中应用了jinja2来套用模板

async def response_factory(app, handler):

    async def response(request):
        logging.info('Response handler...')
        # 调用相应的handler处理request
        r = await handler(request)
        logging.info('r = %s' % str(r))
        # 如果响应结果为web.StreamResponse类，则直接把它作为响应返回
        if isinstance(r, web.StreamResponse):
            return r
        # 如果响应结果为字节流，则把字节流塞到response的body里，设置响应类型为流类型，返回
        if isinstance(r, bytes):
            resp = web.Response(body=r)
            resp.content_type = 'application/octet-stream'
            return resp
        # 如果响应结果为字符串
        if isinstance(r, str):
            # 先判断是不是需要重定向，是的话直接用重定向的地址重定向
            if r.startswith('redirect:'):
                return web.HTTPFound(r[9:])
            # 不是重定向的话，把字符串当做是html代码来处理
            resp = web.Response(body=r.encode('utf-8'))
            resp.content_type = 'text/html;charset=utf-8'
            return resp
        # 如果响应结果为字典
        if isinstance(r, dict):
            # 先查看一下有没有'__template__'为key的值
            template = r.get('__template__')
            # 如果没有，说明要返回json字符串，则把字典转换为json返回，对应的response类型设为json类型
            if template is None:
                resp = web.Response(body=json.dumps(r, ensure_ascii=False,
                                        default=lambda o: o.__dict__).encode('utf-8'))
                resp.content_type = 'application/json;charset=utf-8'
                return resp
            else:
                # 如果有'__template__'为key的值，则说明要套用jinja2的模板，'__template__'Key对应的为模板网页所在位置
                resp = web.Response(body=app['__templating__'].get_template(
                    template).render(**r).encode('utf-8'))
                resp.content_type = 'text/html;charset=utf-8'
                # 以html的形式返回
                return resp
        # 如果响应结果为int
        if isinstance(r, int) and r >= 100 and r < 600:
            return web.Response(r)
        # 如果响应结果为tuple且数量为2
        if isinstance(r, tuple) and len(r) == 2:
            t, m = r
            # 如果tuple的第一个元素是int类型且在100到600之间，这里应该是认定为t为http状态码，m为错误描述
            # 或者是服务端自己定义的错误码+描述
            if isinstance(t, int) and t >= 100 and t < 600:
                return web.Response(status=t, text=str(m))
            # default: 默认直接以字符串输出
            resp = web.Response(body=str(r).encode('utf-8'))
            resp.content_type = 'text/plain;charset=utf-8'
            return resp
    return response

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
    await create_pool(loop=loop, user='simpleblog', password='test', db='simpleblog')
    app = web.Application(loop=loop, middlewares=[logger_factory,auth_factory,response_factory])
    init_jinja2(app, filters=dict(datetime=datetime_filter))
    add_routes(app, 'handlers')
    add_static(app)

    srv = await loop.create_server(app.make_handler(), '127.0.0.1', 9000)
    logging.info('server started at http://127.0.0.1:9000...')
    return srv

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(init(loop))
    loop.run_forever()