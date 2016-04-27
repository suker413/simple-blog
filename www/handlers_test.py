#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Date    : 2016-04-25 17:10:10
# @Author  : Your Name (you@example.org)
# @Link    : http://example.org
# @Version : $Id$
import asyncio, time, os
from aiohttp import web
from web_frame import get, post
from models import User, Blog, Comment

@get('/uesrs')
async def get_users():
    users = await User.findAll()
    return {
        '__template__': 'test.html',
        'users': users
    }

@get('/blogs')
def blogs(request):
    summary = 'Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.'
    blogs = [
        Blog(id='1', name='Test Blog', summary=summary, created_at=time.time()-120),
        Blog(id='2', name='Something New', summary=summary, created_at=time.time()-3600),
        Blog(id='3', name='Learn Swift', summary=summary, created_at=time.time()-7200)
    ]
    return {
        'blogs': blogs
    }

@get('/')
def index():
    return web.Response(body=b'<h1>hello world</h1>')

@get('/o')
def other():
    return '<h1>hi, other world</h1>'

@get('/json')
async def print_json():
    return {'name': 'admin', 'email': 'admin@orm.org'}

@get('/list')
def print_list():
    return list(range(0, 100, 5))

@get('/404')
def get_num():
    return (404, 'the page is found...')


@get('/hello/{name}')
def say_hello(*, name):
    return 'hello %s' % (name)


