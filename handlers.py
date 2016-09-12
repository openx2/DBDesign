#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'cx'

import hashlib, json, time, datetime, logging
import pdb

from aiohttp import web
import pymysql

from apis import APIError, APIValueError, APIPermissionError, APIResourceNotFoundError
from coroweb import get, post
from models import User, Employee, Department, LevelSalary, DimssionEmployee, Skills, EmpSkills

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

@get('/manage/delete_employee')
def manage_delete_employee():
    return {
        '__template__' : 'manage_delete_employee.html'
    }

@get('/manage/change_position')
def manage_change_position():
    return {
        '__template__' : 'manage_change_position.html'
    }

@get('/manage/modify_employee_info')
def manage_modify_employee_info():
    return {
        '__template__' : 'manage_modify_employee_info.html'
    }

@get('/manage/manage_employee_skills')
def manage_employee_skills():
    return {
        '__template__' : 'manage_employee_skills.html'
    }

@get('/manage/add_department')
def manage_add_department():
    return {
        '__template__' : 'manage_add_department.html'
    }

@get('/manage/delete_department')
def manage_delete_department():
    return {
        '__template__' : 'manage_delete_department.html'
    }

@get('/manage/modify_department_info')
def manage_modify_department_info():
    return {
        '__template__' : 'manage_modify_department_info.html'
    }

@get('/manage/hide')
def hide():
    return {
        '__template__' : 'hide.html'
    }

salt = 'sdu'
GENERAL_MANAGER_LEVEL = 4
DEPT_MANAGER_LEVEL = 4
COOKIE_NAME = 'hr_dbdesign'
_COOKIE_KEY = 'software academy'
__skills = None

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
        time.strptime(date, '%Y-%m-%d')
    except ValueError as e:
        raise APIValueError('date', e)

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
async def deleteEmployee(*, emp_id, name, leave_date):
    if not emp_id:
        raise APIValueError('emp_id', 'Invalid employee id.')
    emp = await Employee.find(emp_id)
    if not emp:
        raise APIValueError('emp_id', '该员工不存在！')
    if emp.name != name:
        raise APIValueError('emp_id', '该员工的姓名与你的输入不一致，请检查你的输入！')
    if (await Employee.findNumber('count(`id`)', '`leader_id`=?', [emp_id])) != 0:
        raise APIValueError('emp_id', '该员工还有下属，请先修改所有下属的上司！')
    validateDate(leave_date)
    if datetime.date(*time.strptime(leave_date, '%Y-%m-%d')) < emp.join_date:
        raise APIValueError('leave_date', '员工入职日期大于离职日期！')
    #删除该员工，并将他添加到离职员工表中
    await emp.remove()
    dimission_emp = DimssionEmployee(id=emp_id,name=emp.name,sex=emp.sex,
                                    email=emp.email,phone_num=emp.phone_num,
                                     join_date=emp.join_date,leave_date=leave_date)
    await dimission_emp.save()
    return dimission_emp

@post('/api/change_position')
async def changePosition(*, emp_id, name, change_date, level, dept_number,
                                                                leader_id):
    emp = (await deleteEmployee(emp_id, name, change_date))
    return (await addEmployee(name=name, sex=emp.sex, email=emp.email,
                      phone_number=emp.phone_num, join_date=change_date,
                     level=level, dept_number=dept_number, leader_id=leader_id))

@post('/api/search_employee')
async def searchEmployee(*, emp_id):
    if not emp_id:
        raise APIValueError('emp_id', 'Invalid employee id.')
    emp = await Employee.find(emp_id)
    if not emp:
        raise APIValueError('emp_id', '该员工不存在！')
    return emp

@post('/api/modify_employee_info')
async def modifyEmployeeInfo(*, emp_id, name, sex, email, phone_number, join_date,
                                                             level, leader_id):
    if not name:
        raise APIValueError('name', 'Invalid name.')
    if not level:
        raise APIValueError('level', 'Invalid level.')
    validateDate(join_date)
    #从员工编号中获得部门编号
    dept_number = emp_id[8:11] if emp_id[8:11] != '000' else None
    #从数据库中搜索出该职员
    emp = await Employee.find(emp_id)
    try:
        await validateDeptAndLeader(dept_number, leader_id, level)
    except APIValueError as e:
        if e.data != 'duplicate general manager' or emp.level != 4:
            raise e
    emp.id = (await getEmployeeID(join_date, dept_number))
    emp.name = name.strip()
    emp.sex = sex
    emp.email = email
    emp.phone_num = phone_number
    emp.join_date = join_date
    emp.level = level
    emp.phone_num = phone_number
    emp.leader_id = leader_id if leader_id else None
    await emp.update()
    logging.info('update employee: %s' % emp)
    #添加完毕，将更新后的职员作为json返回
    return emp

