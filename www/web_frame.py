#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Date    : 2016-04-25 16:46:49
# @Author  : Your Name (you@example.org)
# @Link    : http://example.org
# @Version : $Id$

import asyncio, functools, inspect, logging, os, json

from urllib import parse
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
    def __init__(self, app, func):
        self._app = app
        self._func = func
        self._kw = {}
        self._has_request_arg = False
        self._has_var_kw_arg = False
        self._has_named_kw_args = False
        self._named_kw_args = []
        self._required_kw_args = []
        self.init()

    def init(self):
        sig = inspect.signature(self._func)
        params = sig.parameters
        for name, param in params.items():
            if param.kind == inspect.Parameter.KEYWORD_ONLY:
                self._has_named_kw_args = True
                self._named_kw_args.append(name)
                if param.default == inspect.Parameter.empty:
                    self._required_kw_args.append(name)
            if param.kind == inspect.Parameter.VAR_KEYWORD:
                self._has_var_kw_arg = True
            if name == 'request':
                self._has_request_arg = True
                continue
            if self._has_request_arg and param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD:
                raise ValueError('request must be the last named parameter in function: %s%s' % (self._func.__name__, str(sig)))

        self._named_kw_args = tuple(self._named_kw_args)
        self._required_kw_args = tuple(self._required_kw_args)

    def __str__(self):
        s = 'has request arg: %s\n' % str(self._has_request_arg)
        s += 'has var kw arg: %s\n' % str(self._has_var_kw_arg)
        s += 'has named kw args: %s\n' % str(self._has_named_kw_args)
        s += 'named kw args: %s\n' % str(self._named_kw_args)
        s += 'required kw args: %s\n' % str(self._required_kw_args)
        return s

    async def __call__(self, request):
        if request.method == 'POST':
            self._kw = request.__data__
        elif request.method == 'GET':
            self._kw = dict(**request.match_info)

        if self._has_request_arg:
            self._kw['request'] = request
        print('args: %s' % str(self._kw))
        return await self._func(**self._kw)


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
    app.router.add_route(method, path, RequestHandler(app, func))

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

if __name__ == '__main__':
    def foo(*, a, request, b):
        pass
    print(RequestHandler('', foo))