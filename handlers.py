#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'cx'

import hashlib, json, time, logging

from aiohttp import web
import pymysql

from apis import APIError, APIValueError, APIPermissionError, APIResourceNotFoundError
from coroweb import get, post
from models import User, Employee, Department, LevelSalary, DimssionEmployee

@get('/')
def index():
    return web.Response(body=b'<b>OK</b>')

@get('/signin')
def signin():
    return {
        '__template__' : 'signin.html'
    }

@get('/signout')
def signout():
    r = web.HTTPFound('/signin')
    r.set_cookie(COOKIE_NAME, '-delete-', max_age=0, httponly=True)
    logging.info('user signed out.')
    return r

@get('/manage/')
def manage():
    return {
        '__template__' : 'manage.html'
    }

@get('/manage/signin')
def manage_signin():
    return {
        '__template__' : 'manage_signin.html'
    }

@get('/manage/change_password')
def manage_change_password():
    return {
        '__template__' : 'manage_change_password.html'
    }

@get('/manage/add_employee')
def manage_add_employee():
    return {
        '__template__' : 'manage_add_employee.html'
    }

@get('/manage/hide')
def hide():
    return {
        '__template__' : 'hide.html'
    }

salt = 'sdu'
GENERAL_MANAGER_LEVEL = 4
COOKIE_NAME = 'hr_dbdesign'
_COOKIE_KEY = 'software academy'

def user2cookie(user, max_age):
    '''
    Generate cookie str by user.
    '''
    #build cookie string by: id-expires-sha1
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
        s = '%s-%s-%s-%s' % (user.id, user.password, expires, _COOKIE_KEY)
        if sha1 != hashlib.sha1(s.encode('utf-8')).hexdigest():
            logging.info('invalid sha1')
            return None
        user.password = '******'
        return user
    except Exception as e:
        logging.exception(e)
        return None

def validateDate(date):
    if not date:
        raise APIValueError('date', 'Invalid date.')
    try:
        day = time.strptime(date, '%Y-%m-%d')
    except ValueError as e:
        raise APIValueError('date', e)
    if day > time.localtime(time.time()):
        raise APIValueError('date', '日期大于当前日期！')

async def validateDeptAndLeader(dept_num, leader_id, level):
    is_general_manager = \
                (level == GENERAL_MANAGER_LEVEL and dept_num is None and \
                                                             leader_id == '')
    if not is_general_manager:
        if not dept_num or not leader_id:
            raise APIValueError('department or leader empty', '部门编号或领导编号为空')
        if (await Department.find(dept_num)) is None:
            raise APIValueError('department', '该部门不存在')
        leader = await Employee.find(leader_id)
        if not leader or (leader.dno != dept_num and leader.level != \
                                                      GENERAL_MANAGER_LEVEL):
            raise APIValueError('leader', '该领导不存在')
        if level + 1 != leader.level:
            raise APIValueError('leader', '该领导无法成为新员工的直属上司')
    if is_general_manager and dept_num:
        raise APIValueError('department', '总经理不应该有部门编号')
    if is_general_manager and leader_id:
        raise APIValueError('leader', '总经理不应该有上司')
    #如果添加的员工是总经理且员工表中已经存在总经理，报错
    if is_general_manager and \
                        (await Employee.findAll('`level`=?', [level])) != []:
        raise APIValueError('duplicate general manager', '已经存在总经理')

async def getEmployeeID(join_date,dept_num):
    dept = await Department.find(dept_num)
    first_part = join_date.replace('-','')
    second_part = '%03d' % (dept_num or 0)
    third_part = '%09d' % dept.last_num if dept else '0'*9
    return first_part+second_part+third_part

@post('/api/authenticate')
async def authenticate(*, id, password):
    if not id:
        raise APIValueError('id', 'Invalid ID.')
    if not password:
        raise APIValueError('password', 'Invalid password.')
    users = await User.findAll('`id`=?', [id])
    if len(users) == 0:
        raise APIValueError('id', 'ID not exist.')
    user = users[0]
    #check password
    sha1 = hashlib.sha1((user.id+password+salt).encode('utf-8'))
    if user.password != sha1.hexdigest():
        raise APIValueError('password', 'Wrong password.')
    #authenticate ok, set cookie
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400,
                                                                httponly=True)
    user.password = '******'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r

@post('/api/change_password')
async def changePassword(request, *, password):
    if not password:
        raise APIValueError('password', 'Invalid password.')
    user = request.__user__
    #change password
    sha1 = hashlib.sha1((user.id +
             hashlib.sha1((user.id+password+salt).encode('utf-8')).hexdigest() +
                        salt).encode('utf-8'))
    user.password = sha1.hexdigest()
    await user.update()
    logging.info('user %s\'s password changed' % user.id)
    #change password ok, set cookie
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400,
                                                                httponly=True)
    user.password = '******'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r

@post('/api/add_employee')
async def addEmployee(*, name, sex, email, phone_number, join_date, level,
                                                       dept_number, leader_id):
    if not name:
        raise APIValueError('name', 'Invalid name.')
    if not level:
        raise APIValueError('level', 'Invalid level.')
    validateDate(join_date)
    await validateDeptAndLeader(dept_number, leader_id, level)
    #生成职员并添加到数据库中
    emp = Employee(id=(await getEmployeeID(join_date,dept_number)),
               name=name.strip(), sex=sex, email=email, phone_num=phone_number,
                           join_date=join_date, level=level, dno=dept_number,
                                   leader_id=leader_id if leader_id else None)
    await emp.save()
    logging.info('add employee: %s' % emp)
    #添加完毕，将生成的职员作为json返回
    return emp

@post('/api/delete_employee')
async def deleteEmployee(*, emp_id, leave_date):
    if not emp_id:
        raise APIValueError('emp_id', 'Invalid employee id.')
    emp = await Employee.find(emp_id)
    if not emp:
        raise APIValueError('emp_id', '该员工不存在！')
    if (await Employee.findNumber('count(`id`)', '`leader_id`=', emp_id)) != 0:
        raise APIValueError('emp_id', '该员工还有下属，请先修改所有下属的上司！')
    await emp.remove()
    dimission_emp = DimssionEmployee(id=emp_id,name=emp.name,sex=emp.sex,
                                    email=emp.email,phone_num=emp.phone_num,
                                     join_date=emp.join_date,leave_date=leave_date)
    await dimission_emp.save()
    return dimission_emp