@post('/api/search_emp_skills')
async def search_emp_skills(*, emp_id):
    global __skills
    if not __skills:
        skills_list = await Skills.findAll()
        __skills = {s['id']:s['name'] for s in skills_list}
    if not emp_id:
        emp_skills = await EmpSkills.findAll()
    else:
        emp_skills = await EmpSkills.findAll('`emp_id`=?', [emp_id])
    for es in emp_skills:
        es.setdefault('skill_name', __skills[es['skill_id']])
    return dict(emp_skills=emp_skills)

@post('/api/add_emp_skill')
async def add_emp_skill(*, emp_id, skill_id):
    emp_skill = await EmpSkills.findAll('`emp_id`=? and `skill_id`=?', [emp_id, skill_id])
    if len(emp_skill) != 0:
        raise APIValueError('duplicate record in emp_skills',
                                            '员工技能对照表中已经有了这条记录')
    emp_skill = EmpSkills(emp_id=emp_id, skill_id=skill_id)
    await emp_skill.save()
    logging.info('add emp_skill %s' % emp_skill)
    return emp_skill

@post('/api/delete_emp_skill')
async def delete_emp_skill(*, emp_id, skill_id):
    emp_skill = await EmpSkills.findAll('`emp_id`=? and `skill_id`=?', [emp_id, skill_id])
    if not emp_skill:
        raise APIValueError('emp_skill', '找不到该条员工技能记录')
    await (emp_skill[0]).remove()
    emp_skill['skill_name'] = __skills[emp_skill['skill_id']]
    logging.info('delete emp_skill %s' % emp_skill)
    return emp_skill

@post('/api/delete_emp_skill/{id}')
async def delete_emp_skill_by_id(id):
    emp_skill = await EmpSkills.find(id)
    if not emp_skill:
        raise APIValueError('emp_skill', '找不到该条员工技能记录')
    await emp_skill.remove()
    emp_skill['skill_name'] = __skills[emp_skill['skill_id']]
    logging.info('delete emp_skill %s' % emp_skill)
    return emp_skill

@post('/api/add_department')
async def add_department(*, id, name):
    if not id:
        raise APIValueError('dept_id', 'Invaild department ID')
    if (await Department.find(id)):
        raise APIValueError('dept_id', '有该编号的部门已存在！')
    if not name:
        raise APIValueError('dept_name', 'Invaild department name')
    dept = Department(id=id, name=name, manager_id=None, last_num=1)
    await dept.save()
    logging.info('add department %s' % dept)
    return dept

@post('/api/delete_department')
async def delete_department(*, id, name):
    if not id:
        raise APIValueError('dept_id', 'Invaild department ID')
    if not name:
        raise APIValueError('dept_name', 'Invaild department name')
    dept = await Department.find(id)
    if not dept:
        raise APIValueError('dept_id', '有该编号的部门不存在！')
    if dept.name != name:
        raise APIValueError('dept_name', '该编号的部门名称不是输入的名称，请检查输入')
    await dept.remove()
    logging.info('delete department %s' % dept)
    return dept

@post('/api/search_department')
async def searchDepartment(*, id):
    if not id:
        raise APIValueError('dept_id', 'Invaild department ID')
    dept = await Department.find(id)
    if not dept:
        raise APIValueError('dept_id', '该部门不存在！')
    return dept

@post('/api/modify_department_info')
async def modifyDepartmentInfo(*, id, name, manager_id):
    if not id:
        raise APIValueError('dept_id', 'Invaild department ID')
    if not name:
        raise APIValueError('dept_name', 'Invaild department name')
    if not manager_id:
        raise APIValueError('manager_id', 'Invaild department manager_id')
    manager = await Employee.find(manager_id)
    if not manager:
        raise APIValueError('manager_id', '该员工不存在！')
    if manager.level != DEPT_MANAGER_LEVEL:
        raise APIValueError('manager_id', '该员工的级别不是部门经理，请先修改员工信息')
    if manager.dno != id:
        raise APIValueError('manager_id', '该员工不是该部门的员工，请先修改员工信息')
    dept = await Department.find(id)
    if not dept:
        raise APIValueError('dept_id', '该部门不存在！')
    dept.name = name
    dept.manager_id = manager_id
    await dept.update()
    logging.info('modify department %s' % dept)
    return dept
