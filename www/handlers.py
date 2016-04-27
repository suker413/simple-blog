#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Date    : 2016-04-25 17:10:10
# @Author  : Your Name (you@example.org)
# @Link    : http://example.org
# @Version : $Id$
import asyncio, logging, hashlib, json, markdown2, re, time, os

from aiohttp import web

from apis import Page, APIValueError, APIResourceNotFoundError
from web_frame import get, post
from models import User, Blog, Comment, next_id
from config import configs

COOKIE_NAME = 'awesession'
_COOKIE_KEY = configs.session.secret
_RE_EMAIL = re.compile(r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
_RE_SHA1 = re.compile(r'^[0-9a-f]{40}$')

def get_page_index(page_str):
    try:
        return max(int(page_str), 1)
    except ValueError:
        return 1

def text2html(text):
    lines = map(lambda s: '<p>%s</p>' % s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'), filter(lambda s: s.strip() != '', text.split('\n')))
    return ''.join(lines)

def user2cookie(user, max_age):
    '''
    Generate cookie str by user.
    '''
    # build cookie string by: id-expires-sha1
    expires = str(int(time.time() + max_age))
    s = '%s-%s-%s-%s' % (user.id, user.password, expires, _COOKIE_KEY)
    L = [user.id, expires, hashlib.sha1(s.encode('utf-8')).hexdigest()]
    return '-'.join(L)

async def cookie2user(cookie_str):
    '''
    Parse cookie and load user if cookie is valid.
    '''
    if not cookie_str:
        return None
    try:
        L = cookie_str.split('-')
        if len(L) != 3:
            return None
        uid, expires, sha1 = L
        if int(expires) < time.time():
            return None
        user = await User.find(uid)
        if user is None:
            return None
        s = '%s-%s-%s-%s' % (uid, user.password, expires, _COOKIE_KEY)
        if sha1 != hashlib.sha1(s.encode('utf-8')).hexdigest():
            logging.info('invalid sha1')
            return None
        user.passwd = '******'
        return user
    except Exception as e:
        logging.exception(e)
        return None

def check_admin(request):
    if request.__user__ is None or not request.__user__.admin:
        raise APIPermissionError()

def check_string(**kw):
    for field, string in kw.items():
        if not string or not string.strip():
            raise APIValueError(field, '%s cannot be empty.' % field)

@get('/')
async def index(*, page='1'):
    num = await Blog.countRows('id')
    page_info = Page(num, get_page_index(page))
    if num == 0:
        blogs = []
    else:
        blogs = await Blog.findAll(orderBy='created_at desc', limit=(page_info.offset, page_info.limit))
    return {
        '__template__': 'blogs.html',
        'page': page_info,
        'blogs': blogs
    }

@get('/blog/{id}')
async def get_bolg(id):
    blog = await Blog.find(id)
    comments = await Comment.findAll('blog_id = ?', [id], orderBy='created_at desc')
    for c in comments:
        c.html_content = text2html(c.content)
    blog.html_content = markdown2.markdown(blog.content)
    return {
        '__template__': 'blog.html',
        'blog': blog,
        'comments': comments
    }

# 注册一个新用户
@get('/register')
def register():
    return {
        '__template__': 'register.html'
    }

@post('/api/users')
async def api_register_user(*, email, name, password):
    if not name or not name.strip():
        raise APIValueError('name')
    if not email or not _RE_EMAIL.match(email):
        raise APIValueError('email')
    if not password or not _RE_SHA1.match(password):
        raise APIValueError('password')
    users = await User.findAll('email = ?', [email])
    if len(users) > 0:
        raise ('register:failed', 'email', 'Email is already in use.')
    uid = next_id()
    sha1_pw = '%s:%s' % (uid, password)
    user = User(id=uid, name=name.strip(), email=email, password=hashlib.sha1(sha1_pw.encode('utf-8')).hexdigest(), image='empty')
    await user.save()
    # make session cookie
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.password = '******'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r

# 用户登陆
@get('/signin')
def signin():
    return {
        '__template__': 'signin.html'
    }

@post('/api/authenticate')
async def authenticate(*, email, password):
    if not email:
        raise APIValueError('email', 'Invalid email.')
    if not password:
        raise APIValueError('password', 'Invalid password.')
    users = await User.findAll('email = ?', [email])
    if len(users) == 0:
        raise APIValueError('email', 'Email not exist.')
    user = users[0]
    # check password
    sha1 = hashlib.sha1()
    sha1.update(user.id.encode('utf-8'))
    sha1.update(b':')
    sha1.update(password.encode('utf-8'))
    if user.password != sha1.hexdigest():
        raise APIValueError('password', 'Invalid password')
    # authenticate ok, set cookie
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.passwd = '******'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r

# 注销用户
@get('/signout')
def signout(request):
    referer = request.headers.get('Referer')
    r = web.HTTPFound(referer or '/')
    # 清理掉cookie得用户信息数据
    r.set_cookie(COOKIE_NAME, '-deleted-', max_age=0, httponly=True)
    logging.info('user signed out')
    return r

@get('/manage')
def manage():
    return 'redirect:/manage/blogs'

@get('/manage/{table}')
def manage_table(table, *, page='1'):
    return {
        '__template__': 'manage_%s.html' % table,
        'page_index': get_page_index(page)
    }

@get('/api/{table}')
async def api_model(table, *, page=1):
    models = {'users': User, 'blogs': Blog, 'comments': Comment}
    num = await models[table].countRows('id')
    page_info = Page(num, get_page_index(page))
    if num == 0:
        return { 'page': page_info, table: () }
    items = await models[table].findAll(orderBy='created_at desc', limit=(page_info.offset, page_info.limit))
    return { 'page': page_info, table: items }

# 创建博客
@get('/manage/blogs/create')
def manage_create_blog():
    return {
        '__template__': 'manage_blog_edit.html',
        'id': '',
        'action': '/api/blogs'
    }

@post('/api/blogs')
async def api_create_blog(request, *, name, summary, content):
    check_admin(request)
    check_string(name=name, summary=summary, content=content)
    blog = Blog(user_id=request.__user__.id, user_name=request.__user__.name, user_image=request.__user__.image,
                        name=name.strip(), summary=summary.strip(), content=content.strip())
    await blog.save()
    return blog

# 更改或删除博客
@get('/manage/blogs/edit')
def manage_edit_blog(id):
    return {
        '__template__': 'manage_blog_edit.html',
        'id': id,
        'action': '/api/blogs/%s' % id
    }

@post('/api/blogs/{id}')
async def api_update_blog(id, request, *, name, summary, content):
    check_admin(request)
    check_string(name=name, summary=summary, content=content)
    blog = await Blog.find(id)
    blog.name = name.strip()
    blog.summary = summary.strip()
    blog.content = content.strip()
    await blog.update()
    return blog

@post('/api/{table}/{id}/delete')
async def api_delete_item(table, id, request):
    models = {'blogs': Blog, 'comments': Comment}
    check_admin(request)
    item = await models[table].find(id)
    if item:
        await item.remove()
    return dict(id=id)

@get('/api/blogs/{id}')
async def api_get_blog(id):
    return await Blog.find(id)

@post('/api/blogs/{id}/comments')
async def api_create_comment(id, request, *, content):
    user = request.__user__
    if user is None:
        raise APIPermissionError('Please signin first.')
    if not content or not content.strip():
        raise APIValueError('content')
    blog = await Blog.find(id)
    if blog is None:
        raise APIResourceNotFoundError('Blog')
    comment = Comment(blog_id=blog.id, user_id=user.id, user_name=user.name, user_image=user.image, content=content.strip())
    await comment.save()
    return comment