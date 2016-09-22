#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'cx'

import pdb
import hashlib, json, time, logging, calendar
from datetime import datetime, date, timedelta

from aiohttp import web

import orm
from apis import APIError, APIValueError, APIPermissionError, APIResourceNotFoundError
from coroweb import get, post
from models import Employee, Department, LevelSalary, Skill, EmpSkill, Attendance, EmpBonusFine
from attendanceManagement import NORMAL, LEAVE_EARLY, OVERDUE, ABSENCE_FROM_DUTY, HAS_VACATED

@get('/')
def index():
    return {
        '__template__' : 'employee_index.html'
    }

@get('/signin')
def signin(request):
    return {
        '__template__' : 'signin.html'
    }

@get('/signout')
def signout():
    r = web.HTTPFound('/signin')
    r.set_cookie(COOKIE_NAME, '-delete-', max_age=0, httponly=True)
    logging.info('user signed out.')
    return r

@get('/personal_info')
async def get_personal_info(request):
    user = request.__user__
    global __level_name
    if __level_name is None:
        level_name_list = await LevelSalary.findAll()
        __level_name = {ln['level']:ln['name'] for ln in level_name_list}
    user['level_name'] = __level_name[user.level]
    return {
        '__template__': 'personal_info.html',
        'emp': user
    }

@get('/verificate_vacation')
def verificate_vacation():
    return {
        '__template__': 'verificate_vacation.html',
    }

@get('/determine_bonuses')
def determine_bonuses():
    return {
        '__template__': 'determine_bonuses.html',
    }

@get('/query_salary')
def query_salary():
    return {
        '__template__': 'query_salary.html',
    }

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
async def manage_employee_skills():
    global __skills
    if not __skills:
        skills_list = await Skill.findAll()
        __skills = {s['id']:s['name'] for s in skills_list}
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

@get('/manage/employees_salary')
def manage_employees_salary():
    return {
        '__template__' : 'employees_salary.html'
    }

@get('/manage/employees_dept')
def manage_employees_dept():
    return {
        '__template__' : 'employees_dept.html'
    }

@get('/manage/employees_attendance')
def manage_employees_attendance():
    return {
        '__template__' : 'employees_attendance.html'
    }

@get('/manage/hide')
def hide():
    return {
        '__template__' : 'hide.html'
    }

salt = 'sdu'
origin_password = '123456'
GENERAL_MANAGER_LEVEL = 4
DEPT_MANAGER_LEVEL = 3
COOKIE_NAME = 'hr_dbdesign'
_COOKIE_KEY = 'software academy'
__skills = None
__level_name = None
__status = { NORMAL: '正常', LEAVE_EARLY: '早退', OVERDUE: '迟到',
            LEAVE_EARLY+OVERDUE: '迟到且早退',
            LEAVE_EARLY+ABSENCE_FROM_DUTY:'缺勤且早退',
            ABSENCE_FROM_DUTY: '缺勤', HAS_VACATED: '请假' }

def json_default(obj):
    if isinstance(obj, date):
        return str(obj)
    elif isinstance(obj, datetime):
        return str(obj)
    else:
        return obj.__dict__

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
        user = await Employee.find(uid)
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
        if level == DEPT_MANAGER_LEVEL and \
        (await Employee.findAll('`level`=? and dno=?', [level,dept_num])) != []:
            raise APIValueError('duplicate department manager', '已经存在部门经理')
    if is_general_manager and dept_num:
        raise APIValueError('department', '总经理不应该有部门编号')
    if is_general_manager and leader_id:
        raise APIValueError('leader', '总经理不应该有上司')
    #如果添加的员工是总经理且员工表中已经存在总经理，报错
    if is_general_manager and \
                        (await Employee.findAll('`level`=?', [level])) != []:
        raise APIValueError('duplicate general manager', '已经存在总经理')

def getSHA1(id, password):
    return hashlib.sha1((id + hashlib.sha1((id+password+salt).encode('utf-8'))\
                                         .hexdigest() + salt).encode('utf-8'))

async def getEmployeeID(join_date,dept_num):
    dept = await Department.find(dept_num)
    first_part = join_date.replace('-','')
    second_part = '%03d' % (dept_num or 0)
    third_part = '%09d' % dept.last_num if dept else '0'*9
    return first_part+second_part+third_part

def getAttendanceID(dt, emp_id):
    date = datetime.strftime(dt,'%Y%m%d')
    time_period = 'am' if dt.hour < 12 else 'pm'
    return date+time_period+emp_id

