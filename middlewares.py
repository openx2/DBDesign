#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'cx'

'''
middlewares used by the application
'''

import asyncio, logging, json, datetime

from aiohttp import web
from handlers import cookie2user, json_default, COOKIE_NAME

async def logger_factory(app, handler):
    async def logger(request):
        logging.info('Request: %s %s' % (request.method, request.path))
        return (await handler(request))
    return logger

#响应处理
#总结下来一个请求在服务端收到后的方法调用顺序是:
#       logger_factory->response_factory->RequestHandler().__call__->get或post->handler
#那么结果处理的情况就是:
#       由handler构造出要返回的具体对象
#       然后在这个返回的对象上加上'__method__'和'__route__'属性，以标识别这个对象并使接下来的程序容易处理
#       RequestHandler目的就是从URL函数中分析其需要接收的参数，从request中获取必要的参数，调用URL函数，然后把结果返回给response_factory
#       response_factory在拿到经过处理后的对象，经过一系列对象类型和格式的判断，构造出正确web.Response对象，以正确的方式返回给客户端
#在这个过程中，我们只用关心我们的handler的处理就好了，其他的都走统一的通道，如果需要差异化处理，就在通道中选择适合的地方添加处理代码
async def response_factory(app, handler):
    async def response(request):
        logging.info('Response handler...')
        #调用相应的handler处理request
        r = await handler(request)
        logging.info('r = %s' % str(r))
        #如果响应结果为web.StreamResponse类的实例，直接把它作为响应返回
        if isinstance(r, web.StreamResponse):
            return r
        #如果响应结果为字节流，把它放到response的body中，设置响应类型为流类型
        if isinstance(r, bytes):
            resp = web.Response(body=r)
            resp.content_type = 'application/octet-stream'
            return resp
        #如果响应结果为字符串
        if isinstance(r, str):
            #先判断是否要重定向，是的话直接用重定向的地址重定向
            if r.startswith('redirect:'):
                return web.HTTPFound(r[9:])
            #如果不是重定向的话，把字符串当作html代码来处理
            resp = web.Response(body=r.encode('utf-8'))
            resp.content_type = 'text/html;charset=utf-8'
            return resp
        #如果响应结果为字典
        if isinstance(r, dict):
            #先查看一下是否有以'__template__'为key的值
            template = r.get('__template__', None)
            #如果没有，说明要返回json字符串，则把字典转换为json返回，响应类型设为json类型
            if template is None:
                resp = web.Response(body=json.dumps(r, ensure_ascii=False,
                                default=json_default).encode('utf-8'))
                resp.content_type = 'application/json;charset=utf-8'
                return resp
            else:
                r['__user__'] = request.__user__
                #如果有'__template__'为key的值，则说明要使用jinja2的模板，template就是模板的名字
                template_instance = app['__templating__'].get_template(template)
                template_instance.globals['datetime'] = datetime
                resp = web.Response(
                    body=template_instance.render(**r).encode('utf-8')
                )
                resp.content_type = 'text/html;charset=utf-8'
                #以html的形式返回
                return resp
        #响应结果为int，即状态码
        if isinstance(r, int) and r>=100 and r < 600:
            return web.Response(status=r)
        #如果响应结果为tuple且元素数为2
        if isinstance(r, tuple) and len(r) == 2:
            t, m = r
            #如果tuple的第一个元素为int且在100到600之间，应该认为t是http状态码，m为错误描述
            #或者是服务器端自己定义的错误码+描述
            if isinstance(t, int) and t>=100 and t < 600:
                return web.Response(status=t, text=str(m))
        #default: 默认直接以字符串输出
        resp = web.Response(body=str(r).encode('utf-8'))
        resp.content_type = 'text/plain;charset=utf-8'
        return resp
    return response

async def auth_factory(app, handler):
    async def auth(request):
        logging.info('check user: %s %s' % (request.method, request.path))
        request.__user__ = None
        cookie_str = request.cookies.get(COOKIE_NAME)
        if cookie_str and not request.path.startswith('/static/'):
            user = await cookie2user(cookie_str)
            if user:
                logging.info('set current user: %s' % user.id)
                request.__user__ = user
        #如果没有得到__user__或权限不足
        if request.__user__ == None or (request.path.startswith('/manage/')
                                    and not request.__user__.authority == 0):
            #POST请求、/signin页面和静态资源不要跳转
            if request.method != 'POST' and request.path != '/signin' and \
                                    not request.path.startswith('/static/'):
                return web.HTTPFound('/signin')
        return (await handler(request))
    return auth

async def redirect_factory(app, handler):
    async def redirect(request):
        #如果用户存在且为管理员
        if request.__user__ and request.__user__.authority == 0:
            #GET请求时，/signin和/signout页面、静态资源和本来就以/manage/开头的url不要跳转
            if request.method == 'GET' \
               and request.path != '/signin' and request.path != '/signout' \
                               and not request.path.startswith('/static/') \
                                   and not request.path.startswith('/manage/'):
                return web.HTTPFound('/manage'+request.path)
        return (await handler(request))
    return redirect
