#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'cx'

from orm import Model,StringField,IntegerField,BooleanField,DatetimeField

class Employee(Model):
    '''员工表，有编号、姓名、性别、电话、邮箱、进入时间、离开时间、级别、部门编号、上级编号、密码、权限级别的属性'''
    __table__ = 'employees'

    id = StringField(primary_key=True, ddl='char(20)')
    name = StringField(ddl='char(20)')
    sex = BooleanField()
    email = StringField(ddl='varchar(50)')
    phone_num = StringField(ddl='varchar(20)')
    join_date = DatetimeField()
    leave_date = DatetimeField()
    level = IntegerField()
    dno = IntegerField()
    leader_id = StringField(ddl='char(20)')
    password = StringField(ddl='varchar(50)')
    authority = IntegerField()

class Department(Model):
    '''部门表，有编号、名称、经理编号、本部门最近加入职员的部门内编号的属性'''
    __table__ = 'departments'

    id = IntegerField(primary_key=True)
    name = StringField(ddl='varchar(30)')
    manager_id = StringField(ddl='char(20)')
    last_num = IntegerField()

class LevelSalary(Model):
    '''级别表，有级别、名称、对应基本工资的属性'''
    __table__ = 'level_salary'

    level = IntegerField(primary_key=True)
    name = StringField(ddl='char(20)')
    basic_salary = IntegerField()

class Skill(Model):
    '''技能表，包括技能编号和技能名称'''
    __table__ = 'skills'

    id = IntegerField(primary_key=True)
    name = StringField(ddl='varchar(100)')

class EmpSkill(Model):
    '''员工技能对照表，包括条目id、员工编号、技能编号'''
    __table__ = 'emp_skills'

    id = IntegerField(primary_key=True)
    emp_id = StringField(ddl='char(20)')
    skill_id = IntegerField()
    proficiency = IntegerField()

class Attendance(Model):
    '''员工出席情况表，包括编号、员工编号、签到时间、签离时间、是否请假、批准人编号'''
    __table__ = 'attendance'

    id = StringField(primary_key=True, ddl='char(30)')
    emp_id = StringField(ddl='char(20)')
    in_time = DatetimeField()
    out_time = DatetimeField()
    has_vacated = BooleanField()
    vertifier_id = StringField(ddl='char(20)')
    status = IntegerField()

class EmpBonusFine(Model):
    '''员工月奖罚金表，包括编号、员工编号、月份、奖金、罚款'''
    __table__ = 'emp_bonuses_fines'

    id = IntegerField(primary_key=True)
    emp_id = StringField(ddl='char(20)')
    month = DatetimeField()
    bonus = IntegerField()
    fine = IntegerField()