async def isSubordinate(leader, sub_id):
    if leader.id == sub_id:
        return False
    subordinate = await Employee.find(sub_id)
    if not subordinate:
        raise APIValueError('sub_id', '该下属不存在，请检查编号！')
    if leader.level == GENERAL_MANAGER_LEVEL:
        return True
    if leader.level == DEPT_MANAGER_LEVEL and leader.dno == subordinate.dno:
        return True
    if subordinate.leader_id == leader.id:
        return True
    return False

async def adjustAttendanceRecord(emp_id, vertifier_id, dt):
    id=getAttendanceID(dt, emp_id)
    attendance = await Attendance.find(id)
    if attendance:
        attendance.has_vacated = True
        attendance.vertifier_id = vertifier_id
        await attendance.update()
    else:
        attendance = Attendance(id=id, emp_id=emp_id,
                                in_time=None, out_time=None, has_vacated=True,
                                vertifier_id=vertifier_id, status=None)
        await attendance.save()

async def adjustTime(user_id, sub_id, date, time_period, isStartTime):
    if isStartTime and time_period == 'pm':
        await adjustAttendanceRecord(sub_id, user_id,
                               date+timedelta(hours=13))
    if not isStartTime and time_period == 'am':
        await adjustAttendanceRecord(sub_id, user_id,
                               date+timedelta(hours=7))
    if time_period == 'pm':
        date += timedelta(days=1)
    return date

@post('/api/authenticate')
async def authenticate(*, id, password):
    if not id:
        raise APIValueError('id', 'Invalid ID.')
    if not password:
        raise APIValueError('password', 'Invalid password.')
    users = await Employee.findAll('`id`=?', [id])
    if len(users) == 0:
        raise APIValueError('id', 'ID not exist.')
    user = users[0]
    #check user whether dimissioned
    if user.leave_date is not None:
        raise APIValueError('leave_date','员工已离职，不能登录系统')
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
    r.body = json.dumps(user, ensure_ascii=False, default=json_default).encode('utf-8')
    return r

@post('/api/change_password')
async def changePassword(request, *, origin_password, password):
    if not password:
        raise APIValueError('password', 'Invalid password.')
    user = request.__user__
    users = await Employee.findAll('`id`=?', [user.id])
    if len(users) == 0:
        raise APIValueError('id', 'ID not exist.')
    user = users[0]
    #check password
    sha1 = getSHA1(user.id, origin_password)
    if user.password != sha1.hexdigest():
        raise APIValueError('password', '原密码错误！')
    #change password
    sha1 = getSHA1(user.id, password)
    user.password = sha1.hexdigest()
    await user.update()
    logging.info('user %s\'s password changed' % user.id)
    #change password ok, set cookie
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400,
                                                                httponly=True)
    user.password = '******'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False, default=json_default).encode('utf-8')
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
                           join_date=join_date, leave_date=None, level=level,
                                   leader_id=leader_id if leader_id else None,
                                dno=dept_number, password=None, authority=10)
    emp.password = getSHA1(emp.id, origin_password).hexdigest()
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
    if date(*time.strptime(leave_date, '%Y-%m-%d')[:3]) < emp.join_date:
        raise APIValueError('leave_date', '员工入职日期大于离职日期！')
    #设置员工的离职日期
    emp.leave_date = leave_date
    await emp.update()
    return emp

