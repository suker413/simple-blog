#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Date    : 2016-04-17 11:09:06
# @Author  : Your Name (you@example.org)
# @Link    : http://example.org
# @Version : $Id$

import asyncio, functools, logging, inspect, os
from aiohttp import web
from apis import APIError
from urllib import parse

def get(path):
    '''
    Define decorator @get('/path')
    '''
    def decorater(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'GET'
        wrapper.__route__ = path
        return wrapper
    return decorater

def post(path):
    '''
    Define decorator @post('/path')
    '''
    def decorater(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'POST'
        wrapper.__route__ = path
        return wrapper
    return decorater

# --使用inspect模块中的signature方法来获取函数的参数，实现一些复用功能--
# 关于inspect.Parameter的 kind 类型有5种：
# def foo(a, *b, c, **d): pass
# a : POSITIONAL_OR_KEYWORD # 可以通过位置和名字来设置参数
# b : VAR_POSITIONAL        # 可变长列表参数
# c : KEYWORD_ONLY          # 只能通过名字才能设置参数，这种参数是在可变长列表后面
# d : VAR_KEYWORD           # 可变长字典参数
#     POSITIONAL_ONLY       # 这类型多是出现在内置函数或扩展模块
def kw_only_empty_args(fn):
    args = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY and param.default == inspect.Parameter.empty:
            args.append(name)
    return tuple(args)

def kw_only_args(fn):
    args = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            args.append(name)
    return tuple(args)

def has_kw_only(fn):
    params = inspect.signature(fn).parameters.values()
    return any(param.kind == inspect.Parameter.KEYWORD_ONLY for param in params)


def has_var_kw(fn):
    params = inspect.signature(fn).parameters.values()
    return any(param.kind == inspect.Parameter.VAR_KEYWORD for param in params)

def has_request(fn):
    sig = inspect.signature(fn)
    params = sig.parameters
    found = False
    for name, param in params.items():
        if name == 'request':
            found = True
            continue
        if found and param.kind not in (inspect.Parameter.VAR_KEYWORD, inspect.Parameter.POSITIONAL_ONLY):
            raise ValueError('request parameter must be the last named parameter in function: %s%s' % (fn.__name__, str(sig)))
    return found

class RequestHandler(object):

    def __init__(self, app, fn):
        self._app = app
        self._func = fn
        self._has_request = has_request(fn)                 # 有没request参数
        self._has_var_kw = has_var_kw(fn)                   # 有没变长字典参数
        self._has_kw_only = has_kw_only(fn)                 # 有没只有kw才能设置的参数
        self._kw_only_args = kw_only_args(fn)               # 只能靠kw设置的参数集
        self._kw_only_empty_args = kw_only_empty_args(fn)   # 只能靠kw设置且不带默认的参数集



    def __str__(self):
        s  = 'function: %s%s\n' % (self._func.__name__, str(inspect.signature(self._func)))
        s += '有没request参数: %s\n' % str(self._has_request)
        s += '有没只能靠kw设置的参数: %s\n' % str(self._has_kw_only)
        s += '有没变长字典参数: %s\n' % str(self._has_var_kw)
        s += '只能靠kw设置的参数集: %s\n' % str(self._kw_only_args)
        s += '只能靠kw设置且不带默认的参数集: %s' % str(self._kw_only_empty_args)
        return s

    async def __call__(self, request):
        kw = None
        if any((self._has_request, self._has_var_kw, self._has_kw_only)):
            if request.method == 'POST':
                if not request.content_type:
                    return web.HTTPBadRequest('Missing Content-Type.')
                ct = request.content_type.lower()
                if ct.startswith('application/json'):
                    params = await request.json()
                    if not isinstance(params, dict):
                        return web.HTTPBadRequest('JSON body must be object.')
                    kw = params  # 正确的话把request的参数信息给kw
                elif ct.startswith('application/x-www-form-urlencoded') or ct.startswith('multipart/form-data'):
                    params = await request.post()  # 调用post方法，注意此处已经使用了装饰器
                    kw = dict(**params)
                else:
                    return web.HTTPBadRequest('Unsupported Content-Type: %s' % request.content_type)

            if request.method == 'GET':
                qs = request.query_string
                if qs:
                    kw = dict()
                    # 该方法解析url中?后面的键值对内容保存到kw
                    for k, v in parse.parse_qs(qs, True).items():
                        kw[k] = v[0]
        if kw is None:
            kw = dict(**request.match_info)
        else:
            # 如果从Request对象中获取到参数了
            # 当没有可变参数，有命名关键字参数时候，kw指向命名关键字参数的内容
            if not self._has_var_kw and self._kw_only_args:
                # remove all unamed kw: 删除所有没有命名的关键字参数
                copy = dict()
                for name in self._kw_only_args:
                    if name in kw:
                        copy[name] = kw[name]
                kw = copy
                for k, v in request.match_info.items():
                    if k in kw: # 命名参数和关键字参数有名字重复
                        logging.warning('Duplicate arg name in named arg and kw args: %s' % k)
                        kw[k] = v
        # 如果有request这个参数，则把request对象加入kw['request']
        if self._has_request:
            kw['request'] = request
        # check required kw: 检查是否有必要关键字参数
        if self._kw_only_empty_args:
            for name in self._kw_only_empty_args:
                if name not in kw:
                    return web.HTTPBadRequest(text='Missing argument: %s' % name)
        logging.info('call with args: %s' % str(kw))
        try:
            r = await self._func(**kw)
            return r
        except APIError as e:
            return dict(error=e.error, data=e.data, message=e.message)

# 添加静态页面的路径
def add_static(app):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    # app是aiohttp库里面的对象，通过router.add_router方法可以指定处理函数。本节代码自己实现了add_router。关于更多请查看aiohttp的库文档：http://aiohttp.readthedocs.org/en/stable/web.html
    app.router.add_static('/static/', path)
    logging.info('add static %s => %s' % ('/static/', path))

def add_route(app, fn):
    # add_route函数，用来注册一个URL处理函数
    # 获取'__method__'和'__route__'属性，如果有空则抛出异常
    method = getattr(fn, '__method__', None)
    path = getattr(fn, '__route__', None)
    if path is None or method is None:
        raise ValueError('@get or @post not defined in %s.' % str(fn))
    # 判断fn是不是协程(即@asyncio.coroutine修饰的) 并且 判断是不是fn 是不是一个生成器(generator function)
    if not asyncio.iscoroutine(fn) and not inspect.isgeneratorfunction(fn):
        # 都不是的话，强行修饰为协程
        fn = asyncio.coroutine(fn)
    logging.info('add route %s %s => %s (%s)' % (method, path,
                        fn.__name__, ', '.join(inspect.signature(fn).parameters.keys())))
    # 正式注册为相应的url处理方法
    # 处理方法为RequestHandler的自省函数 '__call__'
    # logging.info(str(RequestHandler(app, fn)))
    app.router.add_route(method, path, RequestHandler(app, fn))

def add_routes(app, module_name):
    # 自动搜索传入的module_name的module的处理函数
    # 检查传入的module_name是否有'.'
    # Python rfind() 返回字符串最后一次出现的位置，如果没有匹配项则返回-1
    n = module_name.rfind('.')
    logging.info('n = %s', n)
    # 没有'.',则传入的是module名
    # __import__方法使用说明请看：
    if n == (-1):
        mod = __import__(module_name, globals(), locals())
        logging.info('globals = %s', globals()['__name__'])
    else:
        # name = module_name[n+1:]
        # mod = getattr(__import__(module_name[:n], globals(), locals(), [name]), name)
        # 上面两行是廖大大的源代码，但是把传入参数module_name的值改为'handlers.py'的话走这里是报错的，所以改成了下面这样
        mod = __import__(module_name[:n], globals(), locals())
    # 遍历mod的方法和属性,主要是招处理方法
    # 由于我们定义的处理方法，被@get或@post修饰过，所以方法里会有'__method__'和'__route__'属性
    for attr in dir(mod):
        # 如果是以'_'开头的，一律pass，我们定义的处理方法不是以'_'开头的
        if attr.startswith('_'):
            continue
        # 获取到非'_'开头的属性或方法
        fn = getattr(mod, attr)
        # 取能调用的，说明是方法
        if callable(fn):
            # 检测'__method__'和'__route__'属性
            method = getattr(fn, '__method__', None)
            path = getattr(fn, '__route__', None)
            if method and path:
                # 如果都有，说明是我们定义的处理方法，加到app对象里处理route中
                add_route(app, fn)

if __name__ == '__main__':
    # def foo(a, *b, request, **d):
    #     pass

    # print(RequestHandler(foo))
    print(os.path.abspath(__file__))
    print(os.path.dirname(os.path.abspath(__file__)))
    print(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static'))