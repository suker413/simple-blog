#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Date    : 2016-04-25 16:46:49
# @Author  : Your Name (you@example.org)
# @Link    : http://example.org
# @Version : $Id$

import asyncio, functools, inspect, logging, os

from aiohttp import web

from apis import APIError

#--------------------------------------------------------------------------------------
def get(path):
    '''
    Define decorator @get('/path')
    '''
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'GET'
        wrapper.__route__ = path
        return wrapper
    return decorator

def post(path):
    '''
    Define decorator @post('/path')
    '''
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'POST'
        wrapper.__route__ = path
        return wrapper
    return decorator

#--------------------------------------------------------------------------------------
class RequestHandler(object):
    def __init__(self, func):
        self._func = func

    async def __call__(self, request):
        # 获取函数的参数表
        args = list(inspect.signature(self._func).parameters)
        logging.info('required args: %s' % str(args))
        # 获取match_info的参数值，例如@get('/blog/{id}')之类的参数值
        kw = dict(**request.match_info)
        # 获取从data_factory函数处理过的参数值
        for key, value in request.__data__.items():
            # 如果函数的参数表有这参数名就加入
            if key in args:
                kw[key] = value
            else:
                logging.info('param %s not in args list' % key)
        # 如果有request参数的话也加入
        if 'request' in args:
            kw['request'] = request

        logging.info('call with args: %s' % str(kw))
        try:
            return await self._func(**kw)
        except APIError as e:
            return dict(error=e.error, data=e.data, message=e.message)

#-------------------------------------------------------------------------------------
def add_route(app, func):
    method = getattr(func, '__method__', None)
    path = getattr(func, '__route__', None)
    if None in (method, path):
        raise ValueError('@get or @post not defined in %s.' % str(func))
    if not asyncio.iscoroutinefunction(func) and not inspect.isgeneratorfunction(func):
        func = asyncio.coroutine(func)

    args = ', '.join(inspect.signature(func).parameters.keys())
    logging.info('add route %s %s => %s(%s)' % (method, path, func.__name__, args))
    app.router.add_route(method, path, RequestHandler(func))

def add_routes(app, module_name):
    n = module_name.rfind('.')
    if n == -1:
        mod = __import__(module_name, globals(), locals())
    else:
        name = module_name[n+1:]
        mod = getattr(__import__(module_name[:n], globals(), locals(), [name]), name)
    for attr in dir(mod):
        if attr.startswith('_'):
            continue
        func = getattr(mod, attr)
        if callable(func):
            method = getattr(func, '__method__', None)
            path = getattr(func, '__route__', None)
            if method and path:
                add_route(app, func)

def add_static(app):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    app.router.add_static('/static/', path)
    logging.info('add static %s => %s' % ('/static/', path))