@post('/api/change_position')
async def changePosition(*, emp_id, name, change_date, level, dept_number,
                                                                leader_id):
    if not emp_id:
        raise APIValueError('emp_id', 'Invalid employee id.')
    if not name:
        raise APIValueError('name', 'Invalid name.')
    if not level:
        raise APIValueError('level', 'Invalid level.')
    validateDate(change_date)
    await validateDeptAndLeader(dept_number, leader_id, level)
    emp = await Employee.find(emp_id)
    if not emp:
        raise APIValueError('emp_id', '该员工不存在！')
    if emp.name != name:
        raise APIValueError('emp_id', '该员工的姓名与你的输入不一致，请检查你的输入！')
    if (await Employee.findNumber('count(`id`)', '`leader_id`=?', [emp_id])) != 0:
        raise APIValueError('emp_id', '该员工还有下属，请先修改所有下属的上司！')
    if date(*time.strptime(change_date, '%Y-%m-%d')[:3]) < emp.join_date:
        raise APIValueError('change_date', '员工入职日期大于调职日期！')
    #将员工原先的记录中的离职日期改为调值日期
    emp.leave_date = change_date
    await emp.update()
    #重新插入一条员工记录
    emp = Employee(id=(await getEmployeeID(change_date,dept_number)),
               name=name, sex=emp.sex, email=emp.email, phone_num=emp.phone_num,
                           join_date=change_date, leave_date=None, level=level,
                                   leader_id=leader_id if leader_id else None,
                                dno=dept_number, password=None, authority=10)
    emp.password = getSHA1(emp.id, origin_password).hexdigest()
    await emp.save()
    logging.info('employee change position: %s' % emp)
    #添加完毕，将生成的职员作为json返回
    return emp

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
    if not emp_id:
        raise APIValueError('emp_id', '请填好员工编号！')
    if not name:
        raise APIValueError('name', 'Invalid name.')
    if not level:
        raise APIValueError('level', 'Invalid level.')
    validateDate(join_date)
    #从员工编号中获得部门编号
    dept_number = emp_id[8:11] if emp_id[8:11] != '000' else None
    #从数据库中搜索出该职员
    emp = await Employee.find(emp_id)
    if not emp:
        raise APIValueError('emp_id', '该员工不存在！')
    try:
        await validateDeptAndLeader(dept_number, leader_id, level)
    except APIValueError as e:
        if (e.data != 'duplicate general manager' or emp.level !=\
            GENERAL_MANAGER_LEVEL) and (e.data != 'duplicate department\
                            manager' or emp.level != DEPT_MANAGER_LEVEL):
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
async def searchEmpSkills(*, emp_id):
    global __skills
    if not emp_id:
        emp_skills = await EmpSkill.findAll()
    else:
        emp_skills = await EmpSkill.findAll('`emp_id`=?', [emp_id])
    for es in emp_skills:
        es.setdefault('skill_name', __skills[es['skill_id']])
    return dict(emp_skills=emp_skills)

@post('/api/add_emp_skill')
async def addEmpSkill(*, emp_id, skill_id):
    global __skills
    emp_skill = await EmpSkill.findAll('`emp_id`=? and `skill_id`=?', [emp_id, skill_id])
    if len(emp_skill) != 0:
        raise APIValueError('duplicate record in emp_skills',
                                            '员工技能对照表中已经有了这条记录')
    emp_skill = EmpSkill(emp_id=emp_id, skill_id=skill_id, proficiency=1)
    logging.info('add emp_skill %s' % emp_skill)
    await emp_skill.save()
    emp_skills = await EmpSkill.findAll('`emp_id`=? and `skill_id`=?', [emp_id, skill_id])
    es = emp_skills[0]
    es['skill_name'] = __skills[int(es['skill_id'])]
    return es

@post('/api/modify_emp_skill/{id}')
async def modifyEmpSkill(id, *, proficiency):
    global __skills
    emp_skill = await EmpSkill.find(id)
    if not emp_skill:
        raise APIValueError('emp_skill', '找不到该条员工技能记录')
    emp_skill.proficiency = proficiency
    await emp_skill.update()
    emp_skill['skill_name'] = __skills[int(emp_skill['skill_id'])]
    logging.info('modify emp_skill %s' % emp_skill)
    return emp_skill

@post('/api/delete_emp_skill')
async def deleteEmpSkill(*, emp_id, skill_id):
    global __skills
    emp_skill = await EmpSkill.findAll('`emp_id`=? and `skill_id`=?', [emp_id, skill_id])
    es = emp_skill[0]
    if len(emp_skill) == 0:
        raise APIValueError('emp_skill', '找不到该条员工技能记录')
    await es.remove()
    es['skill_name'] = __skills[int(es['skill_id'])]
    logging.info('delete emp_skill %s' % es)
    return es

@post('/api/delete_emp_skill/{id}')
async def deleteEmpSkillByID(id):
    global __skills
    emp_skill = await EmpSkill.find(id)
    if not emp_skill:
        raise APIValueError('emp_skill', '找不到该条员工技能记录')
    await emp_skill.remove()
    emp_skill['skill_name'] = __skills[int(emp_skill['skill_id'])]
    logging.info('delete emp_skill %s' % emp_skill)
    return emp_skill

@post('/api/add_department')
async def addDepartment(*, id, name):
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
async def deleteDepartment(*, id, name):
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

@post('/api/query_employees_salary')
async def queryEmployeesSalary(*, emp_id, start_year, start_month, end_year,
                                                                     end_month):
    sql = ['select emp.id, emp.name, month, basic_salary, bonus, fine \
           from employees emp, level_salary ls, emp_bonuses_fines ebf \
where emp.level = ls.level and emp.id = ebf.emp_id and emp.leave_date is null']
    args = []
    if any([start_year, start_month]) and not all([start_year, start_month]):
        raise APIValueError('start date', '开始年与开始月不能只有1个为空')
    if any([end_year, end_month]) and not all([end_year, end_month]):
        raise APIValueError('end date', '结束年与结束月不能只有1个为空')
    if emp_id:
        sql.append('and emp.id=?')
        args.append(emp_id)
    if all([start_year, start_month]):
        start_day = str(calendar.monthrange(int(start_year),int(start_month))[1])
        sql.append('and month>=?')
        args.append(start_year+'-'+start_month+'-'+start_day)
    if all([end_year, end_month]):
        end_day = str(calendar.monthrange(int(end_year),int(end_month))[1])
        sql.append('and month<=?')
        args.append(end_year+'-'+end_month+'-'+end_day)
    rs = await orm.select(' '.join(sql), args)
    payrolls = [{'id':r['id'], 'name':r['name'], 'bonus': r['bonus'],
                 'fine':r['fine'], 'month': datetime.strftime(r['month'], '%Y-%m'),
                 'basic_salary': r['basic_salary'],
                 'sum': r['basic_salary']+r['bonus']+r['fine']} for r in rs]
    return dict(payrolls=payrolls)

@post('/api/query_employees_dept')
async def queryEmployeesDept(*, dept_id):
    sql = ['select emp.id emp_id, emp.name emp_name, sex, email, phone_num,\
               join_date, level, leader_id, dept.name dept_name, manager_id\
                                       from employees emp, departments dept\
                    where emp.dno = dept.id and emp.leave_date is null']
    args = []
    if dept_id:
        sql.append('and dept.id=?')
        args.append(dept_id)
    global __level_name
    if __level_name is None:
        level_name_list = await LevelSalary.findAll()
        __level_name = {ln['level']:ln['name'] for ln in level_name_list}
    rs = await orm.select(' '.join(sql), args)
    emp_infos = [{'emp_id':r['emp_id'], 'emp_name':r['emp_name'],
                                      'sex': '女' if r['sex'] else '男',
                          'email': r['email'], 'phone_num': r['phone_num'],
              'level_name':__level_name[r['level']], 'leader_id': r['leader_id'],
         'dept_name': r['dept_name'], 'manager_id': r['manager_id']} for r in rs]
    #如果没有指定部门编号，可以显示总经理
    if not dept_id:
        gm = (await Employee.findAll('`level`=?', [GENERAL_MANAGER_LEVEL]))[0]
        emp_infos.append({'emp_id': gm.id, 'emp_name': gm.name,
                          'email': gm.email, 'phone_num': gm.phone_num,
                          'sex':'女' if gm.sex else '男',
                          'level_name': __level_name[gm.level],
                          'leader_id':'无', 'dept_name':'无', 'manager_id':'无'})
    return dict(emp_infos=emp_infos)

@post('/api/query_employees_attendance')
async def queryEmployeesAttendance(*, emp_id):
    sql = ['select emp.id, emp.name emp_name, in_time, out_time,\
                                       has_vacated, vertifier_id, status\
                                        from employees emp, attendance atd\
                        where emp.id = atd.emp_id and emp.leave_date is null']
    args = []
    if emp_id:
        sql.append('and emp.id=?')
        args.append(emp_id)
    rs = await orm.select(' '.join(sql), args)
    emp_atds = [{'emp_id':r['id'], 'emp_name':r['emp_name'],
'in_time': r['in_time'].strftime('%Y-%m-%d %H:%M:%S') if r['in_time'] else '无',
'out_time': r['out_time'].strftime('%Y-%m-%d %H:%M:%S') if r['out_time'] else '无',
                        'has_vacated': '是' if r['has_vacated'] else '否',
                 'vertifier_id':r['vertifier_id'] if r['vertifier_id'] else '无',
        'status': __status[r['status']] if r['status'] else '未知'} for r in rs]
    return dict(emp_atds=emp_atds)

@post('/api/modify_person_info')
async def modifyPersonInfo(request, *, email, phone_number):
    user = request.__user__
    if not user:
        raise APIPermissionError('该员工不存在！')
    emp = await Employee.find(user.id)
    emp.email = email
    emp.phone_num = phone_number
    await emp.update()
    logging.info('update employee: %s' % emp)
    #信息修改完毕，将更新后的职员作为json返回
    return emp

@post('/api/employee_come')
async def employeeCome(request):
    user = request.__user__
    if not user:
        raise APIPermissionError('该员工不存在！')
    now = datetime.now()
    attendance = await Attendance.find(getAttendanceID(now, user.id))
    if attendance.in_time:
        raise APIValueError('user', '您已经签到完成！')
    attendance.in_time = str(now)
    await attendance.update()
    return attendance

@post('/api/employee_leave')
async def employeeLeave(request):
    user = request.__user__
    if not user:
        raise APIPermissionError('该员工不存在！')
    now = datetime.now()
    id=getAttendanceID(now, user.id)
    attendance = await Attendance.find(id)
    if not attendance.in_time:
        raise APIValueError('attendance', '您还未签到！')
    if attendance.out_time:
        raise APIValueError('user', '您已经签离完成！')
    attendance.out_time = str(now)
    await attendance.update()
    return attendance

@post('/api/verificate_vacation')
async def verificateVacation(request, *, sub_id, start_time,
                              start_time_period, end_time, end_time_period):
    user = request.__user__
    if not user:
        raise APIPermissionError('该员工不存在！')
    if not (await isSubordinate(user, sub_id)):
        raise APIPermissionError('该员工不是你的下属！')
    start_date = datetime.strptime(start_time, '%Y-%m-%d')
    end_date = datetime.strptime(end_time, '%Y-%m-%d')
    if start_date > end_date or (start_date == end_date and start_time_period\
                                         == 'pm' and end_time_period == 'am'):
        raise APIValueError('time', '开始时间不能大于结束时间')
    start_date = await adjustTime(user.id, sub_id, start_date, start_time_period,
                                                                          True)
    end_date = await adjustTime(user.id, sub_id, end_date, end_time_period,
                                                                        False)
    #从开始日期的早上7点开始调整对应记录
    start_date += timedelta(hours=7)
    while start_date < end_date:
        await adjustAttendanceRecord(sub_id, user.id, start_date)
        start_date += timedelta(hours=4)
        await adjustAttendanceRecord(sub_id, user.id, start_date)
        start_date += timedelta(hours=20)
    return user

@post('/api/determine_bonuses')
async def determineBonuses(request, *, sub_id, bonus):
    user = request.__user__
    if not user:
        raise APIPermissionError('该员工不存在！')
    if not (await isSubordinate(user, sub_id)):
        raise APIPermissionError('该员工不是你的下属！')
    today = date.today()
    last_month = date(today.year, today.month, 1) - timedelta(days=1)
    last_month_str = datetime.strftime(last_month, '%Y-%m-%d')
    ebfs = await EmpBonusFine.findAll('`emp_id`=? and `month`=?', [sub_id,
                                                              last_month_str])
    if len(ebfs) == 0:
        raise APIResourceNotFoundError('emp_bonuses_fines',
                                   '记录尚未建立，请等待一段时间')
    if len(ebfs) > 1:
        raise APIError('system error', 'emp_bonuses_fines', '系统内部出现故障')
    ebf = ebfs[0]
    if ebf.bonus:
        raise APIPermissionError('该员工的奖金已被确定！')
    ebf.bonus = bonus
    await ebf.update()
    return ebf

@post('/api/query_salary')
async def querySalary(request, *, start_year, start_month, end_year, end_month):
    user = request.__user__
    if not user:
        raise APIPermissionError('该员工不存在！')
    if start_year > end_year or (start_year == end_year and\
                                            int(start_month) > int(end_month)):
        raise APIValueError('date', '开始日期大于结束日期！')
    start_day = str(calendar.monthrange(int(start_year),int(start_month))[1])
    end_day = str(calendar.monthrange(int(end_year),int(end_month))[1])
    ebfs = await EmpBonusFine.findAll('`emp_id`=? and `month`>=? and `month`<=?',
                          [user.id, start_year+'-'+start_month+'-'+start_day,
                                           end_year+'-'+end_month+'-'+end_day])
    if len(ebfs) == 0:
        raise APIValueError('month', '不存在符合条件的工资记录！')
    #如果最近一个月的奖金还未被领导确定
    if ebfs[-1].bonus is None:
        ebfs = ebfs[:-1]
    if len(ebfs) == 0:
        raise APIValueError('month', '不存在符合条件的工资记录！')
    basic_salary = (await LevelSalary.find(user.level)).basic_salary
    payrolls = [{'month':e.month.strftime('%Y-%m'), 'bonus': e.bonus,\
                'fine': e.fine, 'sum': basic_salary+e.bonus+e.fine,\
                 'basic_salary': basic_salary} for e in ebfs]
    return dict(payrolls=payrolls)